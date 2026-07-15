const IDENTITY_RISICO = {
  exact_entity: 0, same_brand_or_group: 1, possible_match: 2, mismatch: 3, unknown: 2,
};
const SCOPE_RISICO = {
  vestiging: 0, limburg: 0, nederland: 1, concern: 1, unknown: 1,
};
const ZEKERHEID_RISICO = {hoog: 0, middel: 1, laag: 2};

export function deriveZekerheid(result) {
  const identity = result.identity_class || "unknown";
  const scope = result.scope_class || "unknown";
  const zekerheid = result.llm_zekerheid || "laag";

  if (identity === "mismatch") {
    return {niveau: "rood", label: "Verkeerd bedrijf?", uitleg: "Deze bron lijkt niet over dit bedrijf te gaan — goed nalezen voordat je 'm gebruikt."};
  }
  if (identity === "unknown" || zekerheid === "laag") {
    return {niveau: "rood", label: "Goed nalezen", uitleg: "Onvoldoende zekerheid over bron-identiteit of het gevonden getal — controleer handmatig."};
  }

  const risico = IDENTITY_RISICO[identity] + SCOPE_RISICO[scope] + ZEKERHEID_RISICO[zekerheid];
  if (risico === 0) {
    return {niveau: "groen", label: "Redelijk zeker", uitleg: "Bron hoort aantoonbaar bij dit bedrijf en het getal past bij de vestigingsschaal."};
  }
  if (scope === "nederland" || scope === "concern") {
    return {niveau: "oranje", label: "Controleer schaal", uitleg: "Bron noemt mogelijk een landelijk of concernbreed cijfer, niet per se deze vestiging."};
  }
  if (identity === "same_brand_or_group" || identity === "possible_match") {
    return {niveau: "oranje", label: "Controleer identiteit", uitleg: "Bron hoort bij hetzelfde merk/dezelfde groep, maar mogelijk niet exact dit onderdeel."};
  }
  return {niveau: "oranje", label: "Controleer even", uitleg: "Combinatie van signalen geeft geen volledige zekerheid."};
}
