import {describe, expect, it} from "vitest";
import {researchBevestiging, researchKostenIndicatie} from "./researchCost.js";

const BAND = {laag_usd: 0.02, hoog_usd: 0.06};

describe("researchKostenIndicatie", () => {
  it("rekent met de bandbreedte uit de backend", () => {
    expect(researchKostenIndicatie(20, BAND)).toEqual({
      organisaties: 20,
      minimum: 0.4,
      maximum: 1.2,
      perOrganisatieLaag: 0.02,
      perOrganisatieHoog: 0.06,
    });
  });

  it("valt terug op de gemeten standaardband zonder gegevens", () => {
    const zonder = researchKostenIndicatie(100, null);

    // De oude vaste waarden ($0,01–$0,02) zaten twee tot drie keer te laag.
    expect(zonder.perOrganisatieLaag).toBe(0.015);
    expect(zonder.perOrganisatieHoog).toBe(0.056);
  });

  it("maakt ongeldige aantallen veilig nul", () => {
    expect(researchKostenIndicatie(-2, BAND).organisaties).toBe(0);
    expect(researchKostenIndicatie("onbekend", BAND).organisaties).toBe(0);
  });
});

describe("researchBevestiging", () => {
  it("noemt het bedrag voor wat er nog te doen is", () => {
    const tekst = researchBevestiging(108, BAND, 108);

    expect(tekst).toContain("108 organisaties");
    expect(tekst).toContain("$2.16–$6.48");
    expect(tekst).not.toContain("overgeslagen");
  });

  it("zegt hoeveel er wordt overgeslagen bij een herstart", () => {
    // De run pakt alleen op wat nog geen afgeronde research heeft; het scherm
    // noemde eerder de prijs van de hele lijst.
    const tekst = researchBevestiging(12, BAND, 108);

    expect(tekst).toContain("12 organisaties");
    expect(tekst).toContain("96 organisaties zijn al onderzocht");
    expect(tekst).toContain("$0.24–$0.72");
  });

  it("schrijft één overgeslagen organisatie enkelvoudig", () => {
    expect(researchBevestiging(4, BAND, 5)).toContain(
      "1 organisatie is al onderzocht",
    );
  });
});
