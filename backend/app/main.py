from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Base, engine
from .routers import auth, drives, reports, students

app = FastAPI(
    title="SRK Placement AI",
    description="AI-assisted resume screening and placement platform for Shri Rama Krishna Group, Satna. "
    "AI assists; people decide.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


Base.metadata.create_all(engine)
for r in (auth.router, students.router, drives.router, reports.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True}


# Serve the built React app (frontend/dist) when present, so one container runs everything.
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        return FileResponse(_DIST / "index.html")
