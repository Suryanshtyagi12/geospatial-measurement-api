from fastapi import FastAPI
from .database import Base, engine

# Initialize database
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Geospatial File Measurement API",
    description="API to accept geospatial files and calculate projected measurements.",
    version="1.0.0",
)

@app.get("/health")
def health_check():
    return {"status": "ok"}
