# 💳 RazorRecover: Autonomous AI Revenue Recovery Agent

An AI-powered payment diagnosis and recovery engine built for the Razorpay AI Builder program. RazorRecover detects at-risk payments, diagnoses the failure reason using an LLM, and executes strictly bounded recovery actions (like smart retries or payment links) to recover lost revenue safely.

## 🚀 Business Impact (Simulated Batch)
* **Revenue at Risk:** ₹11,40,029
* **Revenue Recovered:** ₹3,35,989
* **Recovery Rate:** 80.65%

## 🧠 System Architecture
1. **Frontend:** Streamlit dashboard for real-time business metrics and audit trails.
2. **Backend:** FastAPI for orchestrating the agent workflows.
3. **AI Agent:** Google Gemini (LLM) combined with an ML Risk probability model.
4. **Safety Layer:** Hard-coded stopping rules to prevent infinite loops and isolate fraud.

## ⚙️ How to Run Locally
1. Clone the repo.
2. Create a virtual environment: `python -m venv venv`
3. Install dependencies: `pip install -r requirements.txt`
4. Create a `.env` file and add your `GEMINI_API_KEY`.
5. Generate test data: `python generate_data.py`
6. Start backend: `uvicorn api.main:app --reload`
7. Start frontend: `streamlit run dashboard/app.py`