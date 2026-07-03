import joblib
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


if __name__ == "__main__":
    config = load_config()
    sample = pd.read_csv(config["data"]["raw_path"]).sample(5)
    print(predict(sample))
