import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIException(Exception):
    def __init__(self, status_code: int, detail: str, file_id: str = None):
        self.status_code = status_code
        self.detail = detail
        self.file_id = file_id


async def api_exception_handler(request: Request, exc: APIException):
    content = {"detail": exc.detail}
    if exc.file_id:
        content["file_id"] = exc.file_id
    return JSONResponse(status_code=exc.status_code, content=content)


async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
