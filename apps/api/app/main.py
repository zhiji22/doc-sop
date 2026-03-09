from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes.files import router as files_router
from app.api.routes.runs import router as runs_router

app = FastAPI(title="doc-sop-api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.WEB_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(files_router)
app.include_router(runs_router)