export function pct(value) {
  if (!value) return 0;
  return Math.max(0, Math.min(100, Math.round(value * 100)));
}

export function classNames(...items) {
  return items.filter(Boolean).join(" ");
}

// Bouwt een link die zo mogelijk direct naar de plek springt waar de AI het
// citaat vond: paginanummer voor PDF's (native browserondersteuning), Text
// Fragment voor webpagina's (markeert het citaat — alleen Chrome/Edge; in
// andere browsers opent de link gewoon de pagina, zonder foutmelding).
export function bronLink(result) {
  if (!result?.bron_url) return null;
  if (result.bron_pagina) {
    return `${result.bron_url}#page=${result.bron_pagina}`;
  }
  if (result.context) {
    const fragment = result.context.trim().slice(0, 120);
    return `${result.bron_url}#:~:text=${encodeURIComponent(fragment)}`;
  }
  return result.bron_url;
}
