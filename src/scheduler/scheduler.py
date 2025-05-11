"""Scheduler using APScheduler to trigger monthly delta ETL job."""

import os
import time

from apscheduler.schedulers.background import BackgroundScheduler
from prometheus_client import start_http_server

from src.logging_config import get_logger
from src.metrics import measure_duration, delta_job_duration_seconds
from src.db.session import get_db_session
from src.etl.etl import ingest_creditors_aging

logger = get_logger(__name__)


@measure_duration(delta_job_duration_seconds)
def delta_job():
    """Job that ingests creditors-aging delta data.

    Reads the CREDITORS_AGING_CSV environment variable to locate the CSV file,
    ingests data via ingest_creditors_aging, and logs inserted and updated counts.

    Returns:
        None
    """
    # Get CSV path from environment variable
    path = os.getenv("CREDITORS_AGING_CSV")
    if not path:
        logger.error("Environment variable CREDITORS_AGING_CSV not set")
        return

    # Check if file exists
    if not os.path.exists(path):
        logger.error(f"Creditors aging CSV file not found at path: {path}")
        return

    # Process the file
    with get_db_session() as db:
        try:
            inserted, updated = ingest_creditors_aging(db, path)
            logger.info(f"Delta job completed: inserted={inserted}, updated={updated}")
        except Exception as e:
            logger.exception(f"Delta job failed: {e}")
            # No need to rollback as the context manager handles it


def start_scheduler():
    """Start the APScheduler to run delta_job monthly.

    Schedules delta_job to run on the 1st of each month at midnight UTC,
    starts the scheduler process, and keeps the application alive.

    Returns:
        None
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(delta_job, "cron", day=1, hour=0, minute=0)
    scheduler.start()
    logger.info(f"Scheduler started. Next runs: {scheduler.get_jobs()}")
    try:
        # Keep the scheduler alive
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    start_http_server(8000)
    start_scheduler()
