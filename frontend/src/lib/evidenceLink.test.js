import {describe, expect, it} from "vitest";
import {bewijsUrl} from "./evidenceLink.js";

describe("bewijsUrl", () => {
  it("geeft niets terug zonder bron", () => {
    expect(bewijsUrl(null)).toEqual({soort: null, url: null, kanInbedden: false});
    expect(bewijsUrl({url: ""})).toEqual({soort: null, url: null, kanInbedden: false});
  });

  it("bouwt een insluitbare pdf.js-URL met pagina en zoekterm", () => {
    const resultaat = bewijsUrl({
      url: "https://example.test/jaarverslag.pdf",
      bron_pagina: 14,
      bewijsfragment: "47 medewerkers in dienst",
    });
    expect(resultaat.soort).toBe("pdf");
    expect(resultaat.kanInbedden).toBe(true);
    expect(resultaat.url).toContain("/pdfjs/web/viewer.html");
    expect(resultaat.url).toContain("page=14");
    expect(resultaat.url).toContain("search=");
    expect(resultaat.url).toContain("#page=14&search=47%20medewerkers%20in%20dienst&phrase=true");
    expect(resultaat.url.split("#")[0]).not.toContain("phrase=");
  });

  it("herkent een pdf ook met queryparameters achter de extensie", () => {
    expect(bewijsUrl({url: "https://example.test/verslag.pdf?v=2"}).soort)
      .toBe("pdf");
  });

  it("bouwt voor html een insluitbare leesweergave-URL met citaat en anker", () => {
    const resultaat = bewijsUrl({
      url: "https://example.test/over-ons",
      bewijsfragment: "47 medewerkers in dienst",
    }, "mijn-token");
    expect(resultaat.soort).toBe("html");
    expect(resultaat.kanInbedden).toBe(true);
    expect(resultaat.url).toContain("/research/bron-pagina");
    expect(resultaat.url).toContain("citaat=47");
    expect(resultaat.url).toContain("token=mijn-token");
    expect(resultaat.url).toContain("#citaat");
  });

  it("bouwt voor html zonder citaat toch een insluitbare URL, zonder anker", () => {
    const resultaat = bewijsUrl({url: "https://example.test/over-ons"});
    expect(resultaat.soort).toBe("html");
    expect(resultaat.kanInbedden).toBe(true);
    expect(resultaat.url).not.toContain("#citaat");
  });
});
