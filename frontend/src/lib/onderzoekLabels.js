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
  // Geen chip: de regel Peilmoment noemt het DUO-jaar al, en waaróm dat een
  // jaar achterloopt (DUO meet op 1 oktober en publiceert later) is geen
  // reviewbeslissing maar een eigenschap van de bron.
  duo_jaar_achter: null,
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

  // "Nieuw" betekent in deze module één ding: het verslag over het doeljaar.
  // Niet "veranderd sinds de vorige ronde" — dat woord is hier bewust vermeden,
  // anders staat er twee keer "nieuw" op dezelfde kaart met een andere betekenis.
  if (jaarstatus === "actueel") {
    return {
      sleutel: "actueel",
      label: company?.doeljaar
        ? `Nieuw — verslag ${company.doeljaar}`
        : "Nieuw verslag",
      toon: "neutraal",
    };
  }
  if (jaarstatus === "verouderd") {
    return {
      sleutel: "verouderd",
      label: company?.verslagjaar
        ? `Ouder — verslag ${company.verslagjaar}`
        : "Ouder — jaartal onbekend",
      toon: "aandacht",
    };
  }
  return {
    sleutel: "ontbreekt",
    label: "Niet gevonden",
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
 * Waar hoort dit getal bij in de tijd? Eén regel op de bronkaart.
 *
 * Dit is de ENIGE plek op de kaart waar het jaar van een bron staat. Het stond
 * er even op drie: in de kop naast het brontype, in deze regel, en als chip
 * onder het citaat ("Verslag 2024, gevraagd is 2025") — drie formuleringen van
 * één feit, op drie hoogtes. Wie de kaarten langsloopt moet zijn oog op één
 * plek kunnen houden, dus het staat hier en nergens anders. Het achterlopen op
 * het gevraagde jaar staat in dezelfde regel, want dat gaat over hetzelfde.
 *
 * De regel staat er altijd, ook zonder datum en ook zonder getal. Verdween hij,
 * dan kan de reviewer "geen datum bekend" niet onderscheiden van "hier is niet
 * naar gekeken". Bij een personeelsgetal is dat verschil belangrijk: een getal
 * zonder datum is niet te plaatsen tegen het peiljaar. En bij een bron zonder
 * getal is de datering even goed een openstaande vraag — dat de regel daar
 * eerder wegviel, maakte een half onderzochte bron ononderscheidbaar van een
 * bron waarin niets te vinden was.
 *
 * Gemeten op de productiedatabase van 17-08-2026: van de 880 kandidaten met
 * brontype `officiele_website` heeft 9% een peilmoment, terwijl 173 een WP-getal
 * dragen. Websites vermelden zelden per wanneer een aantal geldt, dus dit is
 * geen zeldzaam geval maar de norm. De datum van ophalen invullen zou dat gat
 * dichten met een aanname: een pagina kan een cijfer uit 2019 tonen.
 */
export function peilmomentRelatie(candidate, {gevraagdJaar = null} = {}) {
  if (!candidate) return null;
  const jaar = bronjaar(candidate);

  // Een jaarverslag heeft een verslagjaar, geen peilmoment — het label van de
  // regel past zich aan in plaats van dat er een tweede regel bij komt.
  if (jaar?.soort === "verslagjaar") {
    // Alleen het jaartal. Dat het achterloopt op het peiljaar zegt de amber
    // toon al; het peiljaar erbij zetten maakt de regel langer zonder dat de
    // reviewer iets ziet wat hij nog niet wist — het peiljaar staat boven de
    // lijst en is voor alle kaarten hetzelfde.
    const achter = gevraagdJaar != null && jaar.jaar < gevraagdJaar;
    return {
      term: "Verslagjaar",
      label: `${jaar.jaar}`,
      toon: achter ? "aandacht" : "neutraal",
    };
  }
  if (candidate.informatie_peilmoment) {
    return {
      term: "Peilmoment",
      label: String(candidate.informatie_peilmoment),
      toon: "neutraal",
    };
  }
  const aanwijzing = jaaraanwijzing(candidate);
  if (aanwijzing) {
    // Toon "aandacht", niet "neutraal": dit jaartal dateert de bron en niet het
    // getal. Een teampagina uit 2023 kan een cijfer van eerder tonen.
    return {
      term: "Peilmoment",
      label: `${aanwijzing.jaar} — ${aanwijzing.herkomst}`,
      toon: "aandacht",
    };
  }
  return {term: "Peilmoment", label: "Niet bekend", toon: "aandacht"};
}

/**
 * Is dit een bron met een verslagjaar, of alleen met een peilmoment?
 *
 * Een jaarverslag gaat over een jaar; een website of nieuwsartikel niet. Bij
 * zo'n bron is "verslagjaar" het verkeerde woord en "dit verslag loopt achter"
 * een zinloze mededeling — een teampagina is geen verslag over 2023.
 */
function isVerslagbron(candidate) {
  return (
    FORMELE_DOCUMENTTYPEN.has(candidate?.documenttype)
    || ["jaarverslag", "digimv"].includes(candidate?.brontype)
  );
}

/**
 * Uit welk jaar lijkt deze bron te zijn, en waaraan zie je dat?
 *
 * Voor een jaarverslag is het jaar een vaststelling; bij een website of
 * nieuwsartikel is het een aanwijzing. Die aanwijzing wordt hier wél getoond —
 * hem verzwijgen omdat hij niet hard is laat de reviewer met niets achter,
 * terwijl `/nieuws/2023/...` een bruikbaar signaal is. De herkomst staat erbij
 * zodat de reviewer zelf kan wegen hoe hard het jaartal is.
 *
 * Volgorde: het jaar in de URL gaat vóór `verslagjaar`, want bij een
 * niet-verslagbron komt dat veld uit een jaartal ergens in de paginatekst en
 * krijgt het gevraagde jaar daar de voorkeur — een pagina die "2025" noemt
 * heet dan van 2025 te zijn.
 */
function jaaraanwijzing(candidate) {
  if (candidate?.jaar_uit_url) {
    return {jaar: candidate.jaar_uit_url, herkomst: "jaar uit de link"};
  }
  if (candidate?.verslagjaar) {
    return {jaar: candidate.verslagjaar, herkomst: "jaar uit de bron"};
  }
  return null;
}

/**
 * Uit welk jaar is deze bron? Eén regel, altijd zichtbaar op de bronkaart.
 *
 * Twee velden dragen dat jaar en ze betekenen iets anders: `verslagjaar` is het
 * jaar waar het document over gaat, `informatie_peilmoment` het moment waarop
 * het getal betrekking heeft. Ze kunnen verschillen (een jaarverslag over 2025
 * met een personeelsstand per 1 oktober 2025), dus het label zegt welk van de
 * twee je ziet in plaats van er stilzwijgend één jaartal van te maken.
 *
 * Gemeten op de productiedatabase van 17-08-2026: van de 1.281 bronkandidaten
 * heeft 479 een verslagjaar en 213 een peilmoment. Beide stonden tot nu toe
 * alleen in de dichtgeklapte onderbouwing, dus moest de reviewer per kaart
 * openklappen om te zien of een bron over het goede jaar ging.
 */
export function bronjaar(candidate) {
  if (candidate?.verslagjaar && isVerslagbron(candidate)) {
    return {jaar: candidate.verslagjaar, soort: "verslagjaar"};
  }
  const peilmoment = String(candidate?.informatie_peilmoment || "");
  const gevonden = peilmoment.match(/(19|20)\d{2}/);
  if (gevonden) {
    return {jaar: Number(gevonden[0]), soort: "peilmoment"};
  }
  // Zonder opgegeven peilmoment de aanwijzing uit de bron zelf. Websites geven
  // zelden aan per wanneer een aantal geldt (9% van 880 kandidaten met
  // brontype `officiele_website`, gemeten 17-08-2026), dus zonder deze
  // terugval blijft de kaart van een website vrijwel altijd jaarloos.
  const aanwijzing = jaaraanwijzing(candidate);
  return aanwijzing ? {jaar: aanwijzing.jaar, soort: "peilmoment"} : null;
}


const FORMELE_DOCUMENTTYPEN = new Set([
  "jaarverslag", "jaarrekening", "bestuursverslag", "pdf_document",
]);

/** "peiljaar 2025", of een omschrijving die net zo leest zonder jaartal. */
function peiljaarnaam(gevraagdJaar) {
  return gevraagdJaar ? `peiljaar ${gevraagdJaar}` : "het peiljaar";
}

/**
 * Eén oordeel boven de bronnenlijst: wat is er gevonden en hoe hard is het.
 *
 * Bewust deterministisch en niet door een model geschreven. Dit kaartje zegt
 * precies hoe betrouwbaar het bewijs is, en dat is de laatste plek waar een
 * gegenereerde formulering iets mag beweren dat de bronnen niet dragen. Alle
 * signalen liggen al in de kandidaten: het getal, de eenheid, het citaat, de
 * identiteit, het bereik en het verslagjaar.
 *
 * De kleurdiscipline van deze module geldt ook hier: groen alléén als de
 * reviewer zelf een bron heeft gekozen, amber voor "controleer dit", en geen
 * enkele groene toon voor een uitkomst die de agent zelf heeft bedacht.
 *
 * `letOp` bevat de voorbehouden die bij het gevonden bewijs horen. Ze staan los
 * van de hoofdregel omdat ze het oordeel niet veranderen maar wel meewegen:
 * een concerncijfer blijft een concerncijfer, ook als twee bronnen het noemen.
 *
 * Het jaar van een bron telt mee in het oordeel, niet alleen in de losse
 * kaarten. Twee redenen. Ten eerste is "zo recent mogelijk" onderdeel van wat
 * een bron waard maakt: een bevestigd getal uit 2019 is zwakker bewijs dan één
 * getal uit het gevraagde jaar. Ten tweede is een verschil tussen twee getallen
 * over twee jaren geen tegenspraak maar groei — dat als "bronnen spreken elkaar
 * tegen" presenteren stuurt de reviewer op zoek naar een fout die er niet is.
 */
export function onderzoeksadvies(
  items,
  {onderzoekspaden = [], gevraagdJaar = null} = {},
) {
  const bronnen = (items || []).filter((item) => item.status !== "afgewezen");
  if (!bronnen.length) {
    const mislukt = onderzoekspaden.filter((pad) => pad.status === "mislukt");
    if (mislukt.length) {
      return {
        kop: "Geen bronnen, en het zoeken liep vast",
        toelichting:
          `${mislukt.length === 1 ? "Eén route" : `${mislukt.length} routes`} `
          + "kon technisch niet worden uitgevoerd, dus „niets gevonden” is "
          + "hier geen conclusie. Opnieuw zoeken is de moeite waard.",
        toon: "fout",
        letOp: mislukt.map((pad) => `${pad.route}: ${pad.statusreden || pad.status}`),
      };
    }
    return {
      kop: "Geen bruikbare bron gevonden",
      toelichting:
        "Er is niets openbaars gevonden waarop een WP-getal te baseren valt. "
        + "Voeg zelf een bron toe of zet deze vestiging op de bellijst.",
      toon: "aandacht",
      letOp: [],
    };
  }

  const gekozen = bronnen.find((item) => item.status === "geaccepteerd");
  const metWp = bronnen.filter(
    (item) => item.wp_gevonden != null && item.eenheid === "werkzame_personen",
  );
  const waarden = [...new Set(metWp.map((item) => item.wp_gevonden))];
  const letOp = [];

  // Voorbehouden bij het sterkste bewijs, niet bij de hele stapel: de reviewer
  // beslist op de bovenste kaart.
  const leidend = gekozen || metWp[0] || bronnen[0];
  if (leidend) {
    if (leidend.identity_class === "mismatch") {
      letOp.push("De sterkste bron lijkt bij een ander bedrijf te horen.");
    } else if (!["exact_entity", "same_brand_or_group"].includes(leidend.identity_class)) {
      letOp.push("Van de sterkste bron is niet vastgesteld dat het dit bedrijf is.");
    }
    if (["nederland", "concern", "instelling"].includes(leidend.scope_class)) {
      letOp.push("Het cijfer geldt breder dan deze vestiging.");
    }
    // Dezelfde grens als de chip op de bronkaart (`bronwaarschuwingen`), zodat
    // het oordeel boven de lijst niet iets anders zegt dan de kaart eronder.
    const leidendJaar = bronjaar(leidend)?.jaar ?? null;
    if (gevraagdJaar != null && leidendJaar != null && leidendJaar < gevraagdJaar) {
      letOp.push(
        `Het sterkste cijfer komt uit ${leidendJaar}.`,
      );
    }
  }
  if (bronnen.some((item) => item.eenheid === "fte") && !metWp.length) {
    letOp.push("Er is alleen een FTE-cijfer; FTE is geen WP.");
  }
  if (metWp.length && metWp.every((item) => !item.bewijsfragment)) {
    letOp.push("Geen enkel getal is met een citaat onderbouwd.");
  }

  if (gekozen) {
    return {
      kop: gekozen.wp_gevonden != null
        ? `Bron gekozen: ${gekozen.wp_gevonden} WP`
        : "Bron gekozen",
      toelichting: "Je hebt deze vestiging al beoordeeld.",
      toon: "gekozen",
      letOp,
    };
  }

  const jaren = [...new Set(
    metWp.map((item) => bronjaar(item)?.jaar).filter((jaar) => jaar != null),
  )];
  const nieuwste = jaren.length ? Math.max(...jaren) : null;

  if (waarden.length === 1 && metWp.length >= 2) {
    if (jaren.length > 1) {
      // Hetzelfde getal over verschillende jaren is zwakker bewijs, geen
      // sterker: waarschijnlijk heeft één bron de andere overgeschreven, of
      // staat er ergens een verouderd cijfer.
      return {
        kop: `${metWp.length} bronnen noemen ${waarden[0]} WP, maar over `
          + `verschillende jaren (${[...jaren].sort().join(", ")})`,
        toelichting:
          "Mogelijk heeft één bron de andere overgenomen. "
          + `Kies de bron die het dichtst bij ${peiljaarnaam(gevraagdJaar)} ligt.`,
        toon: "aandacht",
        letOp,
      };
    }
    return {
      kop: `${metWp.length} bronnen noemen hetzelfde aantal: ${waarden[0]} WP`
        + (nieuwste ? ` (${nieuwste})` : ""),
      toelichting:
        "Dat is de sterkste bevestiging die deze werkbank kan geven — "
        + "onafhankelijke bronnen die op hetzelfde getal uitkomen.",
      toon: "neutraal",
      letOp,
    };
  }
  if (waarden.length > 1) {
    // Zijn de getallen van verschillende jaren, dan is dit geen tegenspraak.
    const perWaarde = waarden.map((waarde) => {
      const bron = metWp.find((item) => item.wp_gevonden === waarde);
      const jaar = bronjaar(bron)?.jaar ?? null;
      return {waarde, jaar};
    });
    const gedateerd = perWaarde.filter((item) => item.jaar != null);
    const ongedateerd = perWaarde.filter((item) => item.jaar == null);
    // Zonder jaartallen blijft de compacte opsomming staan ("47 en 52 WP");
    // pas als er een jaar bij hoort krijgt elk getal zijn eigen achtervoegsel.
    const beschrijving = gedateerd.length
      ? perWaarde
        .map((item) => `${item.waarde} WP${item.jaar ? ` (${item.jaar})` : ""}`)
        .join(" en ")
      : `${waarden.join(" en ")} WP`;
    const jarenVanWaarden = [...new Set(gedateerd.map((item) => item.jaar))];
    if (jarenVanWaarden.length >= 2) {
      // Een deel van het verschil is uit de tijd te verklaren, dus "tegenspraak"
      // is hier het verkeerde woord. De nieuwste komt vooraan te staan: dat is
      // het cijfer waar de reviewer meestal naartoe wil.
      const nieuwsteBron = gedateerd
        .slice()
        .sort((a, b) => b.jaar - a.jaar)[0];
      return {
        kop: waarden.length > 2
          ? `${waarden.length} verschillende getallen — nieuwste: `
            + `${nieuwsteBron.waarde} WP (${nieuwsteBron.jaar})`
          : `Verschillende peilmomenten: ${beschrijving}`,
        toelichting:
          "Verschillende jaren; dit kan groei zijn. "
          + `Neem het cijfer dat het dichtst bij ${peiljaarnaam(gevraagdJaar)} ligt.`,
        toon: "aandacht",
        letOp,
      };
    }
    // Geen uitspraak over de jaren hier. Deze tak is juist de restcategorie:
    // gelijke jaren, of een getal zonder jaar. "Over hetzelfde jaar" was daar
    // een aanname die de kaart zelf weersprak zodra er een ongedateerd getal
    // tussen stond. Hoe meer de kaart beweert, hoe eerder ze ernaast zit.
    return {
      kop: `Bronnen spreken elkaar tegen: ${beschrijving}`,
      toelichting: "Controleer de bronnen handmatig.",
      toon: "aandacht",
      letOp,
    };
  }
  if (metWp.length === 1) {
    const bron = metWp[0];
    const jaar = bronjaar(bron)?.jaar ?? null;
    return {
      kop: `Eén bron met een getal: ${bron.wp_gevonden} WP`
        + (jaar ? ` (${jaar})` : ""),
      toelichting: bron.bewijsfragment
        ? "Er is één getal, met een citaat erbij. Controleer het citaat en de scope."
        : "Er is één getal, maar zonder citaat. Open de bron om het te verifiëren.",
      toon: bron.bewijsfragment ? "neutraal" : "aandacht",
      letOp,
    };
  }

  const telopdrachten = bronnen.filter(
    (item) => item.validaties?.naamlijst_telling_aan_reviewer,
  );
  if (telopdrachten.length) {
    return {
      kop: "Een namenlijst gevonden, geen telling",
      toelichting:
        "Het afgeleide aantal is ingetrokken omdat de lijst niet het "
        + "personeelsbestand van deze vestiging is. Tel zelf op de bron.",
      toon: "aandacht",
      letOp,
    };
  }
  const formeel = bronnen.filter(
    (item) => FORMELE_DOCUMENTTYPEN.has(item.documenttype),
  );
  if (formeel.length) {
    return {
      kop: `${formeel.length === 1 ? "Een formeel document" : `${formeel.length} formele documenten`}, maar geen getal`,
      toelichting:
        "De documenten zijn er wel; er is geen personeelsgetal uit gelezen. "
        + "Doorzoek ze op medewerkers, personeel, werknemers en fte.",
      toon: "aandacht",
      letOp,
    };
  }
  return {
    kop: `${bronnen.length === 1 ? "Eén bron" : `${bronnen.length} bronnen`}, geen personeelsgetal`,
    toelichting:
      "Er is context gevonden, maar geen aantal werkzame personen. Bekijk of "
      + "een van de bronnen naar een sterkere primaire bron verwijst.",
    toon: "aandacht",
    letOp,
  };
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
    // Terugval voor kandidaten van vóór de DUO-tak in `_menselijke_waarde`;
    // dezelfde strekking, zodat oude en nieuwe runs niet anders lezen.
    const codes = (candidate.raw_data?.instellingscodes || []).join(", ");
    return {
      rol: "duo_personeelsbron",
      label: "DUO-personeelscijfer",
      actie: candidate.wp_gevonden == null
        ? `Open het DUO-bestand (Excel) en beoordeel welke instellingscode${codes ? ` (${codes})` : ""} bij deze vestiging hoort; de waarden zijn bewust niet opgeteld.`
        : `Open het DUO-bestand (Excel)${codes ? ` en zoek instellingscode ${codes}` : ""}. DUO telt onderwijspersoneel per instelling, niet per locatie.`,
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
  // Geen chip meer over het verslagjaar. Die zei hetzelfde als de regel
  // Verslagjaar bovenin ("2024 — gevraagd is 2025"), maar in andere woorden en
  // op een andere hoogte op de kaart. Eén feit hoort op één plek te staan;
  // wie tien kaarten langsloopt moet zijn oog niet hoeven verplaatsen.
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
