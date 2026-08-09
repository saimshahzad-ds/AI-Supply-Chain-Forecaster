# src/models/predictor.py
import pandas as pd
import numpy as np
from datetime import timedelta
from xgboost import XGBRegressor
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
from statsmodels.tsa.arima.model import ARIMA
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings("ignore")

from data.data_manager import get_all_sales, get_customer_counts


def get_daily_customer_series():
    records = get_customer_counts()
    if records is None:
        raise ValueError("No customer count data found.")

    df = records.copy() if isinstance(records, pd.DataFrame) else pd.DataFrame(records)

    if df.empty:
        raise ValueError("Customer count table is empty. Please add data via Data Entry.")

    # Use named columns - iloc[:,0] would grab count_id (int) not the date!
    if 'count_date' in df.columns and 'customer_count' in df.columns:
        date_series  = pd.to_datetime(df['count_date'], errors='coerce')
        count_series = pd.to_numeric(df['customer_count'], errors='coerce')
    elif df.shape[1] >= 3:
        date_series  = pd.to_datetime(df.iloc[:, 1], errors='coerce')
        count_series = pd.to_numeric(df.iloc[:, 2], errors='coerce')
    else:
        raise ValueError(f"Unexpected CustomerCount schema: {list(df.columns)}")

    valid_mask = date_series.notna() & count_series.notna()
    if not valid_mask.any():
        raise ValueError("No valid date-count pairs found in CustomerCount table.")

    df_clean = pd.DataFrame({'date': date_series[valid_mask], 'count': count_series[valid_mask]})
    df_clean = df_clean.set_index('date').sort_index()
    df_clean = df_clean.asfreq('D', fill_value=0)

    if len(df_clean) < 3:
        raise ValueError(f"Need at least 3 days of data. Found {len(df_clean)}.")

    return df_clean['count']


def get_daily_sales_per_item():
    sales = get_all_sales()
    if sales is None or (isinstance(sales, pd.DataFrame) and sales.empty):
        return {}

    df = sales.copy() if isinstance(sales, pd.DataFrame) else pd.DataFrame(sales)
    if df.empty or df.shape[1] < 3:
        return {}

    if 'sale_date' in df.columns and 'item_name' in df.columns and 'quantity' in df.columns:
        date_col, item_col, qty_col = 'sale_date', 'item_name', 'quantity'
    else:
        date_col, item_col, qty_col = df.columns[0], df.columns[1], df.columns[2]

    try:
        df['_date']      = pd.to_datetime(df[date_col], errors='coerce')
        df['_qty']       = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)
        df['_item_name'] = df[item_col].astype(str)
    except Exception:
        return {}

    df = df.dropna(subset=['_date'])
    if df.empty:
        return {}

    result = {}
    for name, group in df.groupby('_item_name'):
        daily = group.groupby('_date')['_qty'].sum()
        daily = daily.asfreq('D', fill_value=0)
        if not daily.empty:
            result[name] = daily
    return result


def train_arima(series, forecast_days=7):
    if series is None or len(series) < 3:
        return None
    try:
        model_fit = ARIMA(series, order=(5, 1, 0)).fit()
        forecast  = model_fit.forecast(steps=forecast_days)
        if isinstance(forecast, pd.DataFrame):
            forecast = forecast.iloc[:, 0].values
        elif isinstance(forecast, pd.Series):
            forecast = forecast.values
        return np.maximum(forecast, 0)
    except Exception:
        return None


def train_xgboost(series, forecast_days=7):
    if series is None or len(series) < 14:
        return None
    df = pd.DataFrame({'y': series})
    for lag in range(1, 8):
        df[f'lag_{lag}'] = df['y'].shift(lag)
    df.dropna(inplace=True)
    if df.empty:
        return None
    model = XGBRegressor(n_estimators=100, random_state=42)
    model.fit(df.drop('y', axis=1).values, df['y'].values)
    last_vals = df.iloc[-1][[f'lag_{i}' for i in range(1, 8)]].values.reshape(1, -1)
    forecasts = []
    for _ in range(forecast_days):
        pred = model.predict(last_vals)[0]
        forecasts.append(pred)
        last_vals = np.roll(last_vals, -1)
        last_vals[0, -1] = pred
    return np.maximum(forecasts, 0)


def train_lstm(series, forecast_days=7, window=7):
    if series is None or len(series) < window + 10:
        return None
    scaler = StandardScaler()
    scaled = scaler.fit_transform(series.values.reshape(-1, 1)).flatten()
    X, y = [], []
    for i in range(window, len(scaled)):
        X.append(scaled[i - window:i])
        y.append(scaled[i])
    if len(X) == 0:
        return None
    X, y = np.array(X).reshape(-1, window, 1), np.array(y)
    model = Sequential([LSTM(50, activation='relu', input_shape=(window, 1)), Dropout(0.2), Dense(1)])
    model.compile(optimizer='adam', loss='mse')
    model.fit(X, y, epochs=50, batch_size=min(4, len(X)), verbose=0,
              callbacks=[EarlyStopping(monitor='loss', patience=5, verbose=0)])
    last_window = scaled[-window:].reshape(1, window, 1)
    forecasts = []
    for _ in range(forecast_days):
        pred_scaled = model.predict(last_window, verbose=0)[0, 0]
        forecasts.append(pred_scaled)
        last_window = np.append(last_window[0, 1:, 0], pred_scaled).reshape(1, window, 1)
    return np.maximum(scaler.inverse_transform(np.array(forecasts).reshape(-1, 1)).flatten(), 0)


def train_naive(series, forecast_days=7, season=7):
    """Seasonal-naive baseline: forecast = actual value from `season` days earlier
    (i.e. same day last week). Falls back to repeating the last value if there
    isn't a full season of history."""
    if series is None or len(series) < 1:
        return None
    values = list(series.values.astype(float))
    if len(values) < season:
        last_val = values[-1]
        return np.maximum(np.array([last_val] * forecast_days), 0)

    extended = values[:]
    forecasts = []
    for _ in range(forecast_days):
        next_val = extended[-season]
        forecasts.append(next_val)
        extended.append(next_val)
    return np.maximum(np.array(forecasts), 0)


# All four functions share the same (series, forecast_days) signature.
MODEL_FUNCS = {
    "ARIMA":   train_arima,
    "XGBoost": train_xgboost,
    "LSTM":    train_lstm,
    "Naive":   train_naive,
}


def train_test_split_series(series, test_days=7):
    """Hold out the last `test_days` observations as a test set. Returns (train, test)."""
    if series is None or len(series) < test_days + 3:
        raise ValueError(
            f"Need at least {test_days + 3} days of data to hold out "
            f"{test_days} test days (found {0 if series is None else len(series)})."
        )
    train = series.iloc[:-test_days]
    test = series.iloc[-test_days:]
    return train, test


def calculate_error_metrics(actual, predicted):
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if len(actual) == 0 or len(predicted) == 0 or len(actual) != len(predicted):
        return {"MAE": None, "RMSE": None, "MAPE": None}

    errors = actual - predicted
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    denom = np.maximum(np.abs(actual), 1.0)  # avoid divide-by-zero on zero-sales days
    mape = float(np.mean(np.abs(errors) / denom) * 100)

    return {"MAE": round(mae, 3), "RMSE": round(rmse, 3), "MAPE": round(mape, 2)}


def backtest_series(series, model_type, test_days=7, **model_kwargs):
    """Fit on everything except the last `test_days`, forecast that window, score it.
    Returns None if there isn't enough data or the model failed to fit."""
    try:
        train, test = train_test_split_series(series, test_days=test_days)
    except ValueError:
        return None

    fn = MODEL_FUNCS.get(model_type)
    if fn is None:
        raise ValueError(f"Unknown model_type: {model_type}")

    predicted = fn(train, test_days, **model_kwargs)
    if predicted is None:
        return None

    predicted = np.asarray(predicted)[:len(test)]
    actual = test.values[:len(predicted)]
    if len(predicted) == 0 or len(predicted) != len(actual):
        return None

    metrics = calculate_error_metrics(actual, predicted)
    return {
        "model": model_type,
        "test_days": len(actual),
        "actual": actual.tolist(),
        "predicted": np.round(predicted, 2).tolist(),
        **metrics,
    }


def evaluate_models(model_types=("ARIMA", "XGBoost", "LSTM"), test_days=7, include_baseline=True):
    """Backtest each model (plus Naive baseline) for the customer series and every item.
    Returns a DataFrame: [series, model, test_days, MAE, RMSE, MAPE]."""
    rows = []
    models_to_run = list(model_types)
    if include_baseline and "Naive" not in models_to_run:
        models_to_run.append("Naive")

    try:
        customer_series = get_daily_customer_series()
        for model_type in models_to_run:
            result = backtest_series(customer_series, model_type, test_days=test_days)
            if result:
                rows.append({
                    "series": "Customer Count",
                    "model": result["model"],
                    "test_days": result["test_days"],
                    "MAE": result["MAE"],
                    "RMSE": result["RMSE"],
                    "MAPE": result["MAPE"],
                })
    except ValueError:
        pass

    for item, series in get_daily_sales_per_item().items():
        if len(series) < test_days + 3:
            continue
        for model_type in models_to_run:
            result = backtest_series(series, model_type, test_days=test_days)
            if result:
                rows.append({
                    "series": item,
                    "model": result["model"],
                    "test_days": result["test_days"],
                    "MAE": result["MAE"],
                    "RMSE": result["RMSE"],
                    "MAPE": result["MAPE"],
                })

    return pd.DataFrame(rows, columns=["series", "model", "test_days", "MAE", "RMSE", "MAPE"])


def generate_all_predictions(model_type="ARIMA", forecast_days=7):
    try:
        customer_series = get_daily_customer_series()
    except ValueError as e:
        raise ValueError(f"Customer data error: {e}")

    valid_models = ("ARIMA", "XGBoost", "LSTM", "Naive")
    if model_type not in valid_models:
        raise ValueError(f"model_type must be one of: {', '.join(valid_models)}")
    fn = MODEL_FUNCS[model_type]

    cust_forecast = fn(customer_series, forecast_days)

    if cust_forecast is None:
        raise ValueError(
            f"{model_type} could not generate a forecast for {forecast_days} days. "
            "Add more historical data (ARIMA: 3+ days, XGBoost/LSTM: 14+ days, "
            "and generally more history than the forecast horizon itself)."
        )

    item_forecasts = {}
    for item, series in get_daily_sales_per_item().items():
        if len(series) < 7:
            continue
        pred = fn(series, forecast_days)
        if pred is not None:
            item_forecasts[item] = np.round(pred).astype(int).tolist()

    from datetime import date as _date
    last_date = customer_series.index[-1]
    today     = pd.Timestamp(_date.today())
    start     = max(last_date, today)   # never show past dates in forecast
    date_strs = [(start + timedelta(days=i + 1)).strftime('%Y-%m-%d') for i in range(forecast_days)]

    return {
        'dates':             date_strs,
        'customer_forecast': np.round(cust_forecast).astype(int).tolist(),
        'item_forecasts':    item_forecasts,
        'model_used':        model_type
    }


def get_prediction_summary(predictions):
    if not predictions or not predictions.get("customer_forecast"):
        return {}
    total = sum(predictions['customer_forecast'])
    return {
        'total_customers_next_week': total,
        'avg_daily_customers':       round(total / len(predictions['customer_forecast']), 1),
        'items_with_forecast':       len(predictions.get('item_forecasts', {})),
        'model_used':                predictions.get('model_used', 'N/A')
    }