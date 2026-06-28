from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, SessionLocal, engine, ensure_lightweight_migrations
from .models import Batch, ChatTemplate, PipelineRun
from .routers import auth, batches, chat, chat_admin, review, jaarverslagen

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
app.include_router(chat.router)
app.include_router(chat_admin.router)
app.include_router(jaarverslagen.router)


DEFAULT_TEMPLATE_CONFIG = {
    "veld_config": {
        "wp_totaal": "verplicht", "eigen_personeel": "verplicht", "uitzend": "verplicht",
        "detachering": "verplicht", "wsw": "verplicht", "man": "verplicht", "vrouw": "verplicht",
        "voltijd": "verplicht", "deeltijd": "verplicht", "pct_op_locatie": "optioneel",
        "adres": "verplicht", "correspondentieadres": "optioneel",
        "perceeloppervlakte": "verplicht", "winkeloppervlakte": "optioneel",
        "kantooroppervlakte": "optioneel", "bedrijfsvloeroppervlakte": "verplicht",
        "uitbreidingsruimte": "optioneel", "seizoensverschil": "optioneel", "opmerking": "optioneel",
    },
    "intro_tekst": "",
    "extra_vragen": [],
}


@app.on_event("startup")
def reset_stuck_batches() -> None:
    """Zet batches die 'running' waren bij herstart terug naar 'error'. Seeded standaard chat-template."""
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

        if db.query(ChatTemplate).count() == 0:
            db.add(ChatTemplate(
                naam="Standaard vragenlijst",
                beschrijving="Basisvragenlijst voor gerichte WP-uitvraag bij bedrijven",
                vragen=DEFAULT_TEMPLATE_CONFIG,
                is_default=True,
            ))
            db.commit()
        else:
            # Migreer bestaande templates met oud lijstformaat naar nieuw dict-formaat
            for tmpl in db.query(ChatTemplate).all():
                if isinstance(tmpl.vragen, list) or tmpl.vragen is None:
                    tmpl.vragen = DEFAULT_TEMPLATE_CONFIG
            db.commit()
    except Exception as exc:
        import logging
        logging.getLogger("startup").error("Startup event fout: %s", exc)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok", "provider_mode": settings.provider_mode}
