import joblib
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, roc_auc_score

from src.data.load_data import load_config, load_raw_data
from src.features.preprocess import clean_data, split_features_target, train_test_split_data


def train():
    config = load_config()
    df = load_raw_data(config)
    df = clean_data(df, config)
    X, y = split_features_target(df, config)
    X_train, X_test, y_train, y_test = train_test_split_data(X, y, config)

    model = XGBClassifier(**config["model"]["params"], eval_metric="logloss")
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]
    print(classification_report(y_test, preds))
    print("ROC-AUC:", roc_auc_score(y_test, proba))

    joblib.dump(model, config["model"]["save_path"])
    print(f"Model saved to {config['model']['save_path']}")


if __name__ == "__main__":
    train()
