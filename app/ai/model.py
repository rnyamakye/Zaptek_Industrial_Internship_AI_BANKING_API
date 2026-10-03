from pathlib import Path
import joblib


MODEL_PATH = Path("app/models/risk_model.pkl")

_model = None


def load_model():
    global _model

    if _model is not None:
        return _model

    try:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"AI model not found at: {MODEL_PATH}"
            )

        _model = joblib.load(MODEL_PATH)

        return _model

    except Exception as exc:
        raise RuntimeError(
            f"Failed to load AI risk model: {exc}"
        ) from exc


def get_model():
    return load_model()
