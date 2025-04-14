from fastapi import APIRouter

#from app.endpoints.receiving.enqueue_large_rfid import router as enqueue_router
#from app.endpoints.receiving.rfid_large import router as rfid_large_router
#from dev.rfid_small import router as rfid_small_router
#from app.endpoints.receiving.sync_large_rfid import router as sync_large_router
#from app.endpoints.receiving.update_inventory_large_receiving import router as update_large_inventory_router
from app.endpoints.receiving.sync_small_receiving import router as sync_small_receiving_router  # ← ✅ 追加
from app.endpoints.receiving.update_inventory_small_receiving import router as update_small_inventory_router  # ← ✅追加
from app.endpoints.receiving.update_inventory_large_receiving import router as update_large_inventory_router  # ← ✅追加

router = APIRouter()
#router.include_router(enqueue_router)
#router.include_router(rfid_large_router)
#router.include_router(rfid_small_router)
#router.include_router(sync_large_router)
#router.include_router(update_large_inventory_router)
router.include_router(sync_small_receiving_router)  # ← ✅ 最後に追加
router.include_router(update_small_inventory_router)  # ← ✅追加
router.include_router(update_large_inventory_router)  # ← ✅追加