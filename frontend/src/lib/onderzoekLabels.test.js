import {describe, expect, it} from "vitest";
import {
  bedrijfRelatie,
  bereikLabel,
  bereikRelatie,
  bewijsRelatie,
  bronjaarLabel,
  bronwaarschuwingen,
  brontypeLabel,
  identiteitLabel,
  menselijkeWaarde,
  monitoringStatus,
  onderzoeksadvies,
  peilmomentRelatie,
  organisatieStatus,
  primaireConclusie,
  telopdracht,
} from "./onderzoekLabels.js";

describe("monitoringStatus", () => {
  it("meldt een mislukte controle met fout-toon", () => {
    const status = monitoringStatus({fout: "timeout"});
    expect(status).toEqual({
      sleutel: "mislukt", label: "Controle mislukt", toon: "fout",
    });
  });

  it("noemt het verslag over het doeljaar nieuw", () => {
    expect(monitoringStatus({
      jaarstatus: "actueel", doeljaar: 2025, verslagjaar: 2025,
      laatste_bron_url: "https://x.nl/jaar-2025.pdf",
    })).toEqual({
      sleutel: "actueel", label: "Nieuw — verslag 2025", toon: "neutraal",
    });
  });

  it("noemt een ouder verslag met zijn eigen jaartal", () => {
    expect(monitoringStatus({
      jaarstatus: "verouderd", doeljaar: 2025, verslagjaar: 2023,
      laatste_bron_url: "https://x.nl/jaar-2023.pdf",
    })).toEqual({
      sleutel: "verouderd", label: "Ouder — verslag 2023", toon: "aandacht",
    });
  });

  it("meldt een bron zonder herkenbaar jaartal als zodanig", () => {
    expect(monitoringStatus({
      jaarstatus: "verouderd", doeljaar: 2025,
      laatste_bron_url: "https://x.nl/jaarverslagsite/",
    })).toEqual({
      sleutel: "verouderd", label: "Ouder — jaartal onbekend", toon: "aandacht",
    });
  });

  it("meldt aandacht als er niets is gevonden", () => {
    expect(monitoringStatus({jaarstatus: "ontbreekt"})).toEqual({
      sleutel: "ontbreekt",
      label: "Niet gevonden",
      toon: "aandacht",
    });
    expect(monitoringStatus(null).sleutel).toBe("ontbreekt");
  });

  it("geeft nooit de gekozen-toon: monitoring kiest geen bron", () => {
    expect(monitoringStatus({
      jaarstatus: "actueel", doeljaar: 2025, verslagjaar: 2025,
      laatste_bron_url: "https://x.nl/jaar.pdf",
    }).toon).not.toBe("gekozen");
  });

  it("geeft een fout voorrang op elke jaarstatus", () => {
    expect(monitoringStatus({
      fout: "timeout",
      jaarstatus: "actueel",
      laatste_bron_url: "https://x.nl/jaar.pdf",
    }).sleutel).toBe("mislukt");
  });

  it("laat een verandering sinds de vorige ronde de jaarstatus niet sturen", () => {
    // Op de watchlist van 10-08-2026 waren de enige twee organisaties met
    // nieuwe_bevinding allebei van verslagjaar 2023; als hoofdstatus zette
    // dat juist de verouderde vondsten bovenaan.
    expect(monitoringStatus({
      nieuwe_bevinding: true, jaarstatus: "verouderd",
      doeljaar: 2025, verslagjaar: 2023,
      laatste_bron_url: "https://x.nl/jaar-2023.pdf",
    }).sleutel).toBe("verouderd");
  });

  it("valt terug op bron-aanwezigheid zonder jaarstatus in de respons", () => {
    expect(monitoringStatus({
      laatste_bron_url: "https://x.nl/jaar.pdf",
    }).sleutel).toBe("verouderd");
    expect(monitoringStatus({}).sleutel).toBe("ontbreekt");
  });
});

describe("organisatieStatus", () => {
  it("meldt een niet-gestart onderzoek", () => {
    expect(organisatieStatus({research_status: "niet_gestart"}).label)
      .toBe("Nog niet onderzocht");
  });

  it("meldt een lopend onderzoek", () => {
    expect(organisatieStatus({research_status: "running"}).label)
      .toBe("Onderzoek loopt");
    expect(organisatieStatus({research_status: "pending"}).label)
      .toBe("Onderzoek loopt");
  });

  it("geeft een gekozen bron voorrang op de resultaatstatus", () => {
    const status = organisatieStatus({
      research_status: "completed",
      research_resultaat_status: "review_nodig",
      research_review_status: "geaccepteerd",
    });
    expect(status.label).toBe("Bron gekozen");
    expect(status.toon).toBe("gekozen");
  });

  it("meldt te beoordelen bij voorgestelde kandidaten", () => {
    const status = organisatieStatus({
      research_status: "completed",
      research_resultaat_status: "review_nodig",
    });
    expect(status.label).toBe("Te beoordelen");
    expect(status.sleutel).toBe("te_beoordelen");
  });

  it("meldt geen bron gevonden met aandacht-toon", () => {
    const status = organisatieStatus({
      research_status: "completed",
      research_resultaat_status: "niet_gevonden",
    });
    expect(status.label).toBe("Geen bron gevonden");
    expect(status.toon).toBe("aandacht");
  });

  it("onderscheidt een technisch onvolledige run van een afgeronde", () => {
    // De supervisor zet `technisch_onvolledig` als een verplichte route
    // technisch mislukte. Dat viel door naar "Onderzoek afgerond" — neutraal en
    // buiten elk filter, terwijl "niets gevonden" hier geen conclusie is.
    const status = organisatieStatus({
      research_status: "completed",
      research_resultaat_status: "technisch_onvolledig",
    });
    expect(status.sleutel).toBe("onvolledig");
    expect(status.label).toBe("Onderzoek onvolledig");
    expect(status.toon).toBe("aandacht");
  });

  it("meldt een mislukt onderzoek met fout-toon", () => {
    const status = organisatieStatus({research_status: "error"});
    expect(status.label).toBe("Mislukt");
    expect(status.toon).toBe("fout");
  });
});

describe("identiteitLabel", () => {
  it("vertaalt elke bekende klasse naar Nederlands", () => {
    expect(identiteitLabel("exact_entity").label).toBe("Dit bedrijf");
    expect(identiteitLabel("same_brand_or_group").label).toBe("Zelfde groep");
    expect(identiteitLabel("possible_match").label).toBe("Mogelijk ander bedrijf");
    expect(identiteitLabel("unknown").label).toBe("Mogelijk ander bedrijf");
    expect(identiteitLabel("mismatch").label).toBe("Ander bedrijf");
  });

  it("geeft een mismatch de fout-toon en een exacte match neutraal", () => {
    expect(identiteitLabel("mismatch").toon).toBe("fout");
    expect(identiteitLabel("exact_entity").toon).toBe("neutraal");
    expect(identiteitLabel("possible_match").toon).toBe("aandacht");
  });

  it("valt terug op onbekend zonder waarde", () => {
    expect(identiteitLabel(null).label).toBe("Mogelijk ander bedrijf");
  });
});

describe("bereikLabel", () => {
  it("vertaalt elke bekende scope naar Nederlands", () => {
    expect(bereikLabel("vestiging").label).toBe("Deze vestiging");
    expect(bereikLabel("limburg").label).toBe("Limburg");
    expect(bereikLabel("nederland").label).toBe("Heel Nederland");
    expect(bereikLabel("concern").label).toBe("Hele concern");
    expect(bereikLabel("unknown").label).toBe("Onbekend bereik");
  });

  it("markeert een te ruime scope als aandacht", () => {
    expect(bereikLabel("vestiging").toon).toBe("neutraal");
    expect(bereikLabel("limburg").toon).toBe("neutraal");
    expect(bereikLabel("nederland").toon).toBe("aandacht");
    expect(bereikLabel("concern").toon).toBe("aandacht");
  });
});

describe("brontypeLabel", () => {
  it("vertaalt bekende brontypes", () => {
    expect(brontypeLabel("officiele_website")).toBe("Officiële website");
    expect(brontypeLabel("jaarverslag")).toBe("Jaarverslag");
    expect(brontypeLabel("media")).toBe("Recente media");
    expect(brontypeLabel("handmatig")).toBe("Handmatig toegevoegd");
  });

  it("valt terug op een neutrale omschrijving", () => {
    expect(brontypeLabel(null)).toBe("Openbare bron");
  });
});

describe("bronwaarschuwingen", () => {
  it("waarschuwt niet apart bij een FTE-getal — dat zegt de Bewijs-regel al", () => {
    const labels = bronwaarschuwingen({eenheid: "fte", wp_gevonden: 47})
      .map((item) => item.label);
    expect(labels).toEqual([]);
  });

  it("maakt zichtbaar dat DUO-personen niet automatisch de WP-definitie zijn", () => {
    const labels = bronwaarschuwingen({
      eenheid: "onderwijspersoneel_personen",
      wp_gevonden: 35,
      waarschuwingen: ["duo_definitie_wijkt_af_van_wp"],
    }).map((item) => item.label);
    expect(labels).toContain("DUO-definitie — controleer tegen WP");
  });

  it("maakt zichtbaar dat een WP-getal uit een namenlijst is geteld, niet letterlijk genoemd", () => {
    const labels = bronwaarschuwingen({
      wp_gevonden: 4,
      eenheid: "werkzame_personen",
      waarschuwingen: ["wp_afgeleid_uit_naamlijst"],
    }).map((item) => item.label);
    expect(labels).toContain("Geteld uit namenlijst");
  });

  it("noemt bij een ouder verslag beide jaartallen", () => {
    const labels = bronwaarschuwingen({
      verslagjaar: 2024, gevraagd_jaar: 2025, documenttype: "jaarverslag",
    })
      .map((item) => item.label);
    expect(labels).toContain("Verslag 2024, gevraagd is 2025");
  });

  it("zwijgt over een verslag dat nieuwer is dan gevraagd", () => {
    // Komt uit een publicatiedatum in de URL en is geen probleem dat de
    // reviewer moet oplossen.
    const labels = bronwaarschuwingen({
      verslagjaar: 2026, gevraagd_jaar: 2025, documenttype: "jaarverslag",
    }).map((item) => item.label);
    expect(labels).toEqual([]);
  });

  it("zegt niets over een verslagjaar bij een website of nieuwsartikel", () => {
    // Een teampagina is geen verslag over 2023, dus "dit verslag loopt achter"
    // is daar een zinloze mededeling. Het jaar staat als peilmoment op de kaart.
    const labels = bronwaarschuwingen({
      verslagjaar: 2023, gevraagd_jaar: 2025,
      brontype: "officiele_website", documenttype: "teampagina",
    }).map((item) => item.label);
    expect(labels).toEqual([]);
  });

  it("waarschuwt niet bij een gelijk verslagjaar", () => {
    const labels = bronwaarschuwingen({
      verslagjaar: 2025, gevraagd_jaar: 2025, wp_gevonden: 47,
      eenheid: "werkzame_personen", documenttype: "jaarverslag",
    }).map((item) => item.label);
    expect(labels).toEqual([]);
  });

  it("waarschuwt niet apart als er geen getal is gevonden — dat zegt de Bewijs-regel al", () => {
    const labels = bronwaarschuwingen({wp_gevonden: null})
      .map((item) => item.label);
    expect(labels).toEqual([]);
  });

  it("onderdrukt geen_concreet_wp_bewijs/getal_zonder_bewijsfragment/alleen_context_geen_wp_voorstel — de Bewijs-regel dekt dit al", () => {
    const labels = bronwaarschuwingen({
      wp_gevonden: 47,
      eenheid: "werkzame_personen",
      waarschuwingen: [
        "geen_concreet_wp_bewijs",
        "getal_zonder_bewijsfragment",
        "alleen_context_geen_wp_voorstel",
      ],
    }).map((item) => item.label);
    expect(labels).toEqual([]);
  });

  it("onderdrukt fte_geen_wp — de Bewijs-regel zegt dat al", () => {
    const labels = bronwaarschuwingen({
      wp_gevonden: 47, eenheid: "fte", waarschuwingen: ["fte_geen_wp"],
    }).map((item) => item.label);
    expect(labels).toEqual([]);
  });

  it("onderdrukt afwijkend_verslagjaar, want het jaarsignaal zegt dat al", () => {
    // Zowel de batchflow (source_reviewer) als de monitoring zet deze sleutel
    // bij een ouder verslag; zonder onderdrukking staat de melding er twee keer.
    const labels = bronwaarschuwingen({
      wp_gevonden: 47,
      eenheid: "werkzame_personen",
      verslagjaar: 2024,
      gevraagd_jaar: 2025,
      documenttype: "jaarverslag",
      waarschuwingen: ["afwijkend_verslagjaar"],
    }).map((item) => item.label);
    expect(labels).toEqual(["Verslag 2024, gevraagd is 2025"]);
  });

  it("onderdrukt scope_breder_dan_vestiging, want de bereikchip zegt dat al", () => {
    const labels = bronwaarschuwingen({
      wp_gevonden: 47,
      eenheid: "werkzame_personen",
      waarschuwingen: ["scope_breder_dan_vestiging"],
    }).map((item) => item.label);
    expect(labels).toEqual([]);
  });

  it("toont recent_actualiteitssignaal niet: dat is een pluspunt, geen waarschuwing", () => {
    const labels = bronwaarschuwingen({
      wp_gevonden: 47,
      eenheid: "werkzame_personen",
      waarschuwingen: ["recent_actualiteitssignaal"],
    }).map((item) => item.label);
    expect(labels).toEqual([]);
  });

  it("maakt een onbekende sleutel cosmetisch leesbaar met aandacht-toon", () => {
    const items = bronwaarschuwingen({
      wp_gevonden: 47,
      eenheid: "werkzame_personen",
      waarschuwingen: ["een_nieuwe_backend_sleutel"],
    });
    expect(items).toEqual([
      {label: "een nieuwe backend sleutel", toon: "aandacht"},
    ]);
  });

  it("toont hetzelfde signaal nooit twee keer", () => {
    const labels = bronwaarschuwingen({
      wp_gevonden: 47,
      eenheid: "werkzame_personen",
      waarschuwingen: ["een_nieuwe_backend_sleutel", "een_nieuwe_backend_sleutel"],
    }).map((item) => item.label);
    expect(labels).toEqual(["een nieuwe backend sleutel"]);
  });
});

describe("bedrijfRelatie", () => {
  it("meldt een overeenkomst voor exacte en groepsidentiteit", () => {
    expect(bedrijfRelatie("exact_entity").label).toBe("Komt overeen");
    expect(bedrijfRelatie("same_brand_or_group").label).toBe("Komt overeen");
  });

  it("meldt een mismatch als afwijkend, met fout-toon", () => {
    expect(bedrijfRelatie("mismatch")).toEqual({label: "Afwijkend", toon: "fout"});
  });

  it("meldt onzekere identiteit als nog niet vastgesteld", () => {
    expect(bedrijfRelatie("possible_match").label).toBe("Nog niet vastgesteld");
    expect(bedrijfRelatie(null).label).toBe("Nog niet vastgesteld");
  });
});

describe("bereikRelatie", () => {
  it("meldt vestiging en Limburg als vastgesteld", () => {
    expect(bereikRelatie("vestiging").label).toBe("Vastgesteld — deze vestiging");
    expect(bereikRelatie("limburg").label).toBe("Vastgesteld — Limburg");
    expect(bereikRelatie("vestiging").toon).toBe("neutraal");
  });

  it("meldt een landelijk of concerncijfer als breder dan de vestiging", () => {
    expect(bereikRelatie("nederland").label).toBe("Breder dan deze vestiging");
    expect(bereikRelatie("concern").toon).toBe("aandacht");
  });

  it("meldt een onbekend bereik als nog niet vastgesteld", () => {
    expect(bereikRelatie("unknown").label).toBe("Nog niet vastgesteld");
    expect(bereikRelatie(null).label).toBe("Nog niet vastgesteld");
  });
});

describe("bewijsRelatie", () => {
  it("meldt een WP-getal met citaat neutraal", () => {
    expect(bewijsRelatie({
      wp_gevonden: 47, eenheid: "werkzame_personen", bewijsfragment: "47 medewerkers",
    })).toEqual({label: "47 WP, met citaat", toon: "neutraal"});
  });

  it("meldt een WP-getal zonder citaat als aandacht", () => {
    expect(bewijsRelatie({wp_gevonden: 47, eenheid: "werkzame_personen"}).toon)
      .toBe("aandacht");
  });

  it("meldt een FTE-getal expliciet als geen WP-getal", () => {
    expect(bewijsRelatie({wp_gevonden: 47, eenheid: "fte"}).label)
      .toBe("47 FTE — geen WP-getal");
  });

  it("meldt een teampagina als nog niet geteld", () => {
    expect(bewijsRelatie({documenttype: "teampagina", wp_gevonden: null}).label)
      .toBe("Teamoverzicht gevonden, nog niet geteld");
  });

  it("meldt alleen context wanneer er wel een citaat maar geen getal is", () => {
    expect(bewijsRelatie({wp_gevonden: null, bewijsfragment: "noemt het team"}).label)
      .toBe("Alleen context, geen WP-getal");
  });

  it("meldt geen medewerkerstal zonder getal en zonder citaat", () => {
    expect(bewijsRelatie({wp_gevonden: null}).label)
      .toBe("Geen medewerkerstal uitgelezen");
  });
});

describe("primaireConclusie", () => {
  it("meldt een mismatch als eerste zin, zonder vervolgzin over bereik", () => {
    const conclusie = primaireConclusie({identity_class: "mismatch"});
    expect(conclusie.hoofd).toBe("Deze bron lijkt bij een ander bedrijf te horen.");
  });

  it("meldt een bruikbaar WP-getal met citaat", () => {
    const conclusie = primaireConclusie({
      identity_class: "exact_entity",
      wp_gevonden: 47,
      eenheid: "werkzame_personen",
      bewijsfragment: "47 medewerkers",
      scope_class: "vestiging",
    });
    expect(conclusie.hoofd).toBe("Bruikbaar WP-getal gevonden, met citaat.");
    expect(conclusie.vervolg).toBeNull();
  });

  it("voegt een vervolgzin toe wanneer het bereik nog onbekend is", () => {
    const conclusie = primaireConclusie({
      identity_class: "exact_entity",
      wp_gevonden: null,
      scope_class: "unknown",
    });
    expect(conclusie.hoofd).toBe(
      "Juiste bedrijfsbron gevonden, maar nog geen medewerkerstal uitgelezen.",
    );
    expect(conclusie.vervolg).toBe(
      "De locatie waarop deze informatie betrekking heeft is nog niet vastgesteld.",
    );
  });

  it("meldt een landelijk/concerncijfer als breder dan de vestiging", () => {
    const conclusie = primaireConclusie({
      identity_class: "exact_entity",
      wp_gevonden: 4900,
      eenheid: "werkzame_personen",
      bewijsfragment: "de groep telt 4.900 medewerkers",
      scope_class: "concern",
    });
    expect(conclusie.vervolg).toBe("Dit cijfer geldt breder dan alleen deze vestiging.");
  });
});

describe("menselijkeWaarde", () => {
  it("maakt een lokaal citaat direct bruikbaar", () => {
    expect(menselijkeWaarde({
      wp_gevonden: 47,
      eenheid: "werkzame_personen",
      bewijsfragment: "Ons team telt 47 medewerkers.",
      scope_class: "vestiging",
    }).rol).toBe("direct_wp_bewijs");
  });

  it("presenteert een groepsgetal als onderzoekscontext", () => {
    const waarde = menselijkeWaarde({
      wp_gevonden: 4900,
      eenheid: "werkzame_personen",
      bewijsfragment: "De groep telt 4.900 medewerkers.",
      scope_class: "concern",
    });

    expect(waarde.rol).toBe("organisatieomvang");
    expect(waarde.actie).toContain("vestigingsuitsplitsing");
  });

  it("geeft een teamoverzicht een concrete handmatige vervolgstap", () => {
    const waarde = menselijkeWaarde({
      documenttype: "teampagina",
      wp_gevonden: null,
    });

    expect(waarde.label).toBe("Teamoverzicht");
    expect(waarde.actie).toContain("tel");
  });

  it("vraagt de reviewer zelf te tellen als de telling is ingetrokken", () => {
    const waarde = menselijkeWaarde({
      documenttype: "teampagina",
      wp_gevonden: null,
      validaties: {
        naamlijst_telling_aan_reviewer: {
          reden: "leidinggevendenlijst",
          afgeleid_aantal: 6,
          genoemde_namen: ["Robin Barkmeijer (CEO)", "Frank Van der Linden (COO)"],
        },
      },
    });

    expect(waarde.rol).toBe("telopdracht");
    expect(waarde.label).toBe("Tel de medewerkers zelf");
    expect(waarde.aantal_namen).toBe(2);
  });
});

describe("telopdracht", () => {
  it("geeft niets terug voor een gewone bron", () => {
    expect(telopdracht({wp_gevonden: 12})).toBeNull();
  });

  it("levert de namen zodat de reviewer ze naast de bron kan leggen", () => {
    const telling = telopdracht({
      validaties: {
        naamlijst_telling_aan_reviewer: {
          reden: "scope_buiten_vestiging",
          afgeleid_aantal: 3,
          genoemde_namen: ["Marc", "Mandy", "Nicole"],
        },
      },
    });

    expect(telling.afgeleidAantal).toBe(3);
    expect(telling.namen).toHaveLength(3);
    expect(telling.uitleg).toContain("breder dan deze vestiging");
  });

  it("legt bij een bestuurspagina uit dat het de leidinglaag betreft", () => {
    const telling = telopdracht({
      validaties: {
        naamlijst_telling_aan_reviewer: {reden: "leidinggevendenlijst"},
      },
    });

    expect(telling.uitleg).toContain("leidinglaag");
    expect(telling.namen).toEqual([]);
  });
});

describe("onderzoeksadvies", () => {
  const metGetal = (wp, extra = {}) => ({
    wp_gevonden: wp, eenheid: "werkzame_personen",
    bewijsfragment: `${wp} medewerkers`, identity_class: "exact_entity",
    scope_class: "vestiging", documenttype: "jaarverslag", status: "voorgesteld",
    ...extra,
  });

  it("noemt twee bronnen met hetzelfde getal de sterkste bevestiging", () => {
    const advies = onderzoeksadvies([metGetal(47), metGetal(47)]);
    expect(advies.kop).toBe("2 bronnen noemen hetzelfde aantal: 47 WP");
    expect(advies.toon).toBe("neutraal");
    expect(advies.letOp).toEqual([]);
  });

  it("meldt het als bronnen elkaar tegenspreken", () => {
    const advies = onderzoeksadvies([metGetal(47), metGetal(52)]);
    expect(advies.kop).toBe("Bronnen spreken elkaar tegen: 47 en 52 WP");
    expect(advies.toon).toBe("aandacht");
  });

  it("onderscheidt één getal met citaat van één zonder", () => {
    expect(onderzoeksadvies([metGetal(47)]).toon).toBe("neutraal");
    const zonder = onderzoeksadvies([metGetal(47, {bewijsfragment: null})]);
    expect(zonder.toon).toBe("aandacht");
    expect(zonder.letOp).toContain("Geen enkel getal is met een citaat onderbouwd.");
  });

  it("zegt dat er niets bruikbaars is als er geen bronnen zijn", () => {
    const advies = onderzoeksadvies([]);
    expect(advies.kop).toBe("Geen bruikbare bron gevonden");
    expect(advies.toon).toBe("aandacht");
  });

  it("noemt een vastgelopen route geen conclusie", () => {
    // "Niets gevonden" en "we konden niet kijken" zijn verschillende dingen.
    const advies = onderzoeksadvies([], {
      onderzoekspaden: [
        {route: "document", status: "mislukt", statusreden: "alle zoekopdrachten mislukten"},
      ],
    });
    expect(advies.kop).toBe("Geen bronnen, en het zoeken liep vast");
    expect(advies.toon).toBe("fout");
    expect(advies.letOp[0]).toContain("document");
  });

  it("meldt formele documenten zonder getal", () => {
    const advies = onderzoeksadvies([
      {documenttype: "jaarverslag", status: "voorgesteld", identity_class: "exact_entity"},
    ]);
    expect(advies.kop).toBe("Een formeel document, maar geen getal");
  });

  it("geeft alleen de gekozen-toon als de reviewer zelf koos", () => {
    const advies = onderzoeksadvies([metGetal(47, {status: "geaccepteerd"})]);
    expect(advies.kop).toBe("Bron gekozen: 47 WP");
    expect(advies.toon).toBe("gekozen");
    // Zonder keuze nooit groen: dat zou een menselijk oordeel suggereren.
    expect(onderzoeksadvies([metGetal(47), metGetal(47)]).toon).not.toBe("gekozen");
  });

  it("laat een afgewezen bron niet meetellen als bewijs", () => {
    const advies = onderzoeksadvies([
      metGetal(47, {status: "afgewezen"}),
      metGetal(52),
    ]);
    expect(advies.kop).toBe("Eén bron met een getal: 52 WP");
  });

  it("waarschuwt bij een concerncijfer en bij onbewezen identiteit", () => {
    const advies = onderzoeksadvies([
      metGetal(2400, {scope_class: "concern", identity_class: "possible_match"}),
    ]);
    expect(advies.letOp).toContain("Het cijfer geldt breder dan deze vestiging.");
    expect(advies.letOp).toContain(
      "Van de sterkste bron is niet vastgesteld dat het dit bedrijf is.",
    );
  });

  it("meldt FTE apart, want FTE is geen WP", () => {
    const advies = onderzoeksadvies([
      {wp_gevonden: 31, eenheid: "fte", documenttype: "jaarverslag",
       status: "voorgesteld", identity_class: "exact_entity"},
    ]);
    expect(advies.letOp).toContain("Er is alleen een FTE-cijfer; FTE is geen WP.");
  });

  it("houdt een ingetrokken namenlijst-telling een telopdracht", () => {
    const advies = onderzoeksadvies([
      {documenttype: "teampagina", status: "voorgesteld",
       identity_class: "exact_entity",
       validaties: {naamlijst_telling_aan_reviewer: {afgeleid_aantal: 12}}},
    ]);
    expect(advies.kop).toBe("Een namenlijst gevonden, geen telling");
  });
});

describe("bronjaarLabel", () => {
  it("noemt het verslagjaar bij een verslagbron", () => {
    expect(bronjaarLabel({verslagjaar: 2025, documenttype: "jaarverslag"}))
      .toBe("verslagjaar 2025");
  });

  it("noemt hetzelfde jaar bij een website een peilmoment", () => {
    // "verslagjaar" is bij een teampagina het verkeerde woord, maar het jaar
    // zelf moet de reviewer wel zien.
    expect(bronjaarLabel({
      verslagjaar: 2025, brontype: "officiele_website", documenttype: "teampagina",
    })).toBe("peilmoment 2025");
    expect(bronjaarLabel({
      brontype: "media", informatie_peilmoment: "2024",
    })).toBe("peilmoment 2024");
  });

  it("dateert een website zonder peilmoment op het jaar in de link", () => {
    // Het gat dat dit dicht: een nieuwsartikel zonder opgegeven peilmoment had
    // helemaal geen jaar op de kaart, terwijl de URL het jaartal draagt.
    expect(bronjaarLabel({
      brontype: "media", documenttype: "nieuwsartikel", jaar_uit_url: 2023,
    })).toBe("peilmoment 2023");
  });

  it("laat het jaar in de link voorgaan op het jaar uit de paginatekst", () => {
    // `verslagjaar` komt bij een website uit een jaartal ergens in de tekst,
    // met voorkeur voor het gevraagde jaar. De URL is het hardere signaal.
    expect(bronjaarLabel({
      brontype: "officiele_website", documenttype: "webpagina",
      verslagjaar: 2025, jaar_uit_url: 2021,
    })).toBe("peilmoment 2021");
  });

  it("laat een opgegeven peilmoment voorgaan op het jaar in de link", () => {
    expect(bronjaarLabel({
      brontype: "media", jaar_uit_url: 2023, informatie_peilmoment: "1 juni 2022",
    })).toBe("peilmoment 2022");
  });

  it("gebruikt het jaar in de link niet bij een verslagbron", () => {
    // Daar staat het verslagjaar al, en dat is de vaststelling.
    expect(bronjaarLabel({
      brontype: "jaarverslag", documenttype: "jaarverslag",
      verslagjaar: 2024, jaar_uit_url: 2025,
    })).toBe("verslagjaar 2024");
  });

  it("valt terug op het jaar uit het peilmoment", () => {
    expect(bronjaarLabel({informatie_peilmoment: "1 oktober 2025"}))
      .toBe("peilmoment 2025");
    expect(bronjaarLabel({informatie_peilmoment: "2024"})).toBe("peilmoment 2024");
  });

  it("noemt welk van de twee je ziet: ze kunnen verschillen", () => {
    // Een jaarverslag over 2025 met een stand per 1 oktober 2025; het
    // verslagjaar gaat voor, want dat is het jaar van de bron zelf.
    expect(bronjaarLabel({
      verslagjaar: 2025, documenttype: "jaarverslag",
      informatie_peilmoment: "1 oktober 2024",
    })).toBe("verslagjaar 2025");
  });

  it("zwijgt als er geen jaar bekend is", () => {
    expect(bronjaarLabel({})).toBe(null);
    expect(bronjaarLabel({informatie_peilmoment: "onbekend"})).toBe(null);
    expect(bronjaarLabel(null)).toBe(null);
  });
});

describe("peilmomentRelatie", () => {
  it("toont het peilmoment als het bekend is", () => {
    expect(peilmomentRelatie({informatie_peilmoment: "1 oktober 2025", wp_gevonden: 61}))
      .toEqual({label: "1 oktober 2025", toon: "neutraal"});
  });

  it("maakt een getal zonder datum expliciet zichtbaar", () => {
    // 87 websitebronnen in productie hebben een WP-getal en geen peilmoment; de
    // regel verdween dan, waardoor "geen datum" niet te onderscheiden was van
    // "hier is niet naar gekeken".
    const rij = peilmomentRelatie({wp_gevonden: 47, eenheid: "werkzame_personen"});
    expect(rij.toon).toBe("aandacht");
    expect(rij.label).toBe("Onbekend");
  });

  it("noemt de aanwijzing uit de bron, met waar die vandaan komt", () => {
    // "Onbekend" terwijl de URL /nieuws/2023/ is, is te weinig gezegd. Het
    // blijft toon "aandacht": dit dateert de bron, niet het getal.
    expect(peilmomentRelatie({wp_gevonden: 47, jaar_uit_url: 2023}))
      .toEqual({label: "2023 — jaar uit de link", toon: "aandacht"});
    expect(peilmomentRelatie({wp_gevonden: 47, verslagjaar: 2022}))
      .toEqual({label: "2022 — jaar uit de bron", toon: "aandacht"});
  });

  it("laat een echt peilmoment voorgaan op de aanwijzing", () => {
    expect(peilmomentRelatie({
      wp_gevonden: 47, informatie_peilmoment: "31 december 2024", jaar_uit_url: 2026,
    })).toEqual({label: "31 december 2024", toon: "neutraal"});
  });

  it("zwijgt als er geen getal is om te dateren", () => {
    expect(peilmomentRelatie({wp_gevonden: null})).toBe(null);
    expect(peilmomentRelatie({})).toBe(null);
  });
});
