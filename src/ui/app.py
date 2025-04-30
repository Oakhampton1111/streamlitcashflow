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

from src.logging_config import get_logger
from src.metrics import measure_duration, ui_request_duration_seconds
from src.db.session import SessionLocal
from src.db import models
from src.etl.etl import run_etl
from src.rules.rules import apply_pending_rules
from src.forecast.forecast import run_forecast, get_historical_net_cash
from src.payment.payment import generate_payment_plan, save_draft_payment_plans

logger = get_logger(__name__)


@measure_duration(ui_request_duration_seconds)
def main():
    """Main Streamlit app entry point for Cashflow Forecasting UI.

    Sets up UI sections for data ingestion, supplier management, aging creditors display,
    rule application, forecasting, and payment plan generation. Decorated to record UI request duration.
    """
    st.title("Cashflow Forecasting")

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
        db = SessionLocal()
        suppliers = db.query(models.Supplier).all()
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
        edited_suppliers = st.data_editor(sup_df, num_rows="dynamic")
        if st.button("Save Suppliers"):
            try:
                for row in edited_suppliers.to_dict(orient="records"):
                    sup = db.query(models.Supplier).get(row["id"])
                    sup.type = row["type"]
                    sup.max_delay_days = row["max_delay_days"]
                db.commit()
                st.success("Suppliers updated.")
            except Exception as e:
                db.rollback()
                st.error(f"Update failed: {e}")
        db.close()

    # Aging Creditors
    with st.expander("Aging Creditors"):
        db = SessionLocal()
        creditors = db.query(models.Creditor).all()
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
        st.data_editor(cred_df, num_rows="dynamic")

        # conditional row coloring
        def color_rows(row):
            if row["aging_days"] > 30:
                return ["background-color: red"] * len(row)
            elif row["aging_days"] > 15:
                return ["background-color: yellow"] * len(row)
            else:
                return [""] * len(row)

        st.dataframe(cred_df.style.apply(color_rows, axis=1))
        db.close()

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
                db = SessionLocal()
                hist_df = get_historical_net_cash(db)
                latest = (
                    db.query(models.Forecast)
                    .order_by(models.Forecast.run_date.desc())
                    .first()
                )
                forecast_data = latest.forecast_json
                fc_df = pd.DataFrame(forecast_data)
                fc_df["ds"] = pd.to_datetime(fc_df["ds"])
                chart_df = pd.concat(
                    [
                        hist_df.rename(columns={"ds": "ds", "y": "y"}),
                        fc_df.rename(columns={"ds": "ds", "yhat": "y"}),
                    ]
                )
                chart = (
                    alt.Chart(chart_df)
                    .mark_line()
                    .encode(x="ds:T", y="y:Q", color=alt.value("steelblue"))
                )
                st.altair_chart(chart, use_container_width=True)
                st.dataframe(fc_df)
                db.close()
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
                    db = SessionLocal()
                    count = save_draft_payment_plans(
                        db, edited_plans.to_dict(orient="records")
                    )
                    st.success(f"{count} plans saved.")
                    db.close()
                except Exception as e:
                    logger.exception("UI error", exc_info=e)
                    st.error(f"Save failed: {e}")
            csv = pd.DataFrame(st.session_state["plans"]).to_csv(index=False)
            st.download_button(
                "Download CSV", data=csv, file_name="payment_plans.csv", mime="text/csv"
            )


if __name__ == "__main__":
    main()
