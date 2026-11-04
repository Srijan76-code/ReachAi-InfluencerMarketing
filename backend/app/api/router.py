from fastapi import APIRouter

from app.api.routes import campaign, deals, gmail, outreach, saved_lead, share

api_router = APIRouter()

api_router.include_router(campaign.router, prefix="/api/campaigns", tags=["Campaigns"])
api_router.include_router(saved_lead.router, prefix="/api/saved", tags=["Saved Leads"])
api_router.include_router(outreach.router, prefix="/api/outreach", tags=["Outreach"])
api_router.include_router(share.router, tags=["Share links"])
api_router.include_router(deals.router, tags=["Deals"])
api_router.include_router(gmail.router, tags=["Gmail"])
