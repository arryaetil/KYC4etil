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
  instelling: {label: "Onderwijsinstelling", toon: "aandacht"},
  nederland: {label: "Heel Nederland", toon: "aandacht"},
  concern: {label: "Hele concern", toon: "aandacht"},
  unknown: {label: "Onbekend bereik", toon: "aandacht"},
};

/**
 * Backend-waarschuwingen naar leesbaar Nederlands.
 *
 * `null` betekent bewust onderdrukken. Deze sleutels leidt de bronkaart nu af
 * uit `bewijsRelatie`/`bereikRelatie` (één zin in de samenvatting); ze ook nog
 * als losse chip tonen levert twee meldingen voor hetzelfde feit op —
 * bijvoorbeeld "Geen getal gevonden" naast "Alleen context, geen WP-getal".
 * `recent_actualiteitssignaal` is een pluspunt, geen "controleer dit", en
 * hoort dus niet thuis in een rij waarschuwingen.
 */
const WAARSCHUWING = {
  fte_geen_wp: null,
  // Onderdrukt omdat `bronwaarschuwingen` het jaarverschil zelf al benoemt,
  // mét beide jaartallen. Zowel de batchflow (`source_reviewer`) als de
  // monitoring zet deze sleutel; de chip mag daar niet twee keer van staan.
  afwijkend_verslagjaar: null,
  scope_breder_dan_vestiging: null,
  recent_actualiteitssignaal: null,
  getal_zonder_bewijsfragment: null,
  geen_concreet_wp_bewijs: null,
  alleen_context_geen_wp_voorstel: null,
  duo_definitie_wijkt_af_van_wp: {
    label: "DUO-definitie — controleer tegen WP", toon: "aandacht",
  },
  wp_afgeleid_uit_naamlijst: {
    label: "Geteld uit namenlijst", toon: "aandacht",
  },
  naamlijst_telling_aan_reviewer: {
    label: "Tel zelf — telling ingetrokken", toon: "aandacht",
  },
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
  // `technisch_onvolledig` betekent: een verplichte onderzoeksroute is technisch
  // mislukt, dus "niets gevonden" is hier geen conclusie maar een onbekende.
  // Zonder deze regel viel die status door naar "Onderzoek afgerond" — neutraal
  // en buiten elk filter, terwijl er juist iets te herstellen valt.
  if (company.research_resultaat_status === "technisch_onvolledig") {
    return {
      sleutel: "onvolledig",
      label: "Onderzoek onvolledig",
      toon: "aandacht",
    };
  }
  return {sleutel: "afgerond", label: "Onderzoek afgerond", toon: "neutraal"};
}

/**
 * Monitoring heeft een eigen vocabulaire. De agent vindt daar hooguit een
 * jaarverslag; niemand kiest een bron. Daarom bewust geen "Bron gekozen" en
 * geen groene toon — dat zou een menselijke keuze suggereren die er niet is.
 *
 * De status gaat over het verslagjaar, niet over de vorige controleronde.
 * "Nieuwe vondst" stond hier eerder bovenaan, maar dat betekent "veranderd
 * sinds de laatste keer": op de watchlist van 10-08-2026 kregen precies twee
 * organisaties die badge en die stonden allebei op verslagjaar 2023, terwijl
 * de 51 organisaties met een verslag over 2025 neutraal bleven. De
 * delta-informatie blijft bestaan (`nieuwe_bevinding`), maar als secundair
 * signaal naast de jaarstatus — zie MonitoringVondst.
 *
 * `jaarstatus` en `doeljaar` komen van de backend, zodat er één plek is waar
 * "is dit verslag actueel?" wordt beslist.
 */
export function monitoringStatus(company) {
  if (company?.fout) {
    return {sleutel: "mislukt", label: "Controle mislukt", toon: "fout"};
  }
  // Terugval voor een respons van vóór het jaarstatus-contract: dan alleen
  // "is er een bron", zonder een actualiteit te suggereren die we niet weten.
  const jaarstatus = company?.jaarstatus
    || (company?.laatste_bron_url ? "verouderd" : "ontbreekt");

  if (jaarstatus === "actueel") {
    return {
      sleutel: "actueel",
      label: company?.doeljaar
        ? `Verslag ${company.doeljaar} binnen`
        : "Actueel verslag",
      toon: "neutraal",
    };
  }
  if (jaarstatus === "verouderd") {
    return {
      sleutel: "verouderd",
      label: company?.verslagjaar
        ? `Alleen verslag ${company.verslagjaar}`
        : "Verslag zonder jaartal",
      toon: "aandacht",
    };
  }
  return {
    sleutel: "ontbreekt",
    label: "Geen jaarverslag gevonden",
    toon: "aandacht",
  };
}

export function identiteitLabel(identityClass) {
  return IDENTITEIT[identityClass] || IDENTITEIT.unknown;
}

export function bereikLabel(scopeClass) {
  return BEREIK[scopeClass] || BEREIK.unknown;
}

/**
 * Voor de bronkaart-samenvatting: dezelfde classificatie als `identiteitLabel`,
 * maar in de relationele taal die de reviewer als eerste leest ("komt overeen"
 * versus de technische klassenaam "Dit bedrijf" in de onderbouwing).
 */
export function bedrijfRelatie(identityClass) {
  if (identityClass === "mismatch") {
    return {label: "Afwijkend", toon: "fout"};
  }
  if (identityClass === "exact_entity" || identityClass === "same_brand_or_group") {
    return {label: "Komt overeen", toon: "neutraal"};
  }
  return {label: "Nog niet vastgesteld", toon: "aandacht"};
}

/** Zelfde idee als `bedrijfRelatie`, maar dan voor geografisch bereik. */
export function bereikRelatie(scopeClass) {
  if (scopeClass === "vestiging") {
    return {label: "Vastgesteld — deze vestiging", toon: "neutraal"};
  }
  if (scopeClass === "limburg") {
    return {label: "Vastgesteld — Limburg", toon: "neutraal"};
  }
  if (scopeClass === "nederland" || scopeClass === "concern" || scopeClass === "instelling") {
    return {label: "Breder dan deze vestiging", toon: "aandacht"};
  }
  return {label: "Nog niet vastgesteld", toon: "aandacht"};
}

/**
 * Eén regel bewijsstatus. Vervangt de losse chips "Geen getal gevonden",
 * "Alleen context, geen WP-getal" en "Getal zonder citaat" door één zin, zodat
 * dezelfde constatering niet twee keer in andere woorden op de kaart staat.
 */
export function bewijsRelatie(candidate) {
  const heeftGetal = candidate?.wp_gevonden != null;
  const heeftCitaat = !!candidate?.bewijsfragment;
  if (heeftGetal && candidate.eenheid === "werkzame_personen") {
    return heeftCitaat
      ? {label: `${candidate.wp_gevonden} WP, met citaat`, toon: "neutraal"}
      : {label: `${candidate.wp_gevonden} WP, zonder citaat`, toon: "aandacht"};
  }
  if (heeftGetal && candidate.eenheid === "fte") {
    return {label: `${candidate.wp_gevonden} FTE — geen WP-getal`, toon: "aandacht"};
  }
  if (heeftGetal && candidate.eenheid === "onderwijspersoneel_personen") {
    return {
      label: `${candidate.wp_gevonden} onderwijspersoneel — DUO-definitie, controleer tegen WP`,
      toon: "aandacht",
    };
  }
  if (candidate?.documenttype === "teampagina") {
    return {label: "Teamoverzicht gevonden, nog niet geteld", toon: "aandacht"};
  }
  if (heeftCitaat) {
    return {label: "Alleen context, geen WP-getal", toon: "aandacht"};
  }
  return {label: "Geen medewerkerstal uitgelezen", toon: "aandacht"};
}

/**
 * De primaire conclusie bovenaan de kaart: één zin in gewone taal, met
 * optioneel een tweede zin over het geografisch bereik. Technische
 * classificaties (identity_class, scope_class) komen pas daarna.
 */
export function primaireConclusie(candidate) {
  const identiteit = candidate?.identity_class;
  const bereik = candidate?.scope_class;
  const heeftWpGetal = candidate?.wp_gevonden != null
    && candidate?.eenheid === "werkzame_personen";
  const heeftCitaat = !!candidate?.bewijsfragment;
  const juisteIdentiteit = identiteit === "exact_entity" || identiteit === "same_brand_or_group";

  let hoofd;
  if (identiteit === "mismatch") {
    hoofd = "Deze bron lijkt bij een ander bedrijf te horen.";
  } else if (heeftWpGetal && heeftCitaat) {
    hoofd = "Bruikbaar WP-getal gevonden, met citaat.";
  } else if (heeftWpGetal) {
    hoofd = "WP-getal gevonden, maar zonder citaat ter onderbouwing.";
  } else if (candidate?.eenheid === "fte" && candidate?.wp_gevonden != null) {
    hoofd = "Alleen een FTE-cijfer gevonden — dat is geen WP-getal.";
  } else if (candidate?.eenheid === "onderwijspersoneel_personen" && candidate?.wp_gevonden != null) {
    hoofd = "Alleen een DUO-personeelscijfer gevonden — controleer dit tegen de WP-definitie.";
  } else if (candidate?.documenttype === "duo_personeel_personen") {
    hoofd = "DUO-personeelscijfer gevonden, nog niet herleid naar deze vestiging.";
  } else if (candidate?.documenttype === "teampagina") {
    hoofd = "Teampagina gevonden, medewerkers nog niet geteld.";
  } else if (juisteIdentiteit) {
    hoofd = "Juiste bedrijfsbron gevonden, maar nog geen medewerkerstal uitgelezen.";
  } else {
    hoofd = "Bron gevonden, maar nog geen medewerkerstal uitgelezen.";
  }

  let vervolg = null;
  if (bereik === "unknown") {
    vervolg = "De locatie waarop deze informatie betrekking heeft is nog niet vastgesteld.";
  } else if (bereik === "instelling") {
    vervolg = "Dit cijfer geldt voor de hele onderwijsinstelling, niet per se voor deze vestiging.";
  } else if (bereik === "nederland" || bereik === "concern") {
    vervolg = "Dit cijfer geldt breder dan alleen deze vestiging.";
  }

  return {hoofd, vervolg};
}

export function brontypeLabel(brontype) {
  return BRONTYPE[brontype] || "Openbare bron";
}

/**
 * Een namenlijst die niet het personeelsbestand van déze vestiging is, levert
 * geen WP-voorstel maar een telopdracht op. De namen zijn al vastgelegd door de
 * agent, zodat de reviewer ze naast de bron kan leggen in plaats van opnieuw te
 * zoeken.
 */
export function telopdracht(candidate) {
  const vastgelegd = candidate?.validaties?.naamlijst_telling_aan_reviewer;
  if (!vastgelegd) return null;
  return {
    reden: vastgelegd.reden,
    afgeleidAantal: vastgelegd.afgeleid_aantal ?? null,
    namen: vastgelegd.genoemde_namen || [],
    uitleg: vastgelegd.reden === "leidinggevendenlijst"
      ? "Deze pagina toont de leidinglaag van de organisatie, niet het personeelsbestand."
      : "Deze namenlijst gaat breder dan deze vestiging.",
  };
}

export function menselijkeWaarde(candidate) {
  const vastgelegd = candidate?.validaties?.menselijke_waarde;
  if (vastgelegd?.label && vastgelegd?.actie) return vastgelegd;
  const telling = telopdracht(candidate);
  if (telling) {
    return {
      rol: "telopdracht",
      label: "Tel de medewerkers zelf",
      actie: `${telling.uitleg} Tel de medewerkers op de bron zelf.`,
      aantal_namen: telling.namen.length,
    };
  }
  if (candidate?.documenttype === "duo_personeel_personen") {
    return {
      rol: "duo_personeelsbron",
      label: "DUO-personeelscijfer",
      actie: candidate.wp_gevonden == null
        ? "Controleer de deelinstellingen; DUO-waarden zijn bewust niet opgeteld."
        : "Controleer of de DUO-instelling en het bereik overeenkomen met de registratievestiging.",
    };
  }
  if (
    candidate?.wp_gevonden != null
    && candidate?.eenheid === "werkzame_personen"
    && candidate?.bewijsfragment
  ) {
    return candidate.scope_class === "vestiging" || candidate.scope_class === "limburg"
      ? {
          rol: "direct_wp_bewijs",
          label: "Direct WP-bewijs",
          actie: "Controleer het citaat en de scope; het personeelsgetal staat al in de bron.",
        }
      : {
          rol: "organisatieomvang",
          label: "Indicatie organisatieomvang",
          actie: "Gebruik dit groeps- of organisatiecijfer als context en zoek naar een vestigingsuitsplitsing.",
        };
  }
  if (candidate?.documenttype === "teampagina") {
    return {
      rol: "teamoverzicht",
      label: "Teamoverzicht",
      actie: "Bekijk of tel de genoemde teamleden en controleer of alle functies en locaties zijn opgenomen.",
    };
  }
  if (["jaarverslag", "jaarrekening", "bestuursverslag", "pdf_document"].includes(
    candidate?.documenttype,
  )) {
    return {
      rol: "formeel_document",
      label: "Formeel document",
      actie: "Doorzoek het document op medewerkers, personeel, werknemers, fte en vestigingsnamen.",
    };
  }
  return {
    rol: "aanvullende_context",
    label: "Aanvullende onderzoeksroute",
    actie: "Controleer de bron op namen, locaties of verwijzingen naar een sterkere primaire bron.",
  };
}

export function bronwaarschuwingen(candidate) {
  if (!candidate) return [];
  const items = [];
  if (
    candidate.gevraagd_jaar != null
    && candidate.verslagjaar != null
    && candidate.gevraagd_jaar !== candidate.verslagjaar
  ) {
    // Noem beide jaren. "Ander verslagjaar" liet de reviewer zelf uitzoeken
    // welk jaar er dan gevraagd was, en verzweeg of dit verslag ouder of
    // nieuwer is. Monitoring bewaart oudere verslagen sinds kort bewust als
    // beoordeelbare bron, dus dat onderscheid moet op de kaart staan.
    items.push({
      label: candidate.verslagjaar < candidate.gevraagd_jaar
        ? `Verslag ${candidate.verslagjaar}, gevraagd is ${candidate.gevraagd_jaar}`
        : `Verslag ${candidate.verslagjaar}, nieuwer dan gevraagd`,
      toon: "aandacht",
    });
  }
  for (const waarschuwing of candidate.waarschuwingen || []) {
    const sleutel = String(waarschuwing);
    if (sleutel in WAARSCHUWING) {
      const bekend = WAARSCHUWING[sleutel];
      if (bekend) items.push({...bekend});
      continue;
    }
    items.push({label: sleutel.replaceAll("_", " "), toon: "aandacht"});
  }
  const gezien = new Set();
  return items.filter((item) => {
    if (gezien.has(item.label)) return false;
    gezien.add(item.label);
    return true;
  });
}
