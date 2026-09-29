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

    def __init__(self, path: Path):
        import joblib  # imported here so the placeholder works without it

        bundle = joblib.load(path)
        self._model = bundle["model"]
        self._features = bundle.get("feature_names", FEATURE_NAMES)
        self.version = str(bundle.get("version", "ml-unknown"))

    def predict_score(self, f: dict) -> float:
        row = [[f[name] for name in self._features]]
        return float(self._model.predict_proba(row)[0][1])


def load_model(model_path: str | None) -> RiskModel:
    """Use the ML model if the file exists, otherwise the rule-based fallback."""
    if model_path and Path(model_path).is_file():
        try:
            model = MLRiskModel(Path(model_path))
            logger.info("Loaded ML risk model version %s", model.version)
            return model
        except Exception:
            logger.exception("Failed to load ML model, using rule-based fallback")
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
        self._model = model or RuleBasedRiskModel()
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
        if not isinstance(score, (int, float)) or math.isnan(score) or not 0.0 <= score <= 1.0:
            raise ValueError(f"Invalid risk score from model: {score!r}")
        return float(score)

    def assess(self, features: dict) -> RiskResult:
        """Never raises: a model failure falls back to the rules and is logged."""
        model = self._model
        try:
            score = self._validate_score(model.predict_score(features))
        except Exception:
            logger.exception("Risk model failed, falling back to rule-based model")
            model = self._fallback
            score = self._validate_score(model.predict_score(features))

        result = RiskResult(
            risk_score=round(score, 4),
            risk_level=level_for(score),
            model_version=model.version,
        )
        # Prediction logging (requirement): inputs, output, version.
        logger.info("risk_prediction features=%s result=%s", features, result)
        return result
