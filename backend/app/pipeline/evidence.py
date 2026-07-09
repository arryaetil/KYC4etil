"""Evidence labels shared by agents, reconciliation, confidence and evals.

These labels intentionally separate "is this the right source?" from "what
scope does the number have?". A real concern annual report can be the right
source identity while still being the wrong scope for one branch.
"""
from dataclasses import dataclass, field
from enum import Enum

from ..providers.base import AgentFinding


class IdentityClass(str, Enum):
    EXACT_ENTITY = "exact_entity"
    SAME_BRAND_OR_GROUP = "same_brand_or_group"
    POSSIBLE_MATCH = "possible_match"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


class ScopeClass(str, Enum):
    VESTIGING = "vestiging"
    LIMBURG = "limburg"
    NEDERLAND = "nederland"
    CONCERN = "concern"
    UNKNOWN = "unknown"


class DirectnessClass(str, Enum):
    DIRECTLY_STATED = "directly_stated"
    INFERRED = "inferred"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


@dataclass
class EvidenceAssessment:
    identity: IdentityClass = IdentityClass.UNKNOWN
    scope: ScopeClass = ScopeClass.UNKNOWN
    directness: DirectnessClass = DirectnessClass.UNKNOWN
    official_source: bool | None = None
    address_match: bool | None = None
    freshness_year: int | None = None
    rejection_reason: str | None = None
    factors: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "identity": self.identity.value,
            "scope": self.scope.value,
            "directness": self.directness.value,
            "official_source": self.official_source,
            "address_match": self.address_match,
            "freshness_year": self.freshness_year,
            "rejection_reason": self.rejection_reason,
            "factors": self.factors,
        }


def assess_finding_evidence(finding: AgentFinding | None) -> EvidenceAssessment:
    """Best-effort evidence assessment from today's AgentFinding shape.

    Future graph nodes should write explicit values into finding.raw. Until then,
    this function maps existing fields conservatively so evals can expose what
    is still unknown.
    """
    if finding is None:
        return EvidenceAssessment(rejection_reason="geen finding")

    raw = finding.raw or {}
    identity = _enum_from_raw(raw, "identity_class", IdentityClass, IdentityClass.UNKNOWN)
    scope = _scope_from_finding(finding)
    directness = _directness_from_finding(finding)

    if raw.get("scope_class"):
        scope = _enum_from_raw(raw, "scope_class", ScopeClass, scope)
    if raw.get("directness_class"):
        directness = _enum_from_raw(raw, "directness_class", DirectnessClass, directness)

    return EvidenceAssessment(
        identity=identity,
        scope=scope,
        directness=directness,
        official_source=_official_source_from_finding(finding),
        freshness_year=_parse_year(finding.peilmoment),
        factors={
            "bron_type": finding.bron_type,
            "llm_zekerheid": finding.zekerheid,
            "is_limburg_specifiek": finding.is_limburg_specifiek,
            "is_totaal_meerdere_vestigingen": finding.is_totaal_meerdere_vestigingen,
            "is_fte": finding.is_fte,
            "has_context": bool(finding.context),
            "has_source_url": bool(finding.bron_url),
        },
    )


def _enum_from_raw(raw: dict, key: str, enum_type, default):
    try:
        return enum_type(raw.get(key))
    except ValueError:
        return default


def _scope_from_finding(finding: AgentFinding) -> ScopeClass:
    if finding.is_limburg_specifiek is True:
        return ScopeClass.VESTIGING if finding.bron_type == "website" else ScopeClass.LIMBURG
    if finding.is_limburg_specifiek is False:
        return ScopeClass.NEDERLAND
    return ScopeClass.UNKNOWN


def _directness_from_finding(finding: AgentFinding) -> DirectnessClass:
    if finding.raw.get("is_schatting"):
        return DirectnessClass.ESTIMATED
    if finding.wp_gevonden and finding.context:
        return DirectnessClass.DIRECTLY_STATED
    if finding.wp_gevonden:
        return DirectnessClass.INFERRED
    return DirectnessClass.UNKNOWN


def _official_source_from_finding(finding: AgentFinding) -> bool | None:
    if finding.bron_type in {"website", "jaarverslag"}:
        return True
    if finding.bron_type == "media":
        return False
    return None


def _parse_year(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(str(value)[:4])
    except ValueError:
        return None
