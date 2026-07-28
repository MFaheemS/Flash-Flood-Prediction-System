"""
Train the district-level monthly flood classifier (config.yaml:
district_flood) on the GEE satellite panel + event-derived labels.

Same honest protocol as the province model: stratified 5-fold CV ROC-AUC /
PR-AUC (a single split is too noisy at 126 positives), plus a
probability-calibrated version to show the raw imbalanced model reads high.
The saved model is a plain XGBClassifier so SHAP can read it.

Run:
    python -m src.models.train_district_model
"""
import os

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score, average_precision_score
from xgboost import XGBClassifier

from src.data.load_data import load_config


def train():
    config = load_config()
    dc = config["district_flood"]

    df = pd.read_csv(dc["raw_path"])
    feats = dc["features"]
    X = df[feats]                       # XGBoost handles NaN natively
    y = df[dc["target_column"]].astype(int)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=dc["random_state"])

    raw = XGBClassifier(**dc["model"]["params"], eval_metric="logloss")
    raw_oof = cross_val_predict(raw, X, y, cv=cv, method="predict_proba")[:, 1]
    print(f"Raw model  — CV ROC-AUC: {roc_auc_score(y, raw_oof):.3f} | "
          f"PR-AUC: {average_precision_score(y, raw_oof):.3f} | "
          f"mean p: {raw_oof.mean():.3f} (base rate {y.mean():.4f})")

    calibrated = CalibratedClassifierCV(
        XGBClassifier(**dc["model"]["params"], eval_metric="logloss"),
        method="sigmoid", cv=cv,
    )
    cal_oof = cross_val_predict(calibrated, X, y, cv=cv, method="predict_proba")[:, 1]
    print(f"Calibrated — CV ROC-AUC: {roc_auc_score(y, cal_oof):.3f} | "
          f"PR-AUC: {average_precision_score(y, cal_oof):.3f} | "
          f"mean p: {cal_oof.mean():.3f} (base rate {y.mean():.4f})")

    final = XGBClassifier(**dc["model"]["params"], eval_metric="logloss")
    final.fit(X, y)
    os.makedirs(os.path.dirname(dc["model"]["save_path"]), exist_ok=True)
    joblib.dump(final, dc["model"]["save_path"])
    print(f"Model saved to {dc['model']['save_path']}")

    # Calibrated model for LIVE scoring (raw XGB reads systematically high;
    # the raw model above is kept for SHAP, which needs the tree model).
    cal_final = CalibratedClassifierCV(
        XGBClassifier(**dc["model"]["params"], eval_metric="logloss"),
        method="sigmoid", cv=cv,
    ).fit(X, y)
    cal_path = dc["model"]["save_path"].replace(".pkl", "_calibrated.pkl")
    joblib.dump(cal_final, cal_path)
    print(f"Calibrated model saved to {cal_path}")
    return final


if __name__ == "__main__":
    train()
