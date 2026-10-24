from fastapi import APIRouter

from . import admin, attachment, auth, chat, results, tasks, ws

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(attachment.router)
api_router.include_router(tasks.router)
api_router.include_router(results.router)
api_router.include_router(admin.router)
api_router.include_router(ws.router)
