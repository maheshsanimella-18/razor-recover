from fastapi import FastAPI
from api.routes import router
from database.session import engine, Base

# Create tables if not present
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RazorRecover API",
    description="Autonomous AI Revenue Recovery Engine with Audit Trail",
    version="1.0.0"
)

app.include_router(router, prefix="/api")

@app.get("/")
def root():
    return {"message": "RazorRecover AI Engine is running."}