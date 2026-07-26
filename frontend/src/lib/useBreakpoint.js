import {useEffect, useState} from "react";

/**
 * Abonneert op een media query en levert een opruimfunctie op.
 *
 * Los van React gehouden zodat de riskante kant — luisteren én netjes
 * afmelden, ook op oudere Safari's die alleen addListener kennen — puur
 * testbaar is. `venster` is injecteerbaar voor die tests.
 */
export function abonneerOpMediaQuery(query, onChange, venster = globalThis) {
  const media = venster?.matchMedia?.(query);
  if (!media) return {matches: false, stop: () => {}};

  const luister = (event) => onChange(event.matches);
  if (media.addEventListener) {
    media.addEventListener("change", luister);
    return {matches: media.matches, stop: () => media.removeEventListener("change", luister)};
  }
  media.addListener(luister);
  return {matches: media.matches, stop: () => media.removeListener(luister)};
}

/**
 * Volgt of een media query op dit moment geldt. Gebruikt om zware panelen
 * precies één keer te renderen: een `display:none`-iframe laadt gewoon door,
 * dus een tweede kopie achter `xl:hidden` kost echte bandbreedte.
 */
export function useMediaQuery(query) {
  const [matcht, setMatcht] = useState(
    () => globalThis.matchMedia?.(query)?.matches ?? false,
  );

  useEffect(() => {
    const abonnement = abonneerOpMediaQuery(query, setMatcht);
    setMatcht(abonnement.matches);
    return abonnement.stop;
  }, [query]);

  return matcht;
}

/** True zodra het venster minstens de Tailwind-`xl`-breedte (1280px) heeft. */
export function useIsXl() {
  return useMediaQuery("(min-width: 1280px)");
}
