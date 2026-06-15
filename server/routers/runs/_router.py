"""runs 子路由共享 APIRouter。"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/runs", tags=["runs"])
