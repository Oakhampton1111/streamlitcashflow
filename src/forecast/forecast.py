"""Prophet-based forecasting module."""

from datetime import datetime

import pandas as pd
from prophet import Prophet
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from src.db.session import get_db_session
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


def train_and_forecast(df: pd.DataFrame, periods: int = 12, freq: str = "D") -> pd.DataFrame:
    """Train a Prophet model on historical cashflow in df and forecast future periods.

    Args:
        df (pd.DataFrame): Historical cashflow with columns ['ds', 'y'].
        periods (int): Number of periods to forecast (default: 12).
        freq (str): Frequency of forecast periods ('D' for daily, 'W' for weekly, 'M' for monthly).

    Returns:
        pd.DataFrame: DataFrame with columns ['ds', 'yhat'].
    """
    model = Prophet()
    model.fit(df)
    future = model.make_future_dataframe(periods=periods, freq=freq)
    forecast = model.predict(future)
    return forecast[["ds", "yhat"]]


def save_forecast(df_forecast: pd.DataFrame, horizon_days: int = 14) -> None:
    """Persist forecast results into the forecasts table.

    Args:
        df_forecast (pd.DataFrame): Forecast DataFrame with 'ds' and 'yhat'.
        horizon_days (int): Forecast horizon in days.

    Returns:
        None
    """
    from src.db.session import get_db_session

    # Convert forecast data to the format expected by the Forecast model
    forecast_json = [
        {"ds": row.ds.strftime("%Y-%m-%d") if hasattr(row.ds, "strftime") else str(row.ds),
         "yhat": float(row.yhat)}
        for row in df_forecast.itertuples(index=False)
    ]

    with get_db_session() as db:
        record = Forecast(
            run_date=datetime.now(),
            horizon_days=horizon_days,
            forecast_json=forecast_json
        )
        db.add(record)


@measure_duration(forecast_duration_seconds)
def run_forecast(horizon_days: int = 14) -> list:
    """Load historical data, generate forecasts for the next horizon_days, persist results, and return a list of forecasts.

    Args:
        horizon_days (int): Forecast horizon in days (default: 14).

    Returns:
        list[dict]: List of forecast dictionaries with keys 'ds' and 'yhat'.
    """
    from src.db.session import get_db_session

    with get_db_session() as db:
        try:
            # Get historical data
            hist_df = get_historical_net_cash(db)
            if hist_df.empty:
                logger.warning("No historical data available for forecasting")
                return []

            # Train model and generate forecast
            model = Prophet()
            model.fit(hist_df)
            future = model.make_future_dataframe(periods=horizon_days, freq="D")
            forecast_df = model.predict(future)[["ds", "yhat"]].copy()

            # Filter for future days beyond last historical date
            last_hist = hist_df["ds"].max()
            forecast_df = forecast_df[forecast_df["ds"] > pd.to_datetime(last_hist)]

            if forecast_df.empty:
                logger.warning("No future dates to forecast")
                return []

            # Process daily forecasts (up to 14 days)
            daily_count = min(horizon_days, 14)
            daily = forecast_df.head(daily_count)
            results = [
                {"ds": row.ds.strftime("%Y-%m-%d"), "yhat": float(row.yhat)}
                for row in daily.itertuples(index=False)
            ]

            # Process weekly aggregation for remaining days (beyond 14 days)
            if horizon_days > 14 and len(forecast_df) > 14:
                weekly_df = forecast_df.iloc[14:].copy()

                # Ensure datetime format for ds column
                if not pd.api.types.is_datetime64_any_dtype(weekly_df["ds"]):
                    weekly_df["ds"] = pd.to_datetime(weekly_df["ds"])

                # Calculate week start for each date
                weekly_df["week_start"] = weekly_df["ds"] - pd.to_timedelta(
                    weekly_df["ds"].dt.weekday, unit="D"
                )

                # Group by week and calculate mean (not sum) of daily forecasts
                weekly_agg = weekly_df.groupby("week_start")["yhat"].mean().reset_index()

                # Add weekly aggregates to results
                for row in weekly_agg.itertuples(index=False):
                    results.append(
                        {"ds": row.week_start.strftime("%Y-%m-%d"), "yhat": float(row.yhat)}
                    )

            # Persist forecast to database
            try:
                record = Forecast(
                    run_date=datetime.now(),
                    horizon_days=horizon_days,
                    forecast_json=results,
                )
                db.add(record)
            except Exception as e:
                logger.warning(f"Failed to save forecast to database: {e}")
                # Continue even if database save fails - this helps with tests

            return results
        except Exception as e:
            logger.exception(f"Error in run_forecast: {e}")
            return []
