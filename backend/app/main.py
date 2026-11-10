import uvicorn
import logging
import os
import inngest.fast_api

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.models import *
from app.inngest.client import inngest_client
from app.inngest.functions import keep_backend_warm, refresh_track, refresh_youtube_data, run_campaign, run_outreach, sync_gmail_replies
from app.mcp.server import mcp_routes

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

app = FastAPI(title="ReachAI Backend API")


ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,"
        "https://reach-ai-influencer-marketing.vercel.app",
    ).split(",")
    if origin.strip()
]

ALLOWED_ORIGIN_REGEX = (
    r"https?://(localhost|127\.0\.0\.1)(:\d+)?$|"
    r"https://[a-z0-9-]+\.vercel\.app$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    logging.getLogger("uvicorn.error").exception(
        "Unhandled API error for %s %s", request.method, request.url.path, exc_info=exc
    )
    origin = request.headers.get("origin")
    headers = {}
    if origin in ALLOWED_ORIGINS:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=headers,
    )


# ROUTES
app.include_router(api_router)

# MCP (agent access, spec §15): /api/mcp and its OAuth metadata
app.router.routes.extend(mcp_routes())


# HEALTH
@app.get("/health")
async def health():
    return {"status": "healthy"}


# INNGEST
inngest.fast_api.serve(
    app,
    inngest_client,
    [run_campaign, run_outreach, refresh_youtube_data, keep_backend_warm, sync_gmail_replies, refresh_track],
)


# RUN
if __name__ == "__main__":
    uvicorn.run("app.main:app", reload=True)