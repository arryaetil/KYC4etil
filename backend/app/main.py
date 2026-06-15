from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, SessionLocal, engine, ensure_lightweight_migrations
from .models import Batch, PipelineRun
from .routers import auth, batches, review

settings = get_settings()

Base.metadata.create_all(bind=engine)
ensure_lightweight_migrations()

app = FastAPI(title="Vestigingsregister AI Platform", version="0.1.0",
              description="AI-pipeline voor WP-dataverzameling — Etil / Provincie Limburg")

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                   allow_headers=["*"], expose_headers=["Content-Disposition"])

app.include_router(auth.router)
app.include_router(batches.router)
app.include_router(review.router)


@app.on_event("startup")
def reset_stuck_batches() -> None:
    """Zet batches die 'running' waren bij herstart terug naar 'error'."""
    db = SessionLocal()
    try:
        stuck = db.query(Batch).filter_by(status="running").all()
        for batch in stuck:
            batch.status = "error"
            db.add(PipelineRun(batch_id=batch.id, stap="startup_recovery",
                               status="error", duur_ms=0,
                               error="Batch onderbroken door service-herstart"))
        if stuck:
            db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok", "provider_mode": settings.provider_mode}
