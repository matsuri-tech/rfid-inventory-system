# main.py
import uvicorn
from fastapi import FastAPI
from app.endpoints import (
    rfid_large,
    rfid_small,
    sync_large_rfid,
    sync_picking,
    update_inventory_large_receiving,
    enqueue_large_rfid,
    sync_linen_stockhouse
)

app = FastAPI()
app.include_router(rfid_large.router)
app.include_router(rfid_small.router)
app.include_router(sync_large_rfid.router)
app.include_router(sync_picking.router)
app.include_router(update_inventory_large_receiving.router)
app.include_router(enqueue_large_rfid.router)
app.include_router(sync_linen_stockhouse.router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
