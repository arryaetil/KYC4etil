"""SQLAlchemy-modellen — gecorrigeerd schema uit documentatie §6.
UUID's als String(36) zodat SQLite (lokaal) en PostgreSQL (Railway) beide werken."""
import uuid
from datetime import date, datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    naam: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    rol: Mapped[str] = mapped_column(String(50), default="reviewer")
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    # Toegang intrekken haalt de rij niet weg. Een gebruiker staat overal in
    # het werk waar ze aan heeft gezeten: wie deze bron accepteerde, wie die
    # lijst uploadde. Die verwijzingen horen te blijven kloppen nadat het
    # account is ingetrokken, en in Postgres blokkeren ze een echte DELETE.
    verwijderd_op: Mapped[datetime | None] = mapped_column(DateTime)


class Map(Base):
    """Map waarin onderzoekslijsten worden geordend.

    Puur een ordeningslaag voor de reviewer: een map bevat lijsten, meer niet.
    Een lijst hoeft geen map te hebben — `Batch.map_id` mag leeg zijn — zodat
    een bestaande of via de API aangemaakte lijst nooit onbereikbaar wordt
    doordat er geen map bij is opgegeven.
    """

    __tablename__ = "mappen"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    naam: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    aangemaakt_door: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    # Archiveren is de zachte variant van opruimen: de map verdwijnt uit het
    # hoofdoverzicht, maar de lijsten erin blijven onaangeraakt en bereikbaar.
    # Daarmee is verwijderen niet langer de enige manier om orde te houden.
    gearchiveerd_op: Mapped[datetime | None] = mapped_column(DateTime)

    batches: Mapped[list["Batch"]] = relationship(back_populates="map")


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    naam: Mapped[str | None] = mapped_column(String(255))
    jaar: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    totaal: Mapped[int | None] = mapped_column(Integer)
    verwerkt: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_monitoringlijst: Mapped[bool] = mapped_column(Boolean, default=False)
    geupload_door: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    # Leeg = losse lijst, zichtbaar buiten elke map. Bewust geen verplichte
    # koppeling: een lijst die via de API binnenkomt zonder map moet vindbaar
    # blijven in plaats van nergens te staan.
    map_id: Mapped[str | None] = mapped_column(ForeignKey("mappen.id"), index=True)
    # Prullenbak: gevuld = weggegooid maar nog terug te halen. Een lijst
    # verwijderen wist eerder alles ineens — inclusief elke beoordeling die
    # erin zat — zonder weg terug. Mappen kenden dit al (`gearchiveerd_op`);
    # lijsten niet, terwijl daar het werk in zit.
    verwijderd_op: Mapped[datetime | None] = mapped_column(DateTime)

    companies: Mapped[list["Company"]] = relationship(back_populates="batch")
    map: Mapped["Map | None"] = relationship(back_populates="batches")


class Organization(Base):
    """Deterministische bovenlaag voor vestigingen van dezelfde organisatie.

    Alleen een exact KvK-nummer of een bevestigd websitedomein mag vestigingen
    koppelen. Naamgelijkenis is bewust geen identiteitssleutel.
    """

    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    identity_key: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    naam: Mapped[str] = mapped_column(String(255))
    kvk_nummer: Mapped[str | None] = mapped_column(String(20), index=True)
    website_domain: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    companies: Mapped[list["Company"]] = relationship(back_populates="organization")


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("batch_id", "vestigingsnummer"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), index=True,
    )
    vestigingsnummer: Mapped[str | None] = mapped_column(String(20))
    naam: Mapped[str] = mapped_column(String(255))
    cb_er: Mapped[str | None] = mapped_column(String(20))
    adres: Mapped[str | None] = mapped_column(Text)
    gemeente: Mapped[str | None] = mapped_column(String(100))
    sbi_code: Mapped[str | None] = mapped_column(String(10))
    sbi_omschrijving: Mapped[str | None] = mapped_column(Text)
    kvk_nummer: Mapped[str | None] = mapped_column(String(20))
    afgewerkt: Mapped[bool] = mapped_column(Boolean, default=False)
    website_url: Mapped[str | None] = mapped_column(Text)
    telefoonnummer: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    batch: Mapped[Batch] = relationship(back_populates="companies")
    organization: Mapped[Organization | None] = relationship(back_populates="companies")
    enrichment: Mapped["Enrichment | None"] = relationship(back_populates="company", uselist=False)
    agent_results: Mapped[list["AgentResult"]] = relationship(back_populates="company")
    research_runs: Mapped[list["ResearchRun"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    bronkandidaten: Mapped[list["BronKandidaat"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    candidate: Mapped["Candidate | None"] = relationship(back_populates="company", uselist=False)
    vastgoed: Mapped["VastgoedRecord | None"] = relationship(back_populates="company", uselist=False)

    @property
    def effectieve_website_url(self) -> str | None:
        """De website waar het onderzoek mee heeft gewerkt.

        De verrijking gaat voor: die is tijdens een run gevonden of gecorrigeerd,
        terwijl `website_url` uit het aangeleverde bestand komt en verouderd kan
        zijn. Valt terug op het aangeleverde adres zodra de verrijking leeg is.

        Die terugval is de reden dat dit één plek is en geen losse expressie per
        export: beide exports schreven `enrichment.website_url if enrichment else
        website_url`, en lieten de kolom dus leeg zodra er een verrijkingsrij
        bestond zonder website — bijvoorbeeld na een mislukte Places-lookup.
        """
        return (
            (self.enrichment.website_url if self.enrichment else None)
            or self.website_url
        )


class Enrichment(Base):
    __tablename__ = "enrichments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), unique=True)
    website_url: Mapped[str | None] = mapped_column(Text)
    telefoonnummer: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    locatie_count_nl: Mapped[int | None] = mapped_column(Integer)
    locatie_count_lb: Mapped[int | None] = mapped_column(Integer)
    locatie_bron: Mapped[str | None] = mapped_column(String(20))  # kvk|places|mock
    is_multi_locatie: Mapped[bool] = mapped_column(Boolean, default=False)
    adres_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    lookup_failed: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    company: Mapped[Company] = relationship(back_populates="enrichment")


class AgentResult(Base):
    __tablename__ = "agent_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"))
    agent_type: Mapped[str] = mapped_column(String(50))  # website|jaarverslag
    wp_gevonden: Mapped[int | None] = mapped_column(Integer)
    wp_context: Mapped[str | None] = mapped_column(Text)
    is_limburg_specifiek: Mapped[bool | None] = mapped_column(Boolean)
    is_fte: Mapped[bool] = mapped_column(Boolean, default=False)
    peilmoment: Mapped[str | None] = mapped_column(String(20))
    bron_url: Mapped[str | None] = mapped_column(Text)
    bron_type: Mapped[str | None] = mapped_column(String(50))  # website|jaarverslag|media
    raw_output: Mapped[dict | None] = mapped_column(JSON)
    llm_zekerheid: Mapped[str | None] = mapped_column(String(10))
    eigen_personeel: Mapped[int | None] = mapped_column(Integer)
    uitzend: Mapped[int | None] = mapped_column(Integer)
    detachering: Mapped[int | None] = mapped_column(Integer)
    wsw: Mapped[int | None] = mapped_column(Integer)
    man: Mapped[int | None] = mapped_column(Integer)
    vrouw: Mapped[int | None] = mapped_column(Integer)
    voltijd: Mapped[int | None] = mapped_column(Integer)
    deeltijd: Mapped[int | None] = mapped_column(Integer)
    pct_op_locatie: Mapped[float | None] = mapped_column(Float)
    bron_pagina: Mapped[int | None] = mapped_column(Integer)
    identity_class: Mapped[str | None] = mapped_column(String(30))  # exact_entity|same_brand_or_group|possible_match|mismatch|unknown
    scope_class: Mapped[str | None] = mapped_column(String(30))  # vestiging|limburg|nederland|concern|unknown
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    company: Mapped[Company] = relationship(back_populates="agent_results")


class ResearchRun(Base):
    """Een begrensde bronnenresearch-opdracht voor één organisatie."""

    __tablename__ = "research_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"), index=True
    )
    doel: Mapped[str] = mapped_column(Text)
    gevraagd_jaar: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    resultaat_status: Mapped[str | None] = mapped_column(String(30))
    onderzoekspaden: Mapped[list | None] = mapped_column(JSON)
    configuratie: Mapped[dict | None] = mapped_column(JSON)
    fout: Mapped[str | None] = mapped_column(Text)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    kosten_cents: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    company: Mapped[Company] = relationship(back_populates="research_runs")
    bronkandidaten: Mapped[list["BronKandidaat"]] = relationship(
        back_populates="research_run", cascade="all, delete-orphan"
    )


class BronKandidaat(Base):
    """Uniform bewijsobject uit website-, document- of mediaonderzoek."""

    __tablename__ = "bron_kandidaten"
    __table_args__ = (
        UniqueConstraint(
            "research_run_id", "canonical_url",
            name="uq_bron_kandidaat_run_canonical_url",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    research_run_id: Mapped[str] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    titel: Mapped[str | None] = mapped_column(Text)
    brontype: Mapped[str] = mapped_column(String(50))
    documenttype: Mapped[str | None] = mapped_column(String(50))
    verslagjaar: Mapped[int | None] = mapped_column(Integer)
    publicatiedatum: Mapped[date | None] = mapped_column(Date)
    informatie_peilmoment: Mapped[str | None] = mapped_column(String(20))
    wp_gevonden: Mapped[int | None] = mapped_column(Integer)
    eenheid: Mapped[str | None] = mapped_column(String(30))
    bewijsfragment: Mapped[str | None] = mapped_column(Text)
    bron_pagina: Mapped[int | None] = mapped_column(Integer)
    identity_class: Mapped[str | None] = mapped_column(String(30))
    scope_class: Mapped[str | None] = mapped_column(String(30))
    autoriteit_score: Mapped[float | None] = mapped_column(Float)
    actualiteit_score: Mapped[float | None] = mapped_column(Float)
    identiteit_score: Mapped[float | None] = mapped_column(Float)
    relevantie_score: Mapped[float | None] = mapped_column(Float)
    ranking_score: Mapped[float | None] = mapped_column(Float)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON)
    validaties: Mapped[dict | None] = mapped_column(JSON)
    waarschuwingen: Mapped[list | None] = mapped_column(JSON)
    raw_data: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="voorgesteld")
    rang: Mapped[int | None] = mapped_column(Integer)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_reason_code: Mapped[str | None] = mapped_column(String(50))
    review_reason: Mapped[str | None] = mapped_column(Text)
    bron_relevant: Mapped[bool | None] = mapped_column(Boolean)
    bron_volledig_ingelezen: Mapped[bool | None] = mapped_column(Boolean)
    wp_oordeel: Mapped[str | None] = mapped_column(String(30))
    gecorrigeerd_wp: Mapped[int | None] = mapped_column(Integer)
    extractie_reason_code: Mapped[str | None] = mapped_column(String(50))
    extractie_toelichting: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    research_run: Mapped[ResearchRun] = relationship(back_populates="bronkandidaten")
    company: Mapped[Company] = relationship(back_populates="bronkandidaten")


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("company_id", "batch_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"))
    wp_kandidaat: Mapped[int | None] = mapped_column(Integer)
    is_schatting: Mapped[bool] = mapped_column(Boolean, default=False)
    gekozen_agent_result: Mapped[str | None] = mapped_column(ForeignKey("agent_results.id"))
    reconciliatie_reden: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    confidence_label: Mapped[str | None] = mapped_column(String(10))  # hoog|middel|laag
    score_breakdown: Mapped[dict | None] = mapped_column(JSON)
    strategie: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending|approved|corrected|to_chat|to_call
    reviewer_signaal: Mapped[str | None] = mapped_column(Text)  # actiegerichte melding, geen scoreverandering
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    company: Mapped[Company] = relationship(back_populates="candidate")


class WPRecord(Base):
    __tablename__ = "wp_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"))
    wp_waarde: Mapped[int] = mapped_column(Integer)
    wp_jaar: Mapped[int] = mapped_column(Integer)
    bron_type: Mapped[str] = mapped_column(String(50))
    bron_url: Mapped[str | None] = mapped_column(Text)
    eigen_personeel: Mapped[int | None] = mapped_column(Integer)
    uitzend: Mapped[int | None] = mapped_column(Integer)
    detachering: Mapped[int | None] = mapped_column(Integer)
    wsw: Mapped[int | None] = mapped_column(Integer)
    man: Mapped[int | None] = mapped_column(Integer)
    vrouw: Mapped[int | None] = mapped_column(Integer)
    voltijd: Mapped[int | None] = mapped_column(Integer)
    deeltijd: Mapped[int | None] = mapped_column(Integer)
    pct_op_locatie: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50))  # auto|reviewed|corrected|pending_chat
    goedgekeurd_door: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    goedgekeurd_op: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    variant: Mapped[str] = mapped_column(String(10))  # gericht|volledig
    status: Mapped[str] = mapped_column(String(50), default="created")
    pre_fill_wp: Mapped[int | None] = mapped_column(Integer)
    vragen: Mapped[dict | None] = mapped_column(JSON)
    antwoorden: Mapped[dict | None] = mapped_column(JSON)
    messages: Mapped[list | None] = mapped_column(JSON)
    verwerkt: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)


class ChatTemplate(Base):
    __tablename__ = "chat_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    naam: Mapped[str] = mapped_column(String(255))
    beschrijving: Mapped[str | None] = mapped_column(Text)
    vragen: Mapped[dict | None] = mapped_column(JSON)  # runtime: list van vraag-objecten
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    aangemaakt_door: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class CallListItem(Base):
    __tablename__ = "call_list"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    telefoonnummer: Mapped[str | None] = mapped_column(String(50))
    reden: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="open")
    toegewezen_aan: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    notities: Mapped[str | None] = mapped_column(Text)
    resultaat_wp: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class VastgoedRecord(Base):
    __tablename__ = "vastgoed_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), unique=True)
    perceel_opp: Mapped[int | None] = mapped_column(Integer)       # m²
    winkel_opp: Mapped[int | None] = mapped_column(Integer)        # m²
    kantoor_opp: Mapped[int | None] = mapped_column(Integer)       # m²
    bedrijfs_opp: Mapped[int | None] = mapped_column(Integer)      # m²
    uitbreidingsruimte: Mapped[bool | None] = mapped_column(Boolean)
    seizoensverschillen: Mapped[bool | None] = mapped_column(Boolean)
    seizoen_toelichting: Mapped[str | None] = mapped_column(Text)
    correspondentieadres: Mapped[str | None] = mapped_column(Text)
    bron: Mapped[str | None] = mapped_column(String(50))  # chat|handmatig|import
    ingevoerd_door: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    company: Mapped["Company"] = relationship(back_populates="vastgoed")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"))
    stap: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str | None] = mapped_column(String(20))  # ok|error|skipped
    duur_ms: Mapped[int | None] = mapped_column(Integer)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    kosten_cents: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class JaarverslagUpload(Base):
    __tablename__ = "jaarverslag_uploads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), index=True)
    bestandsnaam: Mapped[str] = mapped_column(String(255))
    pdf_tekst: Mapped[str] = mapped_column(Text)
    jaar: Mapped[int | None] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    berichten: Mapped[list["JaarverslagChatMessage"]] = relationship(
        back_populates="upload", order_by="JaarverslagChatMessage.created_at",
        cascade="all, delete-orphan",
    )


class JaarverslagChatMessage(Base):
    __tablename__ = "jaarverslag_chat_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    upload_id: Mapped[str] = mapped_column(
        ForeignKey("jaarverslag_uploads.id"), index=True
    )
    rol: Mapped[str] = mapped_column(String(10))   # 'user' | 'assistant'
    inhoud: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    upload: Mapped[JaarverslagUpload] = relationship(back_populates="berichten")


class Handeling(Base):
    """Wie deed wat, en wanneer.

    Bronbeslissingen stonden al vast op de bronkandidaat zelf: wie accepteerde,
    met welke reden, op welk moment. Alles daaromheen niet. Wie heeft die lijst
    geüpload, wie heeft die vestiging toegevoegd, wie heeft dat account
    ingetrokken — daar was geen spoor van, en dat merk je pas als iemand vraagt
    "waar is die lijst gebleven".

    Bewust plat: een soort, een omschrijving in gewone taal, en losse velden om
    op terug te zoeken. Geen verwijzingen naar rijen die later verdwijnen — juist
    bij een verwijdering moet de regel blijven kloppen als het object weg is.
    """

    __tablename__ = "handelingen"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    soort: Mapped[str] = mapped_column(String(50), index=True)
    omschrijving: Mapped[str] = mapped_column(Text)
    # Geen ForeignKey: de gebruiker kan later worden verwijderd, en dan hoort
    # de handeling niet mee te verdwijnen of te blokkeren.
    door_id: Mapped[str | None] = mapped_column(String(36))
    door_naam: Mapped[str | None] = mapped_column(String(100))
    onderwerp_id: Mapped[str | None] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class Opmerking(Base):
    """Een vrije opmerking van een reviewer over één organisatie.

    Naast de vaste afwijs- en extractieredenen, niet in plaats daarvan. Die
    keuzelijsten vangen op wát er mis was met een bron; ze vangen niet op dat
    een vestiging is gefuseerd, dat het onderzoek steeds het concernverslag
    pakt, of dat een hele sector een bron mist die de reviewer wél kent.

    Eén opmerking helpt niemand. De waarde zit in de stapel: vijftig ervan laten
    zien waar het onderzoek structureel naast zit. Daarom platte tekst en geen
    categorieën — een keuzelijst kan alleen antwoorden op vragen die we al
    hadden bedacht.

    Aan de organisatie en niet aan een bronkaart: dat is de eenheid waarin
    gewerkt wordt, en een kaart kan verdwijnen bij een nieuwe run terwijl de
    constatering blijft gelden.
    """

    __tablename__ = "opmerkingen"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True,
    )
    geschreven_door: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    tekst: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    company: Mapped["Company"] = relationship()


class JaarverslagMonitoring(Base):
    __tablename__ = "jaarverslag_monitoring"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), unique=True, index=True)
    laatste_bron_url: Mapped[str | None] = mapped_column(Text)
    laatste_verslagjaar: Mapped[int | None] = mapped_column(Integer)
    laatst_gecontroleerd_op: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
