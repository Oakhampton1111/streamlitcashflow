# Cashflow Forecast Streamlit App

[![Deploy](https://static.streamlit.io/badges/streamlit_badge.svg)](https://share.streamlit.io/<YOUR_GITHUB_USERNAME>/<REPO_NAME>/main/src/ui/app.py)

## Description
A Streamlit app that automates cash-flow forecasting and payables management. This application helps businesses predict future cash positions and manage payment schedules efficiently.

## Features
- Database schema for suppliers, creditors, rule changes, payment plans, and forecasts
- ETL pipeline for bank statements and creditors-aging data with robust error handling
- Monthly incremental loads via APScheduler
- Forecasting using Prophet with configurable time horizons
- Natural-language rule engine for supplier payment policies
- Payment-plan generation and editing with deficit detection
- Interactive Streamlit UI with data visualization
- Prometheus metrics for performance monitoring
- Comprehensive logging with JSON output

## Architecture
The application follows a modular architecture:
- **ETL Module**: Data ingestion and transformation
- **Forecast Module**: Time-series forecasting using Prophet
- **Rules Module**: Natural language rule processing
- **Payment Module**: Payment plan generation and management
- **UI Module**: Streamlit-based user interface
- **Scheduler**: Background job processing

## Local Development
1. Clone the repository: `git clone https://github.com/<YOUR_GITHUB_USERNAME>/<REPO_NAME>.git`
2. Change directory: `cd <REPO_NAME>`
3. Install dependencies: `pip install -r requirements.txt`
4. Initialize the database: `alembic upgrade head`
5. Run tests: `python run_tests.py`
6. Run locally: `streamlit run src/ui/app.py`

## Docker Compose
Start services: `docker-compose up -d`
Access the app at [http://localhost:8501](http://localhost:8501).
Metrics are available at [http://localhost:8000/metrics](http://localhost:8000/metrics).

## Testing
The application includes unit tests for all major components:
- Run all tests: `python run_tests.py`
- Run specific module tests: `python -m unittest tests/forecast/test_forecast.py`

## Database Migrations
Database migrations are managed with Alembic:
- Initialize database: `alembic upgrade head`
- Create new migration: `alembic revision -m "description" --autogenerate`
- Apply migrations: `alembic upgrade head`

## Environment Variables
- `DATABASE_URL`: Database connection string (default: `sqlite:///./data.db`)
- `CREDITORS_AGING_CSV`: Path to creditors aging CSV file for scheduled imports
- `LOG_LEVEL`: Logging level (default: `INFO`)

## Recent Improvements
- Added robust database session management with context managers
- Fixed inconsistencies in forecast frequency handling
- Improved error handling in ETL processes
- Enhanced payment plan calculation logic
- Added comprehensive unit tests
- Fixed UI issues with duplicate data display
- Added database migrations
- Improved logging and error reporting

## License
MIT License