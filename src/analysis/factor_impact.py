"""
Quantify how much each input factor moves flash-flood risk, using SHAP
values from a trained model. Works with either dataset in this project:

  - "cloudburst" (default): the Pakistan-specific binary classifier
    (src/models/train_model.py), 14 engineered features, 600 rows.
  - "flood_factors": the Kaggle Flood Prediction Dataset regressor
    (src/models/train_flood_factors.py), 20 named factors, up to 50k rows.
    Requires data/raw/flood_factors.csv -- see that script's docstring.

Produces, per dataset:
  - data/processed/{dataset}_factor_impact.csv — one row per feature,
    ranked by mean absolute SHAP impact, with the average direction
  - reports/{dataset}_factor_impact.png — a horizontal bar chart

Run:
    python -m src.analysis.factor_impact --dataset cloudburst
    python -m src.analysis.factor_impact --dataset flood_factors
"""
import argparse
import os

import joblib
import numpy as np
import pandas as pd
import shap

from src.data.load_data import load_config

# Validated colorblind-safe categorical pair (dataviz skill palette):
# risk-increasing vs risk-decreasing factors.
COLOR_INCREASE = "#DC5B53"  # warm red — pushes risk up
COLOR_DECREASE = "#3B82C4"  # cool blue — pushes risk down

MAX_ROWS_FOR_SHAP = 5000  # sample large datasets for speed; SHAP scales with rows


def _load_cloudburst():
    config = load_config()
    model = joblib.load(config["model"]["save_path"])
    feature_cols = config["features"]["numeric"] + config["features"]["categorical"]
    df = pd.read_csv(config["data"]["raw_path"])
    return model, df, feature_cols, "flash-flood risk"


def _load_flood_factors():
    config = load_config()
    fc = config["flood_factors"]
    if not os.path.exists(fc["raw_path"]):
        raise FileNotFoundError(
            f"{fc['raw_path']} not found. Download train.csv from "
            "https://www.kaggle.com/competitions/playground-series-s4e5/data "
            f"and save it to {fc['raw_path']}, then run "
            "`python -m src.models.train_flood_factors` first."
        )
    model = joblib.load(fc["model"]["save_path"])
    df = pd.read_csv(fc["raw_path"]).drop(columns=["id"], errors="ignore")
    return model, df, fc["features"], "flood probability"


def _load_global_flood():
    config = load_config()
    gf = config["global_flood"]
    if not os.path.exists(gf["raw_path"]):
        raise FileNotFoundError(
            f"{gf['raw_path']} not found. Run `python -m src.data.global_events`, "
            "`python -m src.data.build_global_dataset`, "
            "`python -m src.data.enrich_global_dataset`, and "
            "`python -m src.models.train_global_model` first."
        )
    model = joblib.load(gf["model"]["save_path"])
    df = pd.read_csv(gf["raw_path"])
    return model, df, gf["features"], "global flash-flood risk"


def _load_satellite_flood():
    config = load_config()
    sf = config["satellite_flood"]
    if not os.path.exists(sf["model"]["save_path"]):
        raise FileNotFoundError(
            f"{sf['model']['save_path']} not found. Run "
            "`python -m src.data.build_satellite_dataset` then "
            "`python -m src.models.train_satellite_model` first."
        )
    model = joblib.load(sf["model"]["save_path"])
    df = pd.read_csv(sf["raw_path"])
    return model, df, sf["features"], "monthly flood risk (satellite)"


def _load_district_flood():
    config = load_config()
    dc = config["district_flood"]
    if not os.path.exists(dc["model"]["save_path"]):
        raise FileNotFoundError(
            f"{dc['model']['save_path']} not found. Run "
            "`python -m src.data.build_district_dataset` then "
            "`python -m src.models.train_district_model` first."
        )
    model = joblib.load(dc["model"]["save_path"])
    df = pd.read_csv(dc["raw_path"])
    return model, df, dc["features"], "district monthly flood risk"


LOADERS = {
    "cloudburst": _load_cloudburst,
    "flood_factors": _load_flood_factors,
    "global_flood": _load_global_flood,
    "satellite_flood": _load_satellite_flood,
    "district_flood": _load_district_flood,
}


def compute_factor_impact(dataset: str = "cloudburst") -> tuple[pd.DataFrame, str]:
    model, df, feature_cols, label = LOADERS[dataset]()
    X = df[feature_cols].dropna()
    if len(X) > MAX_ROWS_FOR_SHAP:
        X = X.sample(MAX_ROWS_FOR_SHAP, random_state=42)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    # Binary classifiers return shap_values as-is (n_samples, n_features);
    # this stays a single array for both XGBClassifier and XGBRegressor here.

    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    # Correlation between each feature's value and its own SHAP value tells us
    # the *direction*: positive correlation = higher values increase risk.
    directions = []
    for i, col in enumerate(feature_cols):
        corr = np.corrcoef(X[col].values, shap_values[:, i])[0, 1]
        directions.append("increases risk" if corr > 0 else "decreases risk")

    result = pd.DataFrame({
        "feature": feature_cols,
        "mean_abs_shap_impact": mean_abs_shap,
        "direction": directions,
    })
    result["relative_importance_pct"] = 100 * result["mean_abs_shap_impact"] / result["mean_abs_shap_impact"].sum()
    result = result.sort_values("mean_abs_shap_impact", ascending=False).reset_index(drop=True)
    result.insert(0, "rank", result.index + 1)
    return result, label


def save_csv(result: pd.DataFrame, out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    result.to_csv(out_path, index=False)
    print(f"Saved {out_path}")


def save_chart(result: pd.DataFrame, out_path: str, label: str):
    import matplotlib.pyplot as plt  # lazy: not needed by the API, keeps the deploy slim
    from matplotlib.patches import Patch

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plot_df = result.sort_values("mean_abs_shap_impact", ascending=True)
    colors = [COLOR_INCREASE if d == "increases risk" else COLOR_DECREASE for d in plot_df["direction"]]

    fig, ax = plt.subplots(figsize=(9, max(4, 0.42 * len(plot_df) + 1.5)), dpi=150)
    bars = ax.barh(plot_df["feature"], plot_df["mean_abs_shap_impact"], color=colors, height=0.65)

    for bar, pct in zip(bars, plot_df["relative_importance_pct"]):
        ax.text(bar.get_width() + plot_df["mean_abs_shap_impact"].max() * 0.01,
                 bar.get_y() + bar.get_height() / 2, f"{pct:.1f}%",
                 va="center", fontsize=9, color="#555555")

    ax.set_xlabel(f"Mean |SHAP value| — average impact on predicted {label}")
    ax.set_title(f"What drives {label} predictions", fontsize=13, fontweight="bold", pad=14)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color="#e6e6e6", linewidth=0.8)

    legend_handles = [
        Patch(facecolor=COLOR_INCREASE, label="Higher value → increases risk"),
        Patch(facecolor=COLOR_DECREASE, label="Higher value → decreases risk"),
    ]
    ax.legend(handles=legend_handles, loc="lower right", frameon=False, fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["cloudburst", "flood_factors", "global_flood", "satellite_flood", "district_flood"], default="cloudburst")
    args = parser.parse_args()

    result, label = compute_factor_impact(args.dataset)
    save_csv(result, f"data/processed/{args.dataset}_factor_impact.csv")
    save_chart(result, f"reports/{args.dataset}_factor_impact.png", label)
    print(result.to_string(index=False))
