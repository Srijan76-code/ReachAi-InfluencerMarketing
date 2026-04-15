from fastapi import APIRouter

from app.api.routes import campaign, saved_lead, webhook

api_router = APIRouter()

api_router.include_router(campaign.router, prefix="/api/campaigns", tags=["Campaigns"])
api_router.include_router(saved_lead.router, prefix="/api/saved", tags=["Saved Leads"])
api_router.include_router(webhook.router, prefix="/api/webhooks", tags=["Webhooks"])