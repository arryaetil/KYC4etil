from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, engine
from .routers import auth, batches, review

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Vestigingsregister AI Platform", version="0.1.0",
              description="AI-pipeline voor WP-dataverzameling — Etil / Provincie Limburg")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])  # demo; in productie beperken tot frontend-origin

app.include_router(auth.router)
app.include_router(batches.router)
app.include_router(review.router)


@app.get("/health")
def health():
    return {"status": "ok", "provider_mode": get_settings().provider_mode}
