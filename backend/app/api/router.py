from fastapi import APIRouter

from app.api.routes import api_keys, billing, campaign, deals, gmail, outreach, saved_lead, share, track

api_router = APIRouter()

api_router.include_router(campaign.router, prefix="/api/campaigns", tags=["Campaigns"])
api_router.include_router(saved_lead.router, prefix="/api/saved", tags=["Saved Leads"])
api_router.include_router(outreach.router, prefix="/api/outreach", tags=["Outreach"])
api_router.include_router(share.router, tags=["Share links"])
api_router.include_router(deals.router, tags=["Deals"])
api_router.include_router(gmail.router, tags=["Gmail"])
api_router.include_router(track.router, tags=["Track"])
api_router.include_router(billing.router, prefix="/api/billing", tags=["Billing"])
api_router.include_router(billing.webhook_router, tags=["Billing"])
api_router.include_router(api_keys.router, prefix="/api/keys", tags=["API Keys"])
