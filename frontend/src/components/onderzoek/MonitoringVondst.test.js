import {describe, it, expect} from "vitest";
import {alsBewijsBron} from "./MonitoringVondst.jsx";
import {bewijsUrl} from "../../lib/evidenceLink.js";

describe("alsBewijsBron", () => {
  it("geeft null zonder gevonden bron", () => {
    expect(alsBewijsBron({company_id: "c1"})).toBeNull();
  });

  it("neemt de vindplaats van het WP-getal mee", () => {
    const bron = alsBewijsBron({
      company_id: "c1",
      naam: "Organisatie X",
      laatste_bron_url: "https://voorbeeld.test/jaarverslag-2025.pdf",
      verslagjaar: 2025,
      bron_pagina: 14,
      bewijsfragment: "47 medewerkers in dienst",
    });

    expect(bron.bron_pagina).toBe(14);
    expect(bron.bewijsfragment).toBe("47 medewerkers in dienst");
  });

  it("opent het jaarverslag op de WP-pagina met highlight", () => {
    const bron = alsBewijsBron({
      company_id: "c1",
      naam: "Organisatie X",
      laatste_bron_url: "https://voorbeeld.test/jaarverslag-2025.pdf",
      bron_pagina: 14,
      bewijsfragment: "47 medewerkers in dienst",
    });

    const {soort, url, kanInbedden} = bewijsUrl(bron, "tok");
    expect(soort).toBe("pdf");
    expect(kanInbedden).toBe(true);
    expect(url).toContain("#page=14");
    expect(url).toContain("search=47%20medewerkers%20in%20dienst");
    expect(url).toContain("phrase=true");
  });

  it("valt terug op pagina 1 als de monitoring geen vindplaats kent", () => {
    const bron = alsBewijsBron({
      company_id: "c1",
      naam: "Organisatie X",
      laatste_bron_url: "https://voorbeeld.test/jaarverslag-2025.pdf",
    });

    expect(bewijsUrl(bron, "tok").url).not.toContain("#page=");
  });
});
