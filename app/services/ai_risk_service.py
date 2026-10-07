"""
app/services/ai_risk_service.py

AI risk assessment service for transactions.

Design: routes and the transaction service only ever call
`AIRiskService.assess(...)`. What sits behind it (rule-based placeholder now,
trained ML model later) can be swapped without touching anything else.
"""
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.risk_assessment import RiskAssessment
from app.models.enums import RiskLevel

logger = logging.getLogger("ai_risk")

# Feature order is the contract between the service and any trained model.
FEATURE_NAMES = [
    "amount",
    "amount_ratio",          # amount / customer's average transaction amount
    "txn_count_last_hour",
    "hour_of_day",
    "is_new_beneficiary",    # 1 or 0
]

LOW_MAX = 0.40
MEDIUM_MAX = 0.70

# risk_assessments.model_version is VARCHAR(20) on PostgreSQL: version strings must fit.
MAX_VERSION_LEN = 20

# The ML team's fraud model (Banking-Fraud_Detection-Model) was trained on BankSim card payments.
# The API has no equivalent for several of its inputs, so these neutral defaults are used.
# Any of them can be overridden by passing the key in the features dict.
FRAUD_MODEL_DEFAULTS = {
    # BankSim day index (0-179); not available in the API
    "step": 0,
    # never a BankSim ID -> encoded as "unknown" by the model
    "customer_ref": "BANKAPI-CUSTOMER",
    "merchant_ref": "BANKAPI-MERCHANT",   # same
    "age_group": "U",                 # BankSim age bucket, "U" = unknown
    "gender": "U",                    # the API does not store gender
    "category": "es_otherservices",   # BankSim merchant category
}


@dataclass
class RiskResult:
    risk_score: float        # 0.0 - 1.0
    risk_level: str          # LOW | MEDIUM | HIGH
    model_version: str


class RiskModel(Protocol):
    version: str

    def predict_score(self, features: dict) -> float: ...


class RuleBasedRiskModel:
    """Placeholder used until the ML team delivers a real model."""

    version = "rules-0.1"

    def predict_score(self, f: dict) -> float:
        score = 0.05
        if f["amount"] > 5000:
            score += 0.25
        if f["amount_ratio"] > 5:
            score += 0.25
        elif f["amount_ratio"] > 2:
            score += 0.10
        if f["txn_count_last_hour"] >= 5:
            score += 0.20
        elif f["txn_count_last_hour"] >= 3:
            score += 0.10
        if f["hour_of_day"] < 5:
            score += 0.10
        if f["is_new_beneficiary"]:
            score += 0.10
        return min(score, 1.0)


class MLRiskModel:
    """Loads a joblib bundle: {"model", "feature_names", "version"}.

    Expects a classifier with predict_proba (fraud class = column 1).
    """

    def __init__(self, path: Path | None = None, bundle: dict | None = None):
        if bundle is None:
            import joblib  # imported here so the placeholder works without it

            bundle = joblib.load(path)
        self._model = bundle["model"]
        self._features = bundle.get("feature_names", FEATURE_NAMES)
        self.version = str(bundle.get(
            "version", "ml-unknown"))[:MAX_VERSION_LEN]
        self.base_version = self.version

    def predict_score(self, f: dict) -> float:
        row = [[f[name] for name in self._features]]
        return float(self._model.predict_proba(row)[0][1])


class FraudPipelineModel:
    """Adapter for the ML team's fraud model (`Banking-Fraud_Detection-Model`).

    The bundle is a dict with a fitted sklearn Pipeline (encoding + scaling + RandomForest) under
    "pipeline", so the pipeline takes RAW fields: step, customer, age, gender, merchant, category, amount.

    IMPORTANT LIMITATION: the model learned mostly from customer/merchant identity. Every ID coming
    from this API is unseen by the model, so its scores are weak (measured ROC AUC ~0.55 vs 0.996
    with known IDs). That is why the default mode is "hybrid" (see HybridRiskModel).

    Only load a .pkl from this repository: unpickling untrusted files can execute code.
    """

    REQUIRED_KEYS = ("pipeline", "feature_names",
                     "allowed_values", "model_version")

    def __init__(self, bundle: dict):
        missing = [k for k in self.REQUIRED_KEYS if k not in bundle]
        if missing:
            raise ValueError(f"Fraud model bundle is missing keys: {missing}")

        self._pipeline = bundle["pipeline"]
        self._features = list(bundle["feature_names"])
        self._allowed = bundle["allowed_values"]
        self.base_version = str(bundle["model_version"])
        self.version = f"fraud-rf-{self.base_version}"[:MAX_VERSION_LEN]

        self._check_sklearn_version(bundle.get("sklearn_version"))
        # Predict once at load time: a broken or incompatible pickle fails here (and the service
        # falls back to rules at startup) instead of on a customer's first transaction.
        self._self_test()

    @staticmethod
    def _check_sklearn_version(trained_with: str | None) -> None:
        import sklearn

        if trained_with and trained_with != sklearn.__version__:
            logger.warning(
                "Fraud model was trained with scikit-learn %s but %s is installed; pin the version "
                "in requirements.txt or ask the ML team to retrain",
                trained_with,
                sklearn.__version__,
            )

    def _self_test(self) -> None:
        score = self.predict_score({"amount": 100.0})
        if not 0.0 <= score <= 1.0:
            raise ValueError(
                f"Fraud model self-test returned an invalid score: {score!r}")

    def _pick(self, f: dict, key: str, field: str | None = None) -> str:
        """Value for a categorical field; anything outside the model's allowed values -> default."""
        value = str(f.get(key, FRAUD_MODEL_DEFAULTS[key]))
        allowed = self._allowed.get(field or key)
        if allowed is not None and value not in allowed:
            return FRAUD_MODEL_DEFAULTS[key]
        return value

    def build_row(self, f: dict) -> dict:
        """Map API risk features onto the model's raw input fields."""
        return {
            "step": int(f.get("step", FRAUD_MODEL_DEFAULTS["step"])),
            "customer": str(f.get("customer_ref", FRAUD_MODEL_DEFAULTS["customer_ref"])),
            "age": self._pick(f, "age_group", "age"),
            "gender": self._pick(f, "gender"),
            "merchant": str(f.get("merchant_ref", FRAUD_MODEL_DEFAULTS["merchant_ref"])),
            "category": self._pick(f, "category"),
            "amount": float(f["amount"]),
        }

    def predict_score(self, f: dict) -> float:
        import pandas as pd

        row = self.build_row(f)
        # Training column names AND order matter: the pipeline selects columns by name.
        X = pd.DataFrame([row], columns=self._features)
        return float(self._pipeline.predict_proba(X)[0, 1])


class HybridRiskModel:
    """Final score = max(ML score, rule score).

    The ML model can only RAISE a score, never lower it, so switching it on can never make the
    system flag less than the rule-based model does today. Component scores are logged.
    """

    def __init__(self, ml_model: RiskModel, rules: RiskModel | None = None):
        self._ml = ml_model
        self._rules = rules or RuleBasedRiskModel()
        base = getattr(ml_model, "base_version", ml_model.version)
        self.version = f"hybrid-{base}"[:MAX_VERSION_LEN]

    def predict_score(self, f: dict) -> float:
        # An ML failure propagates; AIRiskService.assess() then falls back to the rules.
        ml_score = self._ml.predict_score(f)
        rule_score = self._rules.predict_score(f)
        logger.info("risk_components ml=%.4f rules=%.4f", ml_score, rule_score)
        return max(ml_score, rule_score)


def _load_ml_model(path: Path) -> RiskModel:
    import joblib  # reads files written by pickle.dump as well

    bundle = joblib.load(path)
    if isinstance(bundle, dict) and "pipeline" in bundle:
        return FraudPipelineModel(bundle)  # ML team's fraud model
    # legacy format: {"model", "feature_names", "version"}
    return MLRiskModel(bundle=bundle)


def load_model(model_path: str | None, mode: str | None = None) -> RiskModel:
    """Use the ML model if the file exists, otherwise the rule-based fallback.

    mode (default: RISK_MODEL_MODE setting): "hybrid" = max(ML, rules); "ml" = ML score only.
    """
    mode = mode or get_settings().risk_model_mode
    if model_path and Path(model_path).is_file():
        try:
            ml_model = _load_ml_model(Path(model_path))
            model = ml_model if mode == "ml" else HybridRiskModel(ml_model)
            logger.info("Loaded risk model %s (mode=%s)", model.version, mode)
            return model
        except Exception:
            logger.exception(
                "Failed to load ML model, using rule-based fallback")
    else:
        logger.warning("No ML model file found, using rule-based placeholder")
    return RuleBasedRiskModel()


def level_for(score: float) -> str:
    if score < LOW_MAX:
        return "LOW"
    if score < MEDIUM_MAX:
        return "MEDIUM"
    return "HIGH"


class AIRiskService:
    def __init__(self, model: RiskModel | None = None):
        if model is None:
            from app.ai.model import get_model
            model = get_model()

        self._model = model
        self._fallback = RuleBasedRiskModel()

    @property
    def model_version(self) -> str:
        return self._model.version

    @staticmethod
    def prepare_features(
        amount: float,
        avg_amount: float,
        txn_count_last_hour: int,
        hour_of_day: int,
        is_new_beneficiary: bool,
    ) -> dict:
        ratio = amount / avg_amount if avg_amount and avg_amount > 0 else 1.0

        return {
            "amount": float(amount),
            "amount_ratio": float(ratio),
            "txn_count_last_hour": int(txn_count_last_hour),
            "hour_of_day": int(hour_of_day),
            "is_new_beneficiary": 1 if is_new_beneficiary else 0,
        }

    @staticmethod
    def _validate_score(score: float) -> float:
        if (
            not isinstance(score, (int, float))
            or math.isnan(score)
            or not 0.0 <= score <= 1.0
        ):
            raise ValueError(f"Invalid risk score from model: {score!r}")

        return float(score)

    def assess(self, features: dict) -> RiskResult:
        """Never raises: a model failure falls back to the rules and is logged."""

        model = self._model

        try:
            score = self._validate_score(
                model.predict_score(features)
            )
        except Exception:
            logger.exception(
                "Risk model failed, falling back to rule-based model"
            )

            model = self._fallback
            score = self._validate_score(
                model.predict_score(features)
            )

        result = RiskResult(
            risk_score=round(score, 4),
            risk_level=level_for(score),
            model_version=model.version,
        )

        logger.info(
            "risk_prediction features=%s result=%s",
            features,
            result,
        )

        return result

    @staticmethod
    def save_assessment(
        db: Session,
        customer_id: int,
        transaction_id: int | None,
        result: RiskResult,
        commit: bool = False,
    ) -> RiskAssessment:
        assessment = RiskAssessment(
            customer_id=customer_id,
            transaction_id=transaction_id,
            risk_score=result.risk_score,
            risk_level=RiskLevel(result.risk_level),
            model_version=result.model_version,
        )

        db.add(assessment)

        if commit:
            db.commit()
            db.refresh(assessment)
        else:
            db.flush()

        logger.info(
            "risk_assessment_saved id=%s customer_id=%s transaction_id=%s",
            assessment.id,
            customer_id,
            transaction_id,
        )

        return assessment
