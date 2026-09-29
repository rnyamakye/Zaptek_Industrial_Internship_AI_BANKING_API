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
