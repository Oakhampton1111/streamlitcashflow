"""Prophet-based forecasting module."""

from datetime import datetime

import pandas as pd
from prophet import Prophet
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from src.db.session import SessionLocal
from src.db.models import Creditor, Forecast
from src.logging_config import get_logger
from src.metrics import measure_duration, forecast_duration_seconds

logger = get_logger(__name__)


def get_historical_net_cash(db: Session) -> pd.DataFrame:
    """Query creditors table and compute daily net cash (credits minus payments) grouped by invoice_date.

    Args:
        db (Session): SQLAlchemy Session object.

    Returns:
        pd.DataFrame: DataFrame with columns ['ds', 'y'] sorted by date.
    """
    query = (
        db.query(
            Creditor.invoice_date.label("ds"),
            (
                func.sum(Creditor.amount).filter(Creditor.status == "credit")
                - func.sum(Creditor.amount).filter(Creditor.status == "payment")
            ).label("y"),
        )
        .group_by(Creditor.invoice_date)
        .all()
    )
    df = pd.DataFrame(query, columns=["ds", "y"])
    df["ds"] = pd.to_datetime(df["ds"]).dt.date
    df["y"] = df["y"].astype(float)
    return df.sort_values("ds")


def train_and_forecast(df: pd.DataFrame, periods: int = 12) -> pd.DataFrame:
    """Train a Prophet model on historical cashflow in df and forecast future periods.

    Args:
        df (pd.DataFrame): Historical cashflow with columns ['ds', 'y'].
        periods (int): Number of periods to forecast (default: 12).

    Returns:
        pd.DataFrame: DataFrame with columns ['ds', 'yhat'].
    """
    model = Prophet()
    model.fit(df)
    future = model.make_future_dataframe(periods=periods, freq="M")
    forecast = model.predict(future)
    return forecast[["ds", "yhat"]]


def save_forecast(df_forecast: pd.DataFrame) -> None:
    """Persist forecast results into the forecasts table.

    Args:
        df_forecast (pd.DataFrame): Forecast DataFrame with 'ds' and 'yhat'.

    Returns:
        None
    """
    db: Session = SessionLocal()
    try:
        for row in df_forecast.itertuples(index=False):
            record = Forecast(period_start=row.ds, period_end=row.ds, value=row.yhat)
            db.add(record)
        db.commit()
    finally:
        db.close()


@measure_duration(forecast_duration_seconds)
def run_forecast(horizon_days: int = 14) -> list:
    """Load historical data, generate forecasts for the next horizon_days, persist results, and return a list of forecasts.

    Args:
        horizon_days (int): Forecast horizon in days (default: 14).

    Returns:
        list[dict]: List of forecast dictionaries with keys 'ds' and 'yhat'.
    """
    db: Session = SessionLocal()
    try:
        hist_df = get_historical_net_cash(db)
        model = Prophet()
        model.fit(hist_df)
        future = model.make_future_dataframe(periods=horizon_days, freq="D")
        forecast_df = model.predict(future)[["ds", "yhat"]].copy()
        # filter for future days beyond last historical
        last_hist = hist_df["ds"].max()
        forecast_df = forecast_df[forecast_df["ds"] > pd.to_datetime(last_hist)]
        # daily forecasts up to day 14
        daily_count = min(horizon_days, 14)
        daily = forecast_df.head(daily_count)
        results = [
            {"ds": row.ds.strftime("%Y-%m-%d"), "yhat": float(row.yhat)}
            for row in daily.itertuples(index=False)
        ]
        # weekly aggregation for remaining days
        if horizon_days > 14:
            weekly_df = forecast_df.iloc[14:]
            weekly_df["week_start"] = weekly_df["ds"] - pd.to_timedelta(
                weekly_df["ds"].dt.weekday, unit="D"
            )
            weekly_agg = weekly_df.groupby("week_start")["yhat"].sum().reset_index()
            for row in weekly_agg.itertuples(index=False):
                results.append(
                    {"ds": row.week_start.strftime("%Y-%m-%d"), "yhat": float(row.yhat)}
                )
        # persist to DB
        try:
            record = Forecast(
                run_date=datetime.now(),
                horizon_days=horizon_days,
                forecast_json=results,
            )
            db.add(record)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return results
    finally:
        db.close()
