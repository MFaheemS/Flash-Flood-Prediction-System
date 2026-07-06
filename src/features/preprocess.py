import pandas as pd
from sklearn.model_selection import train_test_split


def clean_data(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    # Only require the model's actual inputs to be non-null — metadata
    # columns like `district`/`date` are legitimately empty for randomly
    # sampled negative examples and shouldn't cause those rows to be
    # dropped.
    target = config["data"]["target_column"]
    feature_cols = config["features"]["numeric"] + config["features"]["categorical"]
    df = df.dropna(subset=feature_cols + [target])
    df = df.drop_duplicates()
    return df


def split_features_target(df: pd.DataFrame, config: dict):
    target = config["data"]["target_column"]
    feature_cols = config["features"]["numeric"] + config["features"]["categorical"]
    X = df[feature_cols]
    y = df[target]
    return X, y


def train_test_split_data(X, y, config: dict):
    return train_test_split(
        X,
        y,
        test_size=config["data"]["test_size"],
        random_state=config["data"]["random_state"],
        stratify=y,
    )
