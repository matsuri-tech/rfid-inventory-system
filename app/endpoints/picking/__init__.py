from fastapi import APIRouter
from app.endpoints.picking.sync_picking import router as sync_router
from app.endpoints.picking.update_inventory_picking import router as update_router

router = APIRouter()
router.include_router(sync_router, prefix="/picking")
router.include_router(update_router, prefix="/picking")