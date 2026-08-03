import joblib
import numpy as np
import pandas as pd

from src.data.load_data import load_config


def predict(input_df: pd.DataFrame) -> pd.DataFrame:
    config = load_config()
    model = joblib.load(config["model"]["save_path"])
    feature_cols = config["features"]["numeric"] + config["features"]["categorical"]
    preds = model.predict(input_df[feature_cols])
    proba = model.predict_proba(input_df[feature_cols])[:, 1]
    input_df["cloudburst_prediction"] = preds
    input_df["cloudburst_probability"] = proba
    return input_df


def explain(input_df: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    """
    Attach a human-readable explanation of the top contributing factors
    per row, using SHAP values from the trained XGBoost model.
    """
    config = load_config()
    model = joblib.load(config["model"]["save_path"])
    feature_cols = config["features"]["numeric"] + config["features"]["categorical"]
    X = input_df[feature_cols]

    import shap  # lazy: only the offline explanation path needs it, keeps the API deploy slim

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    reasons = []
    for i in range(len(X)):
        row_shap = shap_values[i]
        top_idx = np.argsort(np.abs(row_shap))[::-1][:top_n]
        parts = []
        for idx in top_idx:
            feature = feature_cols[idx]
            value = X.iloc[i][feature]
            direction = "increased" if row_shap[idx] > 0 else "decreased"
            parts.append(f"{feature}={value:g} {direction} risk")
        reasons.append("; ".join(parts))

    input_df["risk_explanation"] = reasons
    return input_df


if __name__ == "__main__":
    config = load_config()
    sample = pd.read_csv(config["data"]["raw_path"]).sample(5)
    result = predict(sample)
    result = explain(result)
    print(result[["cloudburst_probability", "risk_explanation"]])
