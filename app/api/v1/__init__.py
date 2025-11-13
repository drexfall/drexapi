from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

from app.api.v1.endpoints import users  # noqa: E402, F401
from app.api.v1.endpoints import utils  # noqa: E402, F401

router.include_router(users.router)
router.include_router(utils.router)
