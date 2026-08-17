/**
 * Pure logica achter de mappenlaag, los van React zodat ze toetsbaar is.
 *
 * De mappenlaag is puur ordening: een map bevat lijsten en verder niets. Het
 * enige dat echt aandacht vraagt is verwijderen, want onderzoeksresultaten
 * zijn duur om opnieuw op te bouwen.
 */

export function lijstenLabel(aantal) {
  if (!aantal) return "Nog geen lijsten";
  return aantal === 1 ? "1 lijst" : `${aantal} lijsten`;
}

/**
 * Welke bevestiging hoort bij het verwijderen van deze map?
 *
 * Een lege map vraagt één simpele bevestiging. Een gevulde map moet eerst
 * uitleggen wat er met de lijsten gebeurt — anders klikt iemand een
 * waarschuwing weg zonder te weten wat hij weggooit.
 */
export function verwijderBevestiging(map) {
  const aantal = map?.aantal_lijsten || 0;
  if (!aantal) {
    return {
      soort: "verwijderen",
      titel: `"${map?.naam}" verwijderen?`,
      beschrijving:
        "Deze map is leeg. Verwijderen kan niet ongedaan worden gemaakt.",
      bevestigLabel: "Verwijderen",
      ontkoppelLijsten: false,
    };
  }
  return {
    soort: "verwijderen-gevuld",
    titel: `"${map.naam}" verwijderen?`,
    beschrijving:
      `Deze map bevat ${lijstenLabel(aantal).toLowerCase()}. Die blijven `
      + "bestaan en komen onder “Zonder map” te staan — onderzoeksresultaten "
      + "gaan nooit verloren bij het opruimen van een map.",
    bevestigLabel: "Map verwijderen, lijsten behouden",
    ontkoppelLijsten: true,
  };
}

/**
 * Query voor de lijstenpagina.
 *
 * `undefined` = alle lijsten (bestaand gedrag voor aanroepers die geen map
 * kennen), `null` = alleen lijsten buiten elke map, een id = die ene map.
 */
export function batchesQuery(mapId) {
  if (mapId === null) return "/batches?losse_lijsten=true";
  if (mapId === undefined) return "/batches";
  return `/batches?map_id=${encodeURIComponent(mapId)}`;
}

/** Mag er in deze weergave een lijst geüpload worden? */
export function magUploaden(mapId) {
  // "Zonder map" is een verzamelweergave, geen echte map: daar iets in
  // uploaden zou betekenen dat de lijst meteen nergens bij hoort.
  return mapId !== null;
}

/**
 * Bevestiging bij archiveren.
 *
 * Bewust géén waarschuwende toon: er raakt niets kwijt en herstellen kost één
 * klik. Wel expliciet benoemen wat er met de lijsten gebeurt, want dat is
 * precies de zorg die verwijderen oproept.
 */
export function archiveerBevestiging(map) {
  const aantal = map?.aantal_lijsten || 0;
  return {
    soort: "archiveren",
    titel: `"${map?.naam}" archiveren?`,
    beschrijving: aantal
      ? `De map verdwijnt uit het overzicht. De ${lijstenLabel(aantal)
        .toLowerCase()} erin blijven staan en komen terug zodra je de map `
        + "herstelt."
      : "De map verdwijnt uit het overzicht. Je kunt hem later herstellen.",
    bevestigLabel: "Archiveren",
  };
}

/** Menu-items voor een map, in de volgorde van meest naar minst gebruikt. */
export function mapActies(map, {gearchiveerd = false} = {}) {
  if (gearchiveerd) return ["herstellen", "verwijderen"];
  // Archiveren vóór verwijderen: opruimen zonder weggooien is de gewone
  // handeling, definitief weggooien de uitzondering.
  return ["hernoemen", "archiveren", "verwijderen"];
}
