from fastapi import APIRouter
import httpx

router = APIRouter()

CLOUD_RUN_BASE = "https://rfid-cloud-api-829912128848.asia-northeast1.run.app"

@router.post("/batch/inventory-full-update")
async def run_inventory_update_batch():
    endpoints = [
        "/receiving/sync-small-rfid",
        "/receiving/update-inventory-small",
        "/picking/sync-picking",
        "/picking/update-inventory"
    ]

    results = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for endpoint in endpoints:
            try:
                res = await client.post(f"{CLOUD_RUN_BASE}{endpoint}")
                results.append({
                    "endpoint": endpoint,
                    "status_code": res.status_code,
                    "response": res.json()
                })
            except Exception as e:
                results.append({
                    "endpoint": endpoint,
                    "error": str(e)
                })

    return {"status": "completed", "results": results}
