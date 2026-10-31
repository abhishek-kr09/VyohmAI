from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.schemas import HealthResponse
from app.routes.recordings import router as recordings_router
from app.routes.upload import router as upload_router
from app.routes.search import router as search_router
from app.routes.chat import router as chat_router
from app.routes.actions import router as actions_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


settings = get_settings()
app = FastAPI(title="Pocket Recorder API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(upload_router)
app.include_router(recordings_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(actions_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="pocket-recorder-api", database="configured")
