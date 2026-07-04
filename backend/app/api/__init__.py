from fastapi import APIRouter

from . import auth, bootstrap, lists, metrics, stocks

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(bootstrap.router)
api_router.include_router(lists.router)
api_router.include_router(metrics.router)
api_router.include_router(stocks.router)
