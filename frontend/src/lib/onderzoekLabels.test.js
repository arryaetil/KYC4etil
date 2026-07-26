import {describe, expect, it} from "vitest";
import {
  bereikLabel,
  bronwaarschuwingen,
  brontypeLabel,
  identiteitLabel,
  menselijkeWaarde,
  monitoringStatus,
  organisatieStatus,
} from "./onderzoekLabels.js";

describe("monitoringStatus", () => {
  it("meldt een mislukte controle met fout-toon", () => {
    const status = monitoringStatus({fout: "timeout"});
    expect(status).toEqual({
      sleutel: "mislukt", label: "Controle mislukt", toon: "fout",
    });
  });

  it("meldt een nieuwe vondst met aandacht-toon", () => {
    const status = monitoringStatus({
      nieuwe_bevinding: true, laatste_bron_url: "https://x.nl/jaar.pdf",
    });
    expect(status).toEqual({
      sleutel: "nieuwe_vondst", label: "Nieuwe vondst", toon: "aandacht",
    });
  });

  it("meldt een gevonden jaarverslag neutraal, niet als gekozen bron", () => {
    const status = monitoringStatus({laatste_bron_url: "https://x.nl/jaar.pdf"});
    expect(status).toEqual({
      sleutel: "gevonden", label: "Jaarverslag gevonden", toon: "neutraal",
    });
    expect(status.toon).not.toBe("gekozen");
  });

  it("meldt aandacht als er niets is gevonden", () => {
    expect(monitoringStatus({})).toEqual({
      sleutel: "niet_gevonden",
      label: "Geen jaarverslag gevonden",
      toon: "aandacht",
    });
    expect(monitoringStatus(null).sleutel).toBe("niet_gevonden");
  });

  it("geeft een fout voorrang op een bevinding en op een gevonden bron", () => {
    expect(monitoringStatus({
      fout: "timeout",
      nieuwe_bevinding: true,
      laatste_bron_url: "https://x.nl/jaar.pdf",
    }).sleutel).toBe("mislukt");
  });

  it("geeft een nieuwe bevinding voorrang op een reeds gevonden bron", () => {
    expect(monitoringStatus({
      nieuwe_bevinding: true, laatste_bron_url: "https://x.nl/jaar.pdf",
    }).sleutel).toBe("nieuwe_vondst");
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
  it("waarschuwt bij een FTE-getal", () => {
    const labels = bronwaarschuwingen({eenheid: "fte", wp_gevonden: 47})
      .map((item) => item.label);
    expect(labels).toContain("FTE — geen WP");
  });

  it("waarschuwt bij een afwijkend verslagjaar", () => {
    const labels = bronwaarschuwingen({verslagjaar: 2024, gevraagd_jaar: 2025})
      .map((item) => item.label);
    expect(labels).toContain("Ander verslagjaar");
  });

  it("waarschuwt niet bij een gelijk verslagjaar", () => {
    const labels = bronwaarschuwingen({
      verslagjaar: 2025, gevraagd_jaar: 2025, wp_gevonden: 47,
      eenheid: "werkzame_personen",
    }).map((item) => item.label);
    expect(labels).toEqual([]);
  });

  it("waarschuwt als er geen getal is gevonden", () => {
    const labels = bronwaarschuwingen({wp_gevonden: null})
      .map((item) => item.label);
    expect(labels).toContain("Geen getal gevonden");
  });

  it("vertaalt bekende backend-waarschuwingen naar Nederlands", () => {
    const labels = bronwaarschuwingen({
      wp_gevonden: 47,
      eenheid: "werkzame_personen",
      waarschuwingen: [
        "geen_concreet_wp_bewijs",
        "getal_zonder_bewijsfragment",
        "alleen_context_geen_wp_voorstel",
      ],
    }).map((item) => item.label);
    expect(labels).toContain("Geen hard WP-bewijs");
    expect(labels).toContain("Getal zonder citaat");
    expect(labels).toContain("Alleen context, geen WP-getal");
  });

  it("onderdrukt fte_geen_wp, want de FTE-chip zegt dat al", () => {
    const labels = bronwaarschuwingen({
      wp_gevonden: 47, eenheid: "fte", waarschuwingen: ["fte_geen_wp"],
    }).map((item) => item.label);
    expect(labels).toEqual(["FTE — geen WP"]);
  });

  it("onderdrukt afwijkend_verslagjaar, want het jaarsignaal zegt dat al", () => {
    const labels = bronwaarschuwingen({
      wp_gevonden: 47,
      eenheid: "werkzame_personen",
      verslagjaar: 2024,
      gevraagd_jaar: 2025,
      waarschuwingen: ["afwijkend_verslagjaar"],
    }).map((item) => item.label);
    expect(labels).toEqual(["Ander verslagjaar"]);
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
      wp_gevonden: null,
      eenheid: "werkzame_personen",
      waarschuwingen: ["geen_concreet_wp_bewijs", "geen_concreet_wp_bewijs"],
    }).map((item) => item.label);
    expect(labels).toEqual(["Geen getal gevonden", "Geen hard WP-bewijs"]);
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
});
