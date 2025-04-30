# streamlit-cashflow-forecast

[![Deploy](https://static.streamlit.io/badges/streamlit_badge.svg)](https://share.streamlit.io/<YOUR_GITHUB_USERNAME>/<REPO_NAME>/main/src/ui/app.py)

## Description
A Streamlit app that automates cash-flow forecasting and payables management.

## Features
- Database schema for suppliers, creditors, rule changes, payment plans, and forecasts.
- ETL pipeline for bank statements and creditors-aging data.
- Monthly incremental loads via APScheduler.
- Forecasting using Prophet.
- Natural-language rule engine.
- Payment-plan generation and editing.
- Interactive Streamlit UI.

## Local Development
1. Clone the repository: `git clone https://github.com/<YOUR_GITHUB_USERNAME>/<REPO_NAME>.git`
2. Change directory: `cd <REPO_NAME>`
3. Install dependencies: `pip install -r requirements.txt`
4. Initialize the database: see Alembic migrations.
5. Run locally: `streamlit run src/ui/app.py`

## Docker Compose
Start services: `docker-compose up -d`  
Access the app at [http://localhost:8501](http://localhost:8501).

## Streamlit Community Cloud Deployment
Use the badge above to deploy.  
Ensure the following secrets are set in your Streamlit Cloud app:  
- `DATABASE_URL` pointing to your Postgres database URL.  
- `CREDITORS_AGING_CSV` path or link to your creditors-aging CSV (optional).  
The `.streamlit/config.toml` file is included for headless mode.

## Environment Variables
- `DATABASE_URL`  
- `CREDITORS_AGING_CSV`

## License
MIT License