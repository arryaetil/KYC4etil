/**
 * Eén bron van waarheid voor alle labels en kleurtonen in de onderzoeksmodule.
 *
 * Kleurdiscipline: standaard neutraal. Amber ("aandacht") betekent uitsluitend
 * "controleer dit", rood ("fout") uitsluitend een identiteitsmismatch of een
 * mislukking, groen ("gekozen") uitsluitend een gekozen bron. Er bestaat
 * bewust geen groene "in orde"-toon: de afwezigheid van een waarschuwing is
 * het signaal.
 */

export const TOON_STYLE = {
  neutraal: "border-line bg-white text-slate-600",
  aandacht: "border-amber-200 bg-amber-50 text-amber-900",
  fout: "border-red-200 bg-red-50 text-red-800",
  gekozen: "border-emerald-200 bg-emerald-50 text-emerald-900",
};

const IDENTITEIT = {
  exact_entity: {label: "Dit bedrijf", toon: "neutraal"},
  same_brand_or_group: {label: "Zelfde groep", toon: "aandacht"},
  possible_match: {label: "Mogelijk ander bedrijf", toon: "aandacht"},
  unknown: {label: "Mogelijk ander bedrijf", toon: "aandacht"},
  mismatch: {label: "Ander bedrijf", toon: "fout"},
};

const BEREIK = {
  vestiging: {label: "Deze vestiging", toon: "neutraal"},
  limburg: {label: "Limburg", toon: "neutraal"},
  nederland: {label: "Heel Nederland", toon: "aandacht"},
  concern: {label: "Hele concern", toon: "aandacht"},
  unknown: {label: "Onbekend bereik", toon: "aandacht"},
};

const BRONTYPE = {
  officiele_website: "Officiële website",
  jaarverslag: "Jaarverslag",
  media: "Recente media",
  overheid: "Overheidsbron",
  sectorportaal: "Sectorbron",
  handmatig: "Handmatig toegevoegd",
};

export function organisatieStatus(company) {
  const status = company?.research_status;
  if (status === "error") {
    return {sleutel: "mislukt", label: "Mislukt", toon: "fout"};
  }
  if (status === "running" || status === "pending") {
    return {sleutel: "loopt", label: "Onderzoek loopt", toon: "neutraal"};
  }
  if (!status || status === "niet_gestart") {
    return {
      sleutel: "niet_onderzocht",
      label: "Nog niet onderzocht",
      toon: "neutraal",
    };
  }
  if (company.research_review_status === "geaccepteerd") {
    return {sleutel: "gekozen", label: "Bron gekozen", toon: "gekozen"};
  }
  if (company.research_resultaat_status === "niet_gevonden") {
    return {
      sleutel: "niet_gevonden",
      label: "Geen bron gevonden",
      toon: "aandacht",
    };
  }
  if (company.research_resultaat_status === "review_nodig") {
    return {sleutel: "te_beoordelen", label: "Te beoordelen", toon: "neutraal"};
  }
  return {sleutel: "afgerond", label: "Onderzoek afgerond", toon: "neutraal"};
}

export function identiteitLabel(identityClass) {
  return IDENTITEIT[identityClass] || IDENTITEIT.unknown;
}

export function bereikLabel(scopeClass) {
  return BEREIK[scopeClass] || BEREIK.unknown;
}

export function brontypeLabel(brontype) {
  return BRONTYPE[brontype] || "Openbare bron";
}

export function bronwaarschuwingen(candidate) {
  if (!candidate) return [];
  const items = [];
  if (candidate.eenheid === "fte") {
    items.push({label: "FTE — geen WP", toon: "aandacht"});
  }
  if (
    candidate.gevraagd_jaar != null
    && candidate.verslagjaar != null
    && candidate.gevraagd_jaar !== candidate.verslagjaar
  ) {
    items.push({label: "Ander verslagjaar", toon: "aandacht"});
  }
  if (candidate.wp_gevonden == null) {
    items.push({label: "Geen getal gevonden", toon: "aandacht"});
  }
  for (const waarschuwing of candidate.waarschuwingen || []) {
    items.push({
      label: String(waarschuwing).replaceAll("_", " "),
      toon: "aandacht",
    });
  }
  return items;
}
