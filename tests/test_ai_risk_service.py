from app.services.ai_risk_service import AIRiskService, RuleBasedRiskModel


def test_high_risk_transaction_scores_high():
    svc = AIRiskService(RuleBasedRiskModel())
    f = svc.prepare_features(9000, 500, 6, 3, True)
    result = svc.assess(f)
    assert result.risk_level == "HIGH"
    assert result.model_version == "rules-0.1"


def test_normal_transaction_scores_low():
    svc = AIRiskService(RuleBasedRiskModel())
    result = svc.assess(svc.prepare_features(50, 60, 0, 14, False))
    assert result.risk_level == "LOW"


def test_broken_model_falls_back_instead_of_raising():
    class Broken:
        version = "broken"

        def predict_score(self, features):
            raise RuntimeError("boom")

    svc = AIRiskService(Broken())
    result = svc.assess(svc.prepare_features(50, 60, 0, 14, False))
    assert result.model_version == "rules-0.1"


def test_invalid_score_is_rejected_and_falls_back():
    class Nan:
        version = "nan"

        def predict_score(self, features):
            return float("nan")

    svc = AIRiskService(Nan())
    result = svc.assess(svc.prepare_features(50, 60, 0, 14, False))
    assert 0.0 <= result.risk_score <= 1.0
    assert result.model_version == "rules-0.1"


# ---------- ML team's fraud model (app/ml/fraud_detection_model.pkl) ----------

from pathlib import Path  # noqa: E402

import joblib  # noqa: E402
import pytest  # noqa: E402

from app.services.ai_risk_service import (  # noqa: E402
    FRAUD_MODEL_DEFAULTS,
    FraudPipelineModel,
    HybridRiskModel,
    MLRiskModel,
    load_model,
)

FRAUD_MODEL_PATH = "app/ml/fraud_detection_model.pkl"

SAMPLE_FEATURES = [
    {"amount": 20.0, "amount_ratio": 1.0, "txn_count_last_hour": 0,
        "hour_of_day": 14, "is_new_beneficiary": 0},
    {"amount": 500.0, "amount_ratio": 2.5, "txn_count_last_hour": 3,
        "hour_of_day": 2, "is_new_beneficiary": 1},
    {"amount": 9000.0, "amount_ratio": 18.0, "txn_count_last_hour": 6,
        "hour_of_day": 3, "is_new_beneficiary": 1},
]


@pytest.fixture(scope="module")
def fraud_model():
    return load_model(FRAUD_MODEL_PATH, mode="ml")


def test_fraud_model_file_loads_as_pipeline_adapter(fraud_model):
    assert isinstance(fraud_model, FraudPipelineModel)
    assert fraud_model.version == "fraud-rf-1.0.0"


@pytest.mark.parametrize("features", SAMPLE_FEATURES)
def test_fraud_model_scores_are_valid_probabilities(fraud_model, features):
    assert 0.0 <= fraud_model.predict_score(features) <= 1.0


def test_fraud_model_row_mapping_uses_documented_defaults(fraud_model):
    row = fraud_model.build_row({"amount": 123.45})
    assert row == {
        "step": FRAUD_MODEL_DEFAULTS["step"],
        "customer": FRAUD_MODEL_DEFAULTS["customer_ref"],
        "age": "U",
        "gender": "U",
        "merchant": FRAUD_MODEL_DEFAULTS["merchant_ref"],
        "category": "es_otherservices",
        "amount": 123.45,
    }


def test_fraud_model_row_mapping_accepts_overrides_and_rejects_bad_values(fraud_model):
    row = fraud_model.build_row(
        {"amount": 10, "category": "es_travel", "age_group": "3", "gender": "F"})
    assert (row["category"], row["age"], row["gender"]) == (
        "es_travel", "3", "F")
    # Values the model never saw fall back to the neutral default instead of crashing a transaction.
    row = fraud_model.build_row(
        {"amount": 10, "category": "not_a_category", "age_group": "99", "gender": "X"})
    assert (row["category"], row["age"], row["gender"]) == (
        "es_otherservices", "U", "U")


def test_default_mode_is_hybrid_and_version_fits_database_column():
    model = load_model(FRAUD_MODEL_PATH)
    assert isinstance(model, HybridRiskModel)
    assert model.version == "hybrid-1.0.0"
    # risk_assessments.model_version is VARCHAR(20) on PostgreSQL
    assert len(model.version) <= 20


@pytest.mark.parametrize("features", SAMPLE_FEATURES)
def test_hybrid_never_scores_below_rules_or_ml(features):
    hybrid = load_model(FRAUD_MODEL_PATH, mode="hybrid")
    rules = RuleBasedRiskModel().predict_score(features)
    ml = load_model(FRAUD_MODEL_PATH, mode="ml").predict_score(features)
    assert hybrid.predict_score(features) == pytest.approx(max(rules, ml))


def test_hybrid_still_flags_what_the_rules_flag():
    svc = AIRiskService(load_model(FRAUD_MODEL_PATH, mode="hybrid"))
    result = svc.assess(svc.prepare_features(9000, 500, 6, 3, True))
    assert result.risk_level == "HIGH"
    assert result.model_version == "hybrid-1.0.0"


def test_ml_mode_assess_reports_fraud_model_version():
    svc = AIRiskService(load_model(FRAUD_MODEL_PATH, mode="ml"))
    result = svc.assess(svc.prepare_features(50, 60, 0, 14, False))
    assert result.model_version == "fraud-rf-1.0.0" and 0.0 <= result.risk_score <= 1.0


def test_missing_model_file_uses_rules(tmp_path):
    assert isinstance(load_model(str(tmp_path / "nope.pkl")),
                      RuleBasedRiskModel)


def test_corrupt_model_file_uses_rules(tmp_path):
    bad = tmp_path / "bad.pkl"
    bad.write_bytes(b"this is not a pickle")
    assert isinstance(load_model(str(bad)), RuleBasedRiskModel)


def test_bundle_missing_keys_uses_rules(tmp_path):
    bad = tmp_path / "incomplete.pkl"
    joblib.dump({"pipeline": object()}, bad)
    assert isinstance(load_model(str(bad)), RuleBasedRiskModel)


class BrokenPipeline:  # module level so it can be pickled
    def predict_proba(self, X):
        raise RuntimeError("incompatible pickle")


def test_broken_pipeline_fails_self_test_and_uses_rules(tmp_path):
    good = joblib.load(FRAUD_MODEL_PATH)
    bad = tmp_path / "broken.pkl"
    joblib.dump({**good, "pipeline": BrokenPipeline()}, bad)
    assert isinstance(load_model(str(bad)), RuleBasedRiskModel)


def test_legacy_bundle_format_still_loads(tmp_path):
    from sklearn.linear_model import LogisticRegression

    from app.services.ai_risk_service import FEATURE_NAMES

    clf = LogisticRegression().fit(
        [[0, 0, 0, 0, 0], [9000, 18, 6, 3, 1]], [0, 1])
    path = tmp_path / "legacy.pkl"
    joblib.dump({"model": clf, "feature_names": FEATURE_NAMES,
                "version": "legacy-1"}, path)
    model = load_model(str(path), mode="ml")
    assert isinstance(model, MLRiskModel) and model.version == "legacy-1"
    assert 0.0 <= model.predict_score(SAMPLE_FEATURES[2]) <= 1.0


def test_model_file_is_in_repo_where_the_default_path_points():
    from app.core.config import Settings

    assert Path(Settings().risk_model_path).is_file()


# ---------- save_assessment (now a method of AIRiskService) and app/ai/model.py ----------

from app.models import RiskAssessment  # noqa: E402
from app.services.ai_risk_service import RiskResult  # noqa: E402


def _customer_id(make_user):
    return make_user().profile.id


def test_save_assessment_flushes_without_committing(db, make_user):
    cid = _customer_id(make_user)
    saved = AIRiskService.save_assessment(
        db, cid, None, RiskResult(0.55, "MEDIUM", "hybrid-1.0.0"))
    assert saved.id is not None  # flushed, so the id exists...
    db.rollback()  # ...but not committed: the caller's transaction owns the commit
    assert db.query(RiskAssessment).count() == 0


def test_save_assessment_commit_true_persists(db, make_user):
    cid = _customer_id(make_user)
    AIRiskService.save_assessment(db, cid, None, RiskResult(
        0.2, "LOW", "rules-0.1"), commit=True)
    db.rollback()
    row = db.query(RiskAssessment).one()
    assert (row.customer_id, float(row.risk_score), row.risk_level.value,
            row.model_version) == (cid, 0.2, "LOW", "rules-0.1")


def test_get_model_uses_settings_path_and_mode_and_is_cached():
    from app.ai.model import get_model

    model = get_model()
    # app/ml/fraud_detection_model.pkl, RISK_MODEL_MODE=hybrid
    assert model.version == "hybrid-1.0.0"
    assert get_model() is model


def test_services_use_the_shared_model_loader():
    from app.ai.model import get_model
    from app.services.transaction_service import risk_service

    assert risk_service._model is get_model()
