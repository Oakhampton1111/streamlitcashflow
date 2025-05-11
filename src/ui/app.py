"""Streamlit UI for Cashflow Forecasting.

This module implements the Streamlit-based user interface for the Cashflow Forecast application.
It provides UI sections for:
- Data ingestion via CSV uploads.
- Supplier management.
- Aging creditors table display.
- Rule editor and application.
- Forecasting and visualization.
- Payment plan generation and export.
"""

import streamlit as st
import pandas as pd
import altair as alt
import requests

from src.logging_config import get_logger
from src.metrics import measure_duration, ui_request_duration_seconds
from src.db.session import get_db_session
from src.db import models
from src.etl.etl import run_etl
from src.rules.rules import apply_pending_rules
from src.forecast.forecast import run_forecast, get_historical_net_cash
from src.payment.payment import generate_payment_plan, save_draft_payment_plans

logger = get_logger(__name__)

@st.cache_data
def fetch_metrics():
    resp = requests.get("http://localhost:8000/metrics")
    resp.raise_for_status()
    return resp.text

def parse_metrics(text):
    rows = []
    for line in text.splitlines():
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) == 2:
            name_labels, value = parts
            timestamp = None
        elif len(parts) == 3:
            name_labels, value, timestamp = parts
        else:
            continue
        if '{' in name_labels:
            metric, labels_str = name_labels.split('{', 1)
            labels_str = labels_str.rstrip('}')
            labels = {}
            for pair in labels_str.split(','):
                k, v = pair.split('=', 1)
                labels[k] = v.strip('"')
        else:
            metric = name_labels
            labels = {}
        try:
            ts = pd.to_datetime(int(timestamp), unit='s') if timestamp else None
        except:
            ts = None
        rows.append({'metric': metric, 'labels': labels, 'value': float(value), 'timestamp': ts})
    return pd.DataFrame(rows)


@measure_duration(ui_request_duration_seconds)
def main():
    """Main Streamlit app entry point for Cashflow Forecasting UI.

    Sets up UI sections for data ingestion, supplier management, aging creditors display,
    rule application, forecasting, and payment plan generation. Decorated to record UI request duration.
    """
    st.title("Cashflow Forecasting")

    view = st.sidebar.selectbox("View", ["Main App", "Performance Dashboard"])
    if view == "Performance Dashboard":
        try:
            metrics_text = fetch_metrics()
        except Exception as e:
            st.error(f"Metrics endpoint unreachable: {e}")
            return
        df = parse_metrics(metrics_text)
        metric_names = df["metric"].unique().tolist()
        selected_metric = st.selectbox("Select metric", metric_names)
        metric_df = df[df["metric"] == selected_metric].sort_values("timestamp")
        # Time series chart
        chart_df = metric_df.set_index("timestamp")["value"]
        st.line_chart(chart_df)
        # Summary table of latest values
        metric_df['labels_str'] = metric_df['labels'].astype(str)
        latest = metric_df.sort_values("timestamp").drop_duplicates("labels_str", keep="last")
        latest = latest.rename(columns={"labels_str": "labels"})
        st.dataframe(latest[["labels", "value", "timestamp"]])
        return

    # Data Ingestion
    with st.expander("Data Ingestion"):
        bank_files = st.file_uploader(
            "Upload Bank Statement CSVs", type=["csv"], accept_multiple_files=True
        )
        aging_file = st.file_uploader("Upload Creditors-Aging CSV", type=["csv"])
        if st.button("Run ETL"):
            try:
                run_etl(bank_files, aging_file)
                st.success("ETL completed.")
            except Exception as e:
                logger.exception("UI error", exc_info=e)
                st.error(f"ETL failed: {e}")

    # Supplier Manager
    with st.expander("Supplier Manager"):
        with get_db_session() as db:
            # Fetch all suppliers
            suppliers = db.query(models.Supplier).all()

            # Convert to DataFrame for display
            sup_df = pd.DataFrame(
                [
                    {
                        "id": s.id,
                        "name": s.name,
                        "type": s.type,
                        "max_delay_days": s.max_delay_days,
                    }
                    for s in suppliers
                ]
            )

        # Display editable table
        edited_suppliers = st.data_editor(sup_df, num_rows="dynamic")

        # Save changes when button is clicked
        if st.button("Save Suppliers"):
            try:
                with get_db_session() as db:
                    for row in edited_suppliers.to_dict(orient="records"):
                        # Validate row data
                        if "id" not in row or "type" not in row or "max_delay_days" not in row:
                            logger.warning(f"Skipping invalid supplier row: {row}")
                            continue

                        # Get supplier by ID
                        sup = db.query(models.Supplier).get(row["id"])
                        if not sup:
                            logger.warning(f"Supplier with ID {row['id']} not found")
                            continue

                        # Update fields
                        sup.type = row["type"]
                        try:
                            sup.max_delay_days = int(row["max_delay_days"])
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid max_delay_days value: {row['max_delay_days']}")
                            continue

                st.success("Suppliers updated.")
            except Exception as e:
                logger.exception("Error updating suppliers", exc_info=e)
                st.error(f"Update failed: {e}")

    # Aging Creditors
    with st.expander("Aging Creditors"):
        with get_db_session() as db:
            # Fetch all creditors
            creditors = db.query(models.Creditor).all()

            # Convert to DataFrame for display
            cred_df = pd.DataFrame(
                [
                    {
                        "id": c.id,
                        "supplier_id": c.supplier_id,
                        "invoice_date": c.invoice_date,
                        "due_date": c.due_date,
                        "amount": float(c.amount),
                        "aging_days": c.aging_days,
                        "status": c.status,
                    }
                    for c in creditors
                ]
            )

        # Define conditional row coloring function
        def color_rows(row):
            if row["aging_days"] > 30:
                return ["background-color: red"] * len(row)
            elif row["aging_days"] > 15:
                return ["background-color: yellow"] * len(row)
            else:
                return [""] * len(row)

        # Display styled dataframe with color coding
        st.subheader("Aging Creditors Table")
        st.dataframe(cred_df.style.apply(color_rows, axis=1))

    # Rule Editor
    with st.expander("Rule Editor"):
        if st.button("Apply Rules"):
            try:
                applied, failed = apply_pending_rules()
                st.success(f"Rules applied: {applied}, failed: {failed}")
            except Exception as e:
                logger.exception("UI error", exc_info=e)
                st.error(f"Rule application failed: {e}")

    # Forecasting
    with st.expander("Forecasting"):
        horizon = st.number_input("Forecast horizon days", min_value=1, value=14)
        if st.button("Run Forecast"):
            try:
                run_forecast(horizon)
                st.success("Forecast generated.")
            except Exception as e:
                logger.exception("UI error", exc_info=e)
                st.error(f"Forecast failed: {e}")
        # Display chart and table
        if st.button("Show Forecast"):
            try:
                with get_db_session() as db:
                    # Get historical cash data
                    hist_df = get_historical_net_cash(db)

                    # Get latest forecast
                    latest = (
                        db.query(models.Forecast)
                        .order_by(models.Forecast.run_date.desc())
                        .first()
                    )

                    if not latest:
                        st.warning("No forecast data available. Please run a forecast first.")
                        return

                    # Process forecast data
                    forecast_data = latest.forecast_json
                    if not forecast_data:
                        st.warning("Empty forecast data in latest forecast.")
                        return

                    # Convert to DataFrame
                    fc_df = pd.DataFrame(forecast_data)
                    fc_df["ds"] = pd.to_datetime(fc_df["ds"])

                    # Combine historical and forecast data
                    chart_df = pd.concat(
                        [
                            hist_df.rename(columns={"ds": "ds", "y": "y"}),
                            fc_df.rename(columns={"ds": "ds", "yhat": "y"}),
                        ]
                    )

                    # Create and display chart
                    chart = (
                        alt.Chart(chart_df)
                        .mark_line()
                        .encode(
                            x=alt.X("ds:T", title="Date"),
                            y=alt.Y("y:Q", title="Cash Position"),
                            color=alt.value("steelblue")
                        )
                        .properties(title="Cash Flow Forecast")
                    )
                    st.altair_chart(chart, use_container_width=True)

                    # Display forecast data table
                    st.subheader("Forecast Data")
                    st.dataframe(fc_df)

            except Exception as e:
                logger.exception("UI error", exc_info=e)
                st.error(f"Display failed: {e}")

    # Payment Plans
    with st.expander("Payment Plans"):
        if st.button("Generate Draft Plans"):
            try:
                plans = generate_payment_plan()
                st.session_state["plans"] = plans
                st.success("Draft plans generated.")
            except Exception as e:
                logger.exception("UI error", exc_info=e)
                st.error(f"Generation failed: {e}")
        if "plans" in st.session_state:
            plans_df = pd.DataFrame(st.session_state["plans"])
            edited_plans = st.data_editor(plans_df, num_rows="dynamic")
            if st.button("Save Plans"):
                try:
                    with get_db_session() as db:
                        # Convert edited plans to records
                        plan_records = edited_plans.to_dict(orient="records")

                        # Save plans
                        count = save_draft_payment_plans(db, plan_records)
                        st.success(f"{count} plans saved.")
                except Exception as e:
                    logger.exception("UI error", exc_info=e)
                    st.error(f"Save failed: {e}")
            csv = pd.DataFrame(st.session_state["plans"]).to_csv(index=False)
            st.download_button(
                "Download CSV", data=csv, file_name="payment_plans.csv", mime="text/csv"
            )


if __name__ == "__main__":
    main()
