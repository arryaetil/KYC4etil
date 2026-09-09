// Bandbreedte als er nog geen cijfers uit de backend zijn. Gemeten over 177
// productieruns in september 2026; alleen een terugval, want de echte waarden
// komen van /batches/kostenindicatie en bewegen mee met het model en de routes.
const TERUGVAL = {laag_usd: 0.015, hoog_usd: 0.056};

const usd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function researchKostenIndicatie(aantal, band) {
  const organisaties = Math.max(0, Number(aantal) || 0);
  const laag = Number(band?.laag_usd) || TERUGVAL.laag_usd;
  const hoog = Number(band?.hoog_usd) || TERUGVAL.hoog_usd;

  return {
    organisaties,
    minimum: organisaties * laag,
    maximum: organisaties * hoog,
    perOrganisatieLaag: laag,
    perOrganisatieHoog: hoog,
  };
}

/**
 * De tekst boven het starten van een onderzoek.
 *
 * Twee dingen klopten hier niet. Het bedrag stond vast op $0,01–$0,02 per
 * organisatie, opgeschreven in juli en sindsdien nooit bijgesteld terwijl het
 * model wisselde en er routes bij kwamen — werkelijk is het twee tot drie keer
 * zoveel. En het rekende met de hele lijst, terwijl een herstart de
 * organisaties overslaat die al een afgerond onderzoek hebben: bij een lijst
 * van 108 waarvan er nog 12 te doen waren noemde het scherm de prijs van 108.
 */
export function researchBevestiging(aantal, band, totaalInLijst) {
  const {organisaties, minimum, maximum, perOrganisatieLaag, perOrganisatieHoog} =
    researchKostenIndicatie(aantal, band);
  const alGedaan = Math.max(0, (Number(totaalInLijst) || 0) - organisaties);

  return (
    `Bronnenonderzoek starten voor ${organisaties} organisaties?\n\n`
    + (alGedaan
      ? `${alGedaan} ${alGedaan === 1 ? "organisatie is" : "organisaties zijn"} `
        + "al onderzocht en worden overgeslagen.\n\n"
      : "")
    + `Verwachte externe kosten: ${usd.format(minimum)}–${usd.format(maximum)} `
    + `(${usd.format(perOrganisatieLaag)}–${usd.format(perOrganisatieHoog)} `
    + "per organisatie).\n\n"
    + "Een indicatie op basis van eerdere runs; wat het echt wordt hangt af van "
    + "hoeveel bronnen er te vinden zijn. De agent stelt voor, de reviewer beslist."
  );
}
