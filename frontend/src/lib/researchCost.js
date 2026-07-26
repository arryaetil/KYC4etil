const MIN_USD_PER_ORGANISATIE = 0.01;
const MAX_USD_PER_ORGANISATIE = 0.02;

const usd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function researchKostenIndicatie(aantal) {
  const organisaties = Math.max(0, Number(aantal) || 0);

  return {
    organisaties,
    minimum: organisaties * MIN_USD_PER_ORGANISATIE,
    maximum: organisaties * MAX_USD_PER_ORGANISATIE,
  };
}

export function researchBevestiging(aantal) {
  const {organisaties, minimum, maximum} = researchKostenIndicatie(aantal);

  return (
    `Autonoom bronnenonderzoek starten voor ${organisaties} organisaties?\n\n` +
    `Verwachte externe kosten: circa ${usd.format(minimum)}–${usd.format(maximum)} ` +
    `(${usd.format(MIN_USD_PER_ORGANISATIE)}–${usd.format(MAX_USD_PER_ORGANISATIE)} per organisatie).\n\n` +
    "Dit is een indicatie; de werkelijke kosten hangen af van beschikbare bronnen en fallback-zoekopdrachten. " +
    "De agent stelt bronnen voor; een reviewer blijft beslissen."
  );
}
