from fastapi import APIRouter

from app.api.routes import campaign, outreach, saved_lead

api_router = APIRouter()

api_router.include_router(campaign.router, prefix="/api/campaigns", tags=["Campaigns"])
api_router.include_router(saved_lead.router, prefix="/api/saved", tags=["Saved Leads"])
api_router.include_router(outreach.router, prefix="/api/outreach", tags=["Outreach"])


