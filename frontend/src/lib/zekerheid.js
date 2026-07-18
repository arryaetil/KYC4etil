const GROENE_IDENTITEITEN = new Set(["exact_entity", "same_brand_or_group"]);
const GROENE_SCOPES = new Set(["vestiging", "limburg"]);
const GROENE_ZEKERHEDEN = new Set(["hoog", "middel"]);

export function deriveZekerheid(result) {
  const identity = result.identity_class || "unknown";
  const scope = result.scope_class || "unknown";
  const zekerheid = result.llm_zekerheid || "laag";

  const isGroen = GROENE_IDENTITEITEN.has(identity)
    && GROENE_SCOPES.has(scope)
    && GROENE_ZEKERHEDEN.has(zekerheid);

  if (isGroen) {
    return {niveau: "groen", label: "Bron gevonden", uitleg: "Bron hoort aantoonbaar bij dit bedrijf op de juiste schaal."};
  }
  if (identity === "mismatch") {
    return {niveau: "rood", label: "Verkeerd bedrijf?", uitleg: "Deze bron lijkt niet over dit bedrijf te gaan — goed nalezen voordat je 'm gebruikt."};
  }
  return {niveau: "rood", label: "Goed nalezen", uitleg: "Onvoldoende zekerheid over bron-identiteit, schaal of het gevonden getal — controleer handmatig."};
}
