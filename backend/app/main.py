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
        "wp_totaal": True, "eigen_personeel": True, "uitzend": True,
        "detachering": True, "wsw": True, "man": True, "vrouw": True,
        "voltijd": True, "deeltijd": True, "pct_op_locatie": True,
        "adres": True, "correspondentieadres": True,
        "perceeloppervlakte": True, "winkeloppervlakte": True,
        "kantooroppervlakte": True, "bedrijfsvloeroppervlakte": True,
        "uitbreidingsruimte": True, "seizoensverschil": True, "opmerking": True,
    },
    "intro_tekst": "",
    "extra_vragen": [],
}


@app.on_event("startup")
def reset_stuck_batches() -> None:
    """Zet batches die 'running' waren bij herstart terug naar 'error'. Seeded standaard chat-template."""
    import logging
    _log = logging.getLogger("startup")
    if settings.jwt_secret == "change-me":
        _log.critical(
            "BEVEILIGINGSWAARSCHUWING: JWT_SECRET staat op de standaardwaarde 'change-me'. "
            "Stel JWT_SECRET in als omgevingsvariabele voor productie."
        )
    if settings.email_demo_recipient:
        _log.warning(
            "email_demo_recipient is ingesteld op '%s'. "
            "Alle chat-uitnodigingen gaan naar dit adres i.p.v. het bedrijf. "
            "Leeghalen voor productie via EMAIL_DEMO_RECIPIENT=",
            settings.email_demo_recipient,
        )
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
