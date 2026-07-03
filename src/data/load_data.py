import pandas as pd
import yaml


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def load_raw_data(config: dict) -> pd.DataFrame:
    return pd.read_csv(config["data"]["raw_path"])


if __name__ == "__main__":
    cfg = load_config()
    df = load_raw_data(cfg)
    print(df.head())
    print(df.shape)
