from fastapi import FastAPI
from .database import Base, engine
from .api import files
from .exceptions import APIException, api_exception_handler, generic_exception_handler

# Initialize database
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Geospatial File Measurement API",
    description="API to accept geospatial files and calculate projected measurements.",
    version="1.0.0",
)

app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.include_router(files.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}

