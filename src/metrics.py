"""Prometheus metrics definitions and duration measurement decorator.

This module defines Histogram metrics for various pipeline components and a
decorator to measure function execution durations using these metrics.
"""

from prometheus_client import Histogram

etl_duration_seconds = Histogram("etl_duration_seconds", "Duration of ETL pipeline")
delta_job_duration_seconds = Histogram(
    "delta_job_duration_seconds", "Duration of delta_job execution"
)
forecast_duration_seconds = Histogram(
    "forecast_duration_seconds", "Duration of forecast run"
)
rules_duration_seconds = Histogram(
    "rules_duration_seconds", "Duration of rule parsing/applying"
)
payment_plan_duration_seconds = Histogram(
    "payment_plan_duration_seconds", "Duration of payment plan generation"
)
ui_request_duration_seconds = Histogram(
    "ui_request_duration_seconds", "Duration of UI request handling"
)


def measure_duration(metric):
    """Decorator to measure execution duration of a function using the provided Prometheus Histogram metric.

    Args:
        metric (Histogram): Prometheus Histogram to record execution time.

    Returns:
        Callable: A decorator that wraps a function to measure and record its execution duration.
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            with metric.time():
                return func(*args, **kwargs)

        return wrapper

    return decorator
