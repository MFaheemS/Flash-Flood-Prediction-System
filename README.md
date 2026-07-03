# Cloud Burst Prediction

Predicts the likelihood of a cloud burst event from meteorological factors
(temperature, humidity, pressure, wind speed, rainfall, dew point, cloud cover)
using a trained ML model.

## Tech Stack

- Python 3.11
- pandas / numpy — data handling
- scikit-learn — preprocessing, splitting, metrics
- XGBoost — baseline gradient-boosted classifier
- TensorFlow/Keras — optional deep model for sequential weather data
- matplotlib / seaborn — EDA and visualization
- Jupyter — exploratory notebooks
- FastAPI + uvicorn — optional serving API
- PyYAML — config management

## Project Structure

```
data/
  raw/            raw datasets
  processed/       cleaned datasets
notebooks/         exploratory analysis
src/
  data/            loading utilities
  features/        cleaning / feature engineering
  models/          training and inference
  visualization/   plotting helpers
models/            saved trained models
reports/           figures, evaluation reports
tests/             unit tests
config.yaml        paths, feature list, hyperparameters
```

## Setup

```
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

## Usage

1. Place your dataset at `data/raw/cloudburst_dataset.csv` (update path in `config.yaml` if different).
2. Train:
   ```
   python -m src.models.train_model
   ```
3. Predict on new data:
   ```
   python -m src.models.predict
   ```
