import {describe, expect, it} from "vitest";
import {researchBevestiging, researchKostenIndicatie} from "./researchCost.js";

describe("researchKostenIndicatie", () => {
  it("berekent de bandbreedte voor een batch", () => {
    expect(researchKostenIndicatie(20)).toEqual({
      organisaties: 20,
      minimum: 0.2,
      maximum: 0.4,
    });
  });

  it("toont de totale indicatie vóór het starten", () => {
    const tekst = researchBevestiging(108);

    expect(tekst).toContain("108 organisaties");
    expect(tekst).toContain("$1.08–$2.16");
    expect(tekst).toContain("Dit is een indicatie");
  });

  it("maakt ongeldige aantallen veilig nul", () => {
    expect(researchKostenIndicatie(-2).organisaties).toBe(0);
    expect(researchKostenIndicatie("onbekend").organisaties).toBe(0);
  });
});
