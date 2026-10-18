"""API v1 router."""

from fastapi import APIRouter
from app.api.v1.approvals import router as approvals_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.browser import router as browser_router
from app.api.v1.business import router as business_router
from app.api.v1.coding import router as coding_router
from app.api.v1.commerce import router as commerce_router
from app.api.v1.communication import router as communication_router
from app.api.v1.events import router as events_router
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.memories import router as memories_router
from app.api.v1.models import router as models_router
from app.api.v1.proactive import router as proactive_router
from app.api.v1.research import router as research_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.system import router as system_router
from app.api.v1.temporal import router as temporal_router
from app.api.v1.vision import router as vision_router
from app.api.v1.voice import router as voice_router
from app.api.v1.ws import router as ws_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router, tags=["Health"])
api_v1_router.include_router(system_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(approvals_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(temporal_router)
api_v1_router.include_router(memories_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(events_router)
api_v1_router.include_router(proactive_router)
api_v1_router.include_router(models_router)
api_v1_router.include_router(research_router)
api_v1_router.include_router(coding_router)
api_v1_router.include_router(browser_router)
api_v1_router.include_router(vision_router)
api_v1_router.include_router(business_router)
api_v1_router.include_router(communication_router)
api_v1_router.include_router(commerce_router)
api_v1_router.include_router(jobs_router)
api_v1_router.include_router(voice_router)
api_v1_router.include_router(ws_router)

__all__ = ["api_v1_router"]

