import {describe, expect, it} from "vitest";
import {bekijkBewijs, bewijsUrl} from "./evidenceLink.js";

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

  it("bouwt voor html een tekstfragment dat niet insluitbaar is", () => {
    const resultaat = bewijsUrl({
      url: "https://example.test/over-ons",
      bewijsfragment: "47 medewerkers in dienst",
    });
    expect(resultaat.soort).toBe("html");
    expect(resultaat.kanInbedden).toBe(false);
    expect(resultaat.url).toContain("#:~:text=");
  });

  it("codeert koppeltekens en kommas die het tekstfragment zouden breken", () => {
    const resultaat = bewijsUrl({
      url: "https://example.test/over-ons",
      bewijsfragment: "ruim 47 medewerkers, full-time in dienst",
    });
    expect(resultaat.url).not.toMatch(/text=[^#]*[,-]/);
    expect(resultaat.url).toContain("%2D");
    expect(resultaat.url).toContain("%2C");
  });

  it("kort een lang citaat in op een woordgrens", () => {
    const lang = "Wij zijn een organisatie die inmiddels is uitgegroeid tot een "
      + "van de grootste werkgevers van de regio met veel medewerkers";
    const resultaat = bewijsUrl({
      url: "https://example.test/over-ons",
      bewijsfragment: lang,
    });
    const fragment = decodeURIComponent(
      resultaat.url.split("#:~:text=")[1].replaceAll("%2D", "-"),
    );
    expect(fragment.length).toBeLessThanOrEqual(60);
    expect(lang.startsWith(fragment)).toBe(true);
    expect(fragment.endsWith(" ")).toBe(false);
  });

  it("valt zonder citaat terug op de kale bron-URL", () => {
    const resultaat = bewijsUrl({url: "https://example.test/over-ons"});
    expect(resultaat.soort).toBe("html");
    expect(resultaat.url).toBe("https://example.test/over-ons");
  });
});

describe("bekijkBewijs", () => {
  it("houdt een pdf in de werkbank", () => {
    const getoond = [];
    const geopend = [];
    const kandidaat = {url: "https://example.test/verslag.pdf"};

    expect(bekijkBewijs(kandidaat, (item) => getoond.push(item), (...args) => geopend.push(args)))
      .toBe("pdf");
    expect(getoond).toEqual([kandidaat]);
    expect(geopend).toEqual([]);
  });

  it("opent een webpagina extern op de bewijsplek", () => {
    const getoond = [];
    const geopend = [];
    const kandidaat = {
      url: "https://example.test/team",
      bewijsfragment: "Ons team bestaat uit 12 medewerkers",
    };

    expect(bekijkBewijs(kandidaat, (item) => getoond.push(item), (...args) => geopend.push(args)))
      .toBe("extern");
    expect(getoond).toEqual([]);
    expect(geopend).toHaveLength(1);
    expect(geopend[0]).toEqual([
      expect.stringContaining("#:~:text="),
      "_blank",
      "noopener,noreferrer",
    ]);
  });
});
