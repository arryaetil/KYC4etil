from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, engine
from .routers import auth, batches, review

settings = get_settings()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Vestigingsregister AI Platform", version="0.1.0",
              description="AI-pipeline voor WP-dataverzameling — Etil / Provincie Limburg")

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                   allow_headers=["*"])

app.include_router(auth.router)
app.include_router(batches.router)
app.include_router(review.router)


@app.get("/health")
def health():
    return {"status": "ok", "provider_mode": settings.provider_mode}
