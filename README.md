# 💳 RazorRecover: Enterprise Autonomous AI Revenue Recovery Agent

An autonomous AI payment recovery platform engineered for high-throughput payment recovery, graph-based syndicate fraud isolation, and human-in-the-loop exception handling. Built for the Razorpay Buildathon.

---

## 🌟 Key Enterprise Capabilities

1. **🕸️ Networked Fraud Detection (Graph Theory Engine)**:
   - Evaluates payment entity graphs (mapping transactions as nodes and shared IP addresses / Device fingerprints as edges).
   - Traverses 2-hop connected components in sub-millisecond time.
   - Detects syndicated fraud clusters, triggers hard security escalations, and completely bypasses LLM invocations to prevent unauthorized retries and save API compute.

2. **🛡️ Human-in-the-Loop (HITL) Operations Queue**:
   - Dedicated review workbench for safety guardrail escalations, high-value edge cases, and isolated fraud suspects.
   - 1-click execution: Instant Retry, Dynamic Payment Link, or Permanent Rejection with custom reviewer audit notes.

3. **📈 Executive ROI & Unit Economics Quantification**:
   - Live tracking of LLM API token spend (Gemini 1.5 Flash) and gateway execution costs against recovered Gross Merchandise Value (GMV).
   - Live leadership metrics: Net Revenue Recovered, Effective ROI Multiplier, and Cost per ₹10,000 Recovered.

---

## 🚀 Live Business Impact (Simulated 1,000-Txn Batch)
* **Gross Revenue at Risk:** ₹21,18,651.33
* **Autonomous Revenue Recovered:** ₹5,71,891.30
* **Recovery Rate:** 83.33%
* **Fraud Syndicate Nodes Isolated (LLM Bypassed):** 45 Nodes
* **AI & Gateway Spend:** ₹4.55
* **Net Value Generated:** ₹5,71,886.75
* **ROI Multiplier:** ~125,000x Return on AI Spend

---

## 🧠 Production System Architecture
1. **Frontend:** Streamlit 4-tab Enterprise Control Center (Recovery Engine, HITL Queue, ROI Economics, Fraud Graph Topology).
2. **Backend:** FastAPI high-performance orchestration API (`/api/process-batch`, `/api/escalation-queue`, `/api/roi-metrics`, `/api/fraud-network`).
3. **Graph Intelligence:** In-memory BFS bipartite entity graph detector (`core/fraud_graph.py`).
4. **AI & ML Engine:** Google Gemini 1.5 Flash + Scikit-Learn Random Forest Risk Scorer (`core/risk_model.py`, `core/agent.py`).
5. **Safety Guardrails:** Multi-layered stopping rules (`core/stopping_rules.py`).
6. **Data Layer:** SQLite with SQLAlchemy ORM (`database/models.py`).

---

## ⚙️ How to Run Locally
1. Clone the repository.
2. Create & activate a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure `.env`:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
5. Generate synthetic graph dataset:
   ```bash
   python generate_data.py
   ```
6. Start backend:
   ```bash
   uvicorn api.main:app --reload
   ```
7. Start frontend dashboard:
   ```bash
   streamlit run dashboard/app.py
   ```