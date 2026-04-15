import uvicorn
import logging
import inngest.fast_api

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.models import *
from app.inngest.client import inngest_client
from app.inngest.functions import run_campaign

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

app = FastAPI(title="ReachAI Backend API")


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ROUTES
app.include_router(api_router)


# HEALTH
@app.get("/health")
async def health():
    return {"status": "healthy"}


# INNGEST
inngest.fast_api.serve(
    app,
    inngest_client,
    [run_campaign],
)


# RUN
if __name__ == "__main__":
    uvicorn.run("app.main:app", reload=True)