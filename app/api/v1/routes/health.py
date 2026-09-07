from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/db")
async def check_database():
    async with engine.connect() as connection:
        result = await connection.scalar(text("SELECT 1"))

    return {
        "database": "connected",
        "result": result,
    }