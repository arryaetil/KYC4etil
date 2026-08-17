import {describe, expect, it} from "vitest";
import {
  archiveerBevestiging,
  batchesQuery,
  lijstenLabel,
  magUploaden,
  mapActies,
  verwijderBevestiging,
} from "./mappen.js";

describe("lijstenLabel", () => {
  it("telt in het Nederlands enkelvoud en meervoud uit elkaar", () => {
    expect(lijstenLabel(0)).toBe("Nog geen lijsten");
    expect(lijstenLabel(1)).toBe("1 lijst");
    expect(lijstenLabel(2)).toBe("2 lijsten");
    expect(lijstenLabel(205)).toBe("205 lijsten");
  });

  it("behandelt een ontbrekend aantal als leeg", () => {
    expect(lijstenLabel(undefined)).toBe("Nog geen lijsten");
    expect(lijstenLabel(null)).toBe("Nog geen lijsten");
  });
});

describe("verwijderBevestiging", () => {
  it("vraagt bij een lege map één simpele bevestiging", () => {
    const bevestiging = verwijderBevestiging({naam: "Leeg", aantal_lijsten: 0});

    expect(bevestiging.soort).toBe("verwijderen");
    expect(bevestiging.ontkoppelLijsten).toBe(false);
    expect(bevestiging.titel).toBe('"Leeg" verwijderen?');
  });

  it("legt bij een gevulde map uit wat er met de lijsten gebeurt", () => {
    const bevestiging = verwijderBevestiging({naam: "Zorg", aantal_lijsten: 3});

    expect(bevestiging.soort).toBe("verwijderen-gevuld");
    expect(bevestiging.ontkoppelLijsten).toBe(true);
    expect(bevestiging.beschrijving).toContain("3 lijsten");
    expect(bevestiging.beschrijving).toContain("blijven");
    // De knop moet zeggen wat er gebeurt, niet alleen "Verwijderen": de
    // reviewer moet aan het label kunnen zien dat zijn lijsten blijven.
    expect(bevestiging.bevestigLabel).toBe("Map verwijderen, lijsten behouden");
  });

  it("noemt bij één lijst het enkelvoud", () => {
    const bevestiging = verwijderBevestiging({naam: "Bijna leeg", aantal_lijsten: 1});
    expect(bevestiging.beschrijving).toContain("1 lijst.");
  });
});

describe("batchesQuery", () => {
  it("laat bestaande aanroepers ongemoeid zonder map", () => {
    expect(batchesQuery(undefined)).toBe("/batches");
  });

  it("vraagt expliciet om lijsten buiten elke map", () => {
    expect(batchesQuery(null)).toBe("/batches?losse_lijsten=true");
  });

  it("filtert op één map en codeert het id", () => {
    expect(batchesQuery("abc-123")).toBe("/batches?map_id=abc-123");
    expect(batchesQuery("a b&c")).toBe("/batches?map_id=a%20b%26c");
  });
});

describe("magUploaden", () => {
  it("staat uploaden toe in een echte map en zonder mapkeuze", () => {
    expect(magUploaden("abc-123")).toBe(true);
    expect(magUploaden(undefined)).toBe(true);
  });

  it("blokkeert uploaden in de verzamelweergave zonder map", () => {
    // Anders zou de nieuwe lijst meteen nergens bij horen.
    expect(magUploaden(null)).toBe(false);
  });
});

describe("archiveerBevestiging", () => {
  it("waarschuwt niet, want er raakt niets kwijt", () => {
    const bevestiging = archiveerBevestiging({naam: "Oud", aantal_lijsten: 0});

    expect(bevestiging.soort).toBe("archiveren");
    expect(bevestiging.bevestigLabel).toBe("Archiveren");
    expect(bevestiging.beschrijving).toContain("herstellen");
  });

  it("benoemt expliciet dat de lijsten blijven staan", () => {
    const bevestiging = archiveerBevestiging({naam: "Zorg", aantal_lijsten: 4});

    expect(bevestiging.beschrijving).toContain("4 lijsten");
    expect(bevestiging.beschrijving).toContain("blijven staan");
  });
});

describe("mapActies", () => {
  it("zet archiveren vóór verwijderen", () => {
    const acties = mapActies({naam: "Zorg"});

    expect(acties).toEqual(["hernoemen", "archiveren", "verwijderen"]);
    // Opruimen zonder weggooien is de gewone handeling; definitief weggooien
    // hoort niet de eerste optie te zijn die je aanwijst.
    expect(acties.indexOf("archiveren")).toBeLessThan(acties.indexOf("verwijderen"));
  });

  it("biedt in het archief terugzetten aan in plaats van hernoemen", () => {
    expect(mapActies({naam: "Oud"}, {gearchiveerd: true}))
      .toEqual(["herstellen", "verwijderen"]);
  });
});
