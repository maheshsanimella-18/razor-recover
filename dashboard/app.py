import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="RazorRecover AI", layout="wide", page_icon="💳")

API_BASE_URL = "http://127.0.0.1:8000/api"

st.title("💳 RazorRecover — Autonomous AI Revenue Recovery Agent")
st.caption("AI-powered payment diagnosis, bounded safety interventions, and revenue recovery engine.")

st.divider()

# Sidebar controls
st.sidebar.header("Agent Controls")
st.sidebar.markdown("Run the autonomous recovery pipeline on failed transactions stored in the database.")

if st.sidebar.button("🚀 Trigger AI Recovery Batch", type="primary"):
    with st.spinner("Autonomous Agent diagnosing failures and executing bounded recovery..."):
        try:
            res = requests.post(f"{API_BASE_URL}/process-batch")
            if res.status_code == 200:
                data = res.json()
                st.success("Batch processing complete!")
                
                # Display Top-level Key Metrics
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Recovered Revenue", f"₹{data['total_revenue_recovered']:,.2f}")
                col2.metric("Revenue at Risk", f"₹{data['total_amount_at_risk']:,.2f}")
                col3.metric("Recovery Rate", f"{data['recovery_rate_pct']}%")
                col4.metric("Safety Guardrail Stops", data['escalated_or_stopped'])
                
                # Breakdown
                st.subheader("📊 Batch Execution Summary")
                summary_df = pd.DataFrame([{
                    "Total At-Risk Payments": data['at_risk_detected'],
                    "Automated Attempts": data['recovery_attempted'],
                    "Successful Recoveries": data['successfully_recovered'],
                    "Escalated / Blocked": data['escalated_or_stopped']
                }])
                st.dataframe(summary_df, use_container_width=True)
            else:
                st.error(f"Error from backend API: {res.text}")
        except Exception as e:
            st.error(f"Failed to connect to backend server: {e}")

st.divider()

# Live Audit Trail Section
st.subheader("📜 Autonomous Agent Audit Trail")
st.markdown("Real-time log of agent diagnoses, safety bounds, and recovery outcomes.")

try:
    logs_res = requests.get(f"{API_BASE_URL}/audit-logs?limit=50")
    if logs_res.status_code == 200:
        logs_data = logs_res.json()
        if logs_data:
            df_logs = pd.DataFrame(logs_data)
            df_logs = df_logs[['timestamp', 'transaction_id', 'agent_decision', 'reasoning']]
            st.dataframe(df_logs, use_container_width=True)
        else:
            st.info("No audit logs found yet. Click 'Trigger AI Recovery Batch' in the sidebar to run the agent!")
except Exception as e:
    st.warning("Ensure the FastAPI backend is running at http://127.0.0.1:8000 to fetch audit logs.")