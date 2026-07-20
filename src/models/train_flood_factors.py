"""
Train a regressor on the Kaggle "Flood Prediction Dataset" (Playground
Series S4E5): 20 named human/environmental factors -> continuous
FloodProbability (0-1). This is a *regression* target, unlike the binary
cloudburst_occurred model in train_model.py -- a different dataset, a
different question ("how much does each factor move the probability"
rather than "will a cloudburst happen this hour"), so it gets its own
model file and its own script rather than overloading the existing one.

Requires data/raw/flood_factors.csv (config.yaml: flood_factors.raw_path)
-- download train.csv from
https://www.kaggle.com/competitions/playground-series-s4e5/data and
place it there (drop the `id` column if present; it's dropped
automatically below either way).

Run:
    python -m src.models.train_flood_factors
"""
import os

import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

from src.data.load_data import load_config


def train():
    config = load_config()
    fc = config["flood_factors"]

    if not os.path.exists(fc["raw_path"]):
        raise FileNotFoundError(
            f"{fc['raw_path']} not found. Download train.csv from "
            "https://www.kaggle.com/competitions/playground-series-s4e5/data "
            f"and save it to {fc['raw_path']}."
        )

    df = pd.read_csv(fc["raw_path"])
    df = df.drop(columns=["id"], errors="ignore").dropna()

    X = df[fc["features"]]
    y = df[fc["target_column"]]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=fc["test_size"], random_state=fc["random_state"]
    )

    model = XGBRegressor(**fc["model"]["params"])
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)
    print(f"MAE:  {mae:.4f}")
    print(f"R^2:  {r2:.4f}")

    os.makedirs(os.path.dirname(fc["model"]["save_path"]), exist_ok=True)
    joblib.dump(model, fc["model"]["save_path"])
    print(f"Model saved to {fc['model']['save_path']}")
    return model, (mae, r2)


if __name__ == "__main__":
    train()
