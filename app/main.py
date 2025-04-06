from fastapi import FastAPI
from app.endpoints.picking import router as picking_router
from app.endpoints.receiving import router as receiving_router
from app.endpoints.stockhouse import router as stockhouse_router

app = FastAPI()

app.include_router(picking_router)
app.include_router(receiving_router)
app.include_router(stockhouse_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
