from fastapi import APIRouter
from app.endpoints.stockhouse.sync_linen_stockhouse import router as sync_router

router = APIRouter()
router.include_router(sync_router, prefix="/stockhouse")