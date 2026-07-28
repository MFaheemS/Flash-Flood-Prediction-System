"""
Train a monthly flood classifier on the satellite region-panel dataset
(src/data/build_satellite_dataset.py): real flood labels for 6 Pakistani
regions, 2000-2021, with physical satellite features including snow cover
(NDSI) and vegetation (NDVI).

Because there are only 60 positive region-months, a single train/test split
is too noisy to trust, so performance is reported via stratified 5-fold
cross-validated ROC-AUC. The saved model is a plain XGBClassifier (so SHAP's
TreeExplainer can read it for the factor analysis); we ALSO report the AUC of
a probability-calibrated version, because the raw imbalanced model outputs
systematically high probabilities -- the "high risk everywhere" effect --
which calibration corrects.

Run:
    python -m src.models.train_satellite_model
"""
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score, average_precision_score
from xgboost import XGBClassifier

from src.data.load_data import load_config


def train():
    config = load_config()
    sf = config["satellite_flood"]

    df = pd.read_csv(sf["raw_path"])
    feats = sf["features"]
    X = df[feats]  # XGBoost handles NaN natively; no imputation needed
    y = df[sf["target_column"]].astype(int)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=sf["random_state"])

    # --- honest cross-validated performance (raw model) ---
    raw = XGBClassifier(**sf["model"]["params"], eval_metric="logloss")
    raw_oof = cross_val_predict(raw, X, y, cv=cv, method="predict_proba")[:, 1]
    print(f"Raw model     — CV ROC-AUC: {roc_auc_score(y, raw_oof):.3f} | "
          f"PR-AUC: {average_precision_score(y, raw_oof):.3f} | "
          f"mean p: {raw_oof.mean():.3f} (base rate {y.mean():.3f})")

    # --- calibrated version (addresses systematically-high probabilities) ---
    calibrated = CalibratedClassifierCV(
        XGBClassifier(**sf["model"]["params"], eval_metric="logloss"),
        method="sigmoid", cv=cv,
    )
    cal_oof = cross_val_predict(calibrated, X, y, cv=cv, method="predict_proba")[:, 1]
    print(f"Calibrated    — CV ROC-AUC: {roc_auc_score(y, cal_oof):.3f} | "
          f"PR-AUC: {average_precision_score(y, cal_oof):.3f} | "
          f"mean p: {cal_oof.mean():.3f} (base rate {y.mean():.3f})")

    # Fit final SHAP-compatible model on all data and save.
    final = XGBClassifier(**sf["model"]["params"], eval_metric="logloss")
    final.fit(X, y)
    os.makedirs(os.path.dirname(sf["model"]["save_path"]), exist_ok=True)
    joblib.dump(final, sf["model"]["save_path"])
    print(f"Model saved to {sf['model']['save_path']}")
    return final


if __name__ == "__main__":
    train()
