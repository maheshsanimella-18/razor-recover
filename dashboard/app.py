import streamlit as st
import requests
import pandas as pd
import altair as alt

# --- Page Configuration ---
st.set_page_config(
    page_title="RazorRecover — Autonomous Revenue Recovery",
    layout="wide",
    page_icon="💳",
    initial_sidebar_state="expanded"
)

API_BASE_URL = "http://127.0.0.1:8000/api"
COST_PER_GEMINI_CALL = 0.05  # ₹0.05 estimated cost per LLM diagnosis call

# --- Header & Branding ---
st.title("💳 RazorRecover — Autonomous AI Revenue Recovery Agent")
st.caption("Production-grade autonomous payment diagnosis, safety escalations, and revenue recovery engine for Razorpay.")

st.divider()

# --- Sidebar Controls ---
st.sidebar.header("🕹️ Agent Operations")
st.sidebar.markdown("Trigger the autonomous recovery pipeline on failed transactions in the database.")

if st.sidebar.button("🚀 Trigger AI Recovery Batch", type="primary", use_container_width=True):
    with st.spinner("Diagnosing payment failures and executing bounded recovery actions..."):
        try:
            res = requests.post(f"{API_BASE_URL}/process-batch", timeout=60)
            if res.status_code == 200:
                data = res.json()
                st.sidebar.success(f"✅ Batch complete! Recovered ₹{data['total_revenue_recovered']:,.2f}")
                st.rerun()
            else:
                st.sidebar.error(f"API Error: {res.text}")
        except Exception as e:
            st.sidebar.error(f"Connection failed: {e}")

st.sidebar.divider()
st.sidebar.markdown("### 💡 Fintech Recovery Principles")
st.sidebar.info(
    "1. **Safety First**: Infinite retry loops are prevented via strict caps.\n"
    "2. **Human-in-the-Loop**: Ambiguous or high-risk cases are escalated.\n"
    "3. **ROI Positive**: High recovery GMV at negligible AI API cost (₹0.05/call)."
)

# --- Navigation Tabs ---
tab_dashboard, tab_escalations, tab_audit = st.tabs([
    "📊 Executive Dashboard & ROI",
    "🛡️ Human-in-the-Loop Escalation Queue",
    "📜 Live Audit Ledger"
])

# =========================================================
# TAB 1: EXECUTIVE DASHBOARD & ROI REPORTING
# =========================================================
with tab_dashboard:
    st.subheader("📈 Executive Performance & ROI Reporting")
    st.markdown("Quantifying real business impact: **Total Revenue Recovered** vs. **Estimated Gemini API Cost**.")

    try:
        # Fetch live database metrics and audit logs from backend
        roi_res = requests.get(f"{API_BASE_URL}/roi-metrics", timeout=5)
        logs_res = requests.get(f"{API_BASE_URL}/audit-logs?limit=500", timeout=5)

        if roi_res.status_code == 200:
            roi_data = roi_res.json()
            total_recovered = roi_data["total_recovered_revenue"]
            total_at_risk = roi_data["total_at_risk_revenue"]
            recovery_rate = roi_data["recovery_rate_pct"]

            # Count total Gemini diagnosis calls made across transactions
            llm_calls_count = 0
            if logs_res.status_code == 200:
                logs_data = logs_res.json()
                llm_calls_count = sum(
                    1 for log in logs_data 
                    if log["agent_decision"] in ["IMMEDIATE_RETRY", "DELAYED_RETRY", "SEND_PAYMENT_LINK", "ESCALATE_TO_HUMAN"]
                )

            # Fallback estimation if logs are freshly reset
            if llm_calls_count == 0 and total_recovered > 0:
                llm_calls_count = roi_data.get("total_processed", 100)

            # Executive Unit Economics Calculations
            total_api_cost = round(llm_calls_count * COST_PER_GEMINI_CALL, 2)
            net_profit_recovered = round(total_recovered - total_api_cost, 2)
            roi_multiplier = round(total_recovered / max(total_api_cost, 0.01), 1) if total_recovered > 0 else 0.0

            # --- Top-Level KPI Metric Cards ---
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Revenue Recovered", f"₹{total_recovered:,.2f}", delta="Gross Recovered GMV")
            col2.metric("Revenue at Risk", f"₹{total_at_risk:,.2f}")
            col3.metric("Estimated Gemini API Cost", f"₹{total_api_cost:,.2f}", help=f"{llm_calls_count} calls @ ₹{COST_PER_GEMINI_CALL} per call")
            col4.metric("Net Profit / ROI Value", f"₹{net_profit_recovered:,.2f}", delta=f"{roi_multiplier:,.0f}x Return")

            st.divider()

            # --- Visual ROI Comparison Chart & Summary Table ---
            chart_col1, chart_col2 = st.columns([3, 2])

            with chart_col1:
                st.markdown("##### 💰 Value Generated vs. Operational API Cost")
                comparison_df = pd.DataFrame({
                    "Metric": ["Revenue Recovered", "Gemini API Cost"],
                    "Amount (₹)": [total_recovered, max(total_api_cost, 1.0)]
                })
                bar_chart = alt.Chart(comparison_df).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
                    x=alt.X("Metric:N", title="", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("Amount (₹):Q", title="Amount in INR (₹)"),
                    color=alt.Color("Metric:N", scale=alt.Scale(range=["#10b981", "#ef4444"]))
                ).properties(height=280)
                st.altair_chart(bar_chart, use_container_width=True)

            with chart_col2:
                st.markdown("##### 📋 Executive Financial Breakdown")
                roi_summary_table = pd.DataFrame([
                    {"Key Metric": "Total Payments at Risk", "Value": f"₹{total_at_risk:,.2f}"},
                    {"Key Metric": "Gross Revenue Recovered", "Value": f"₹{total_recovered:,.2f}"},
                    {"Key Metric": "Success Recovery Rate", "Value": f"{recovery_rate}%"},
                    {"Key Metric": "Gemini API Calls Made", "Value": f"{llm_calls_count} calls"},
                    {"Key Metric": "Estimated Gemini Cost (₹0.05/call)", "Value": f"₹{total_api_cost:,.2f}"},
                    {"Key Metric": "Net Recovered Revenue (Profit)", "Value": f"₹{net_profit_recovered:,.2f}"},
                    {"Key Metric": "Return on AI Investment (ROI)", "Value": f"{roi_multiplier:,.1f}x Multiplier"}
                ])
                st.dataframe(roi_summary_table, use_container_width=True, hide_index=True)
        else:
            st.warning("Backend API is currently offline. Please ensure FastAPI is running on http://127.0.0.1:8000.")
    except Exception as e:
        st.error(f"Error loading executive metrics: {e}")

# =========================================================
# TAB 2: HUMAN-IN-THE-LOOP ESCALATION QUEUE
# =========================================================
with tab_escalations:
    st.subheader("🛡️ Human-in-the-Loop Escalation Queue")
    st.markdown("Transactions flagged for human review (`ESCALATE_TO_HUMAN` or safety guardrail blocks). Support agents can inspect full diagnostic context and take bounded recovery actions.")

    try:
        queue_res = requests.get(f"{API_BASE_URL}/escalation-queue?status=PENDING_REVIEW", timeout=5)
        if queue_res.status_code == 200:
            escalated_items = queue_res.json()
            st.markdown(f"**Pending Cases Awaiting Human Review:** `{len(escalated_items)}`")

            if escalated_items:
                # Render clean cards for each escalated transaction
                for item in escalated_items[:15]:  # Display top 15 for responsive UI
                    with st.expander(
                        f"💳 **{item['id']}** | Amount: **₹{item['amount']:,.2f}** | Customer: `{item['customer_id']}` | Reason: `{item['failure_reason']}`",
                        expanded=True
                    ):
                        c1, c2, c3 = st.columns(3)
                        c1.markdown(f"**Transaction ID:** `{item['id']}`")
                        c1.markdown(f"**Customer ID:** `{item['customer_id']}`")
                        
                        c2.markdown(f"**Amount at Risk:** ₹{item['amount']:,.2f}")
                        c2.markdown(f"**Retry Attempts:** `{item['retry_count']}`")
                        
                        c3.markdown(f"**Queue Status:** ⚠️ `{item['queue_status']}`")
                        c3.markdown(f"**Escalated At:** `{item.get('escalated_at', 'N/A')}`")

                        st.info(f"🧠 **AI Diagnostic / Guardrail Context:** {item.get('latest_audit_reason', 'Escalated to human support for manual review.')}")

                        # Support Agent 1-Click Action Buttons
                        st.markdown("##### ✍️ Human Operator Decision:")
                        act_col1, act_col2, act_col3 = st.columns([2, 2, 2])

                        notes_val = f"Manual review approved by support agent for {item['id']}"

                        if act_col1.button("✅ Approve & Retry Charge", key=f"btn_retry_{item['id']}", use_container_width=True):
                            action_res = requests.post(
                                f"{API_BASE_URL}/escalation-queue/{item['id']}/action",
                                json={"action": "APPROVE_RETRY", "reviewer_notes": notes_val}
                            )
                            if action_res.status_code == 200:
                                st.toast(f"Retry triggered for {item['id']}", icon="✅")
                                st.rerun()

                        if act_col2.button("✉️ Send Payment Link", key=f"btn_link_{item['id']}", use_container_width=True):
                            action_res = requests.post(
                                f"{API_BASE_URL}/escalation-queue/{item['id']}/action",
                                json={"action": "APPROVE_PAYMENT_LINK", "reviewer_notes": notes_val}
                            )
                            if action_res.status_code == 200:
                                st.toast(f"Payment Link sent to customer for {item['id']}", icon="✉️")
                                st.rerun()

                        if act_col3.button("🛑 Reject / Close Case", key=f"btn_rej_{item['id']}", type="secondary", use_container_width=True):
                            action_res = requests.post(
                                f"{API_BASE_URL}/escalation-queue/{item['id']}/action",
                                json={"action": "REJECT", "reviewer_notes": "Rejected by support agent as unrecoverable."}
                            )
                            if action_res.status_code == 200:
                                st.toast(f"Transaction {item['id']} rejected.", icon="🛑")
                                st.rerun()
            else:
                st.success("🎉 No pending escalations! All transactions have been processed or resolved.")
        else:
            st.error(f"Failed to fetch escalation queue: {queue_res.text}")
    except Exception as e:
        st.error(f"Connection error fetching escalation queue: {e}")

# =========================================================
# TAB 3: LIVE AUDIT LEDGER
# =========================================================
with tab_audit:
    st.subheader("📜 Live Autonomous Agent Audit Ledger")
    st.caption("Immutable record of AI diagnoses, guardrail blocks, token costs, and recovery outcomes.")

    try:
        logs_res = requests.get(f"{API_BASE_URL}/audit-logs?limit=50", timeout=5)
        if logs_res.status_code == 200:
            logs = logs_res.json()
            if logs:
                df_logs = pd.DataFrame(logs)
                st.dataframe(
                    df_logs[['timestamp', 'transaction_id', 'agent_decision', 'reasoning']],
                    column_config={
                        "timestamp": st.column_config.DatetimeColumn("Timestamp", format="D MMM YYYY, HH:mm:ss"),
                        "transaction_id": st.column_config.TextColumn("Transaction ID"),
                        "agent_decision": st.column_config.TextColumn("AI Decision"),
                        "reasoning": st.column_config.TextColumn("Reasoning / Diagnostic Detail")
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No audit logs recorded yet. Trigger a batch in the sidebar to populate logs.")
    except Exception as e:
        st.warning(f"Audit log backend unavailable: {e}")