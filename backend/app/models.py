"""SQLAlchemy-modellen — gecorrigeerd schema uit documentatie §6.
UUID's als String(36) zodat SQLite (lokaal) en PostgreSQL (Railway) beide werken."""
import uuid
from datetime import datetime

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer,
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    naam: Mapped[str | None] = mapped_column(String(255))
    jaar: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    totaal: Mapped[int | None] = mapped_column(Integer)
    verwerkt: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    companies: Mapped[list["Company"]] = relationship(back_populates="batch")


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("batch_id", "vestigingsnummer"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    vestigingsnummer: Mapped[str | None] = mapped_column(String(20))
    naam: Mapped[str] = mapped_column(String(255))
    cb_er: Mapped[str | None] = mapped_column(String(20))
    adres: Mapped[str | None] = mapped_column(Text)
    gemeente: Mapped[str | None] = mapped_column(String(100))
    sbi_code: Mapped[str | None] = mapped_column(String(10))
    sbi_omschrijving: Mapped[str | None] = mapped_column(Text)
    kvk_nummer: Mapped[str | None] = mapped_column(String(20))
    website_url: Mapped[str | None] = mapped_column(Text)
    telefoonnummer: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    batch: Mapped[Batch] = relationship(back_populates="companies")
    enrichment: Mapped["Enrichment | None"] = relationship(back_populates="company", uselist=False)
    agent_results: Mapped[list["AgentResult"]] = relationship(back_populates="company")
    candidate: Mapped["Candidate | None"] = relationship(back_populates="company", uselist=False)


class Enrichment(Base):
    __tablename__ = "enrichments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), unique=True)
    website_url: Mapped[str | None] = mapped_column(Text)
    telefoonnummer: Mapped[str | None] = mapped_column(String(50))
    locatie_count_nl: Mapped[int | None] = mapped_column(Integer)
    locatie_count_lb: Mapped[int | None] = mapped_column(Integer)
    locatie_bron: Mapped[str | None] = mapped_column(String(20))  # kvk|places|mock
    is_multi_locatie: Mapped[bool] = mapped_column(Boolean, default=False)
    adres_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    lookup_failed: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped[Company] = relationship(back_populates="agent_results")


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
    verwerkt: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
