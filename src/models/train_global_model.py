"""
Train a binary classifier on the global rain-driven flood dataset (600
events across ~400 countries + negatives) -- see config.yaml:
global_flood and src/data/build_global_dataset.py /
src/data/enrich_global_dataset.py for how it's built.

Run:
    python -m src.models.train_global_model
"""
import os

import joblib
import pandas as pd
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from src.data.load_data import load_config


def train():
    config = load_config()
    gf = config["global_flood"]

    df = pd.read_csv(gf["raw_path"])
    df = df.dropna(subset=gf["features"] + [gf["target_column"]]).drop_duplicates()

    X = df[gf["features"]]
    y = df[gf["target_column"]]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=gf["test_size"], random_state=gf["random_state"], stratify=y
    )

    model = XGBClassifier(**gf["model"]["params"], eval_metric="logloss")
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]
    print(classification_report(y_test, preds))
    print("ROC-AUC:", roc_auc_score(y_test, proba))

    os.makedirs(os.path.dirname(gf["model"]["save_path"]), exist_ok=True)
    joblib.dump(model, gf["model"]["save_path"])
    print(f"Model saved to {gf['model']['save_path']}")
    return model


if __name__ == "__main__":
    train()
