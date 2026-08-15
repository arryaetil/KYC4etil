import {buildBronPaginaUrl, buildPdfViewerUrl} from "./pdfViewerLink.js";

function isPdf(url) {
  try {
    return new URL(url).pathname.toLowerCase().endsWith(".pdf");
  } catch {
    return url.toLowerCase().includes(".pdf");
  }
}

/**
 * Bepaalt hoe het bewijs van een bronkandidaat getoond kan worden.
 *
 * PDF's gaan door de meegeleverde pdf.js-viewer. HTML-bronnen gaan door de
 * backend-leesweergave (research/bewijspagina.py): de browser past de
 * `#:~:text=`-tekstfragment-highlight sowieso niet toe binnen een iframe, dus
 * highlighten kan alleen door de tekst zelf te markeren vóór het insluiten.
 */
export function bewijsUrl(candidate, token) {
  const bron = candidate?.url;
  if (!bron) return {soort: null, url: null, kanInbedden: false};

  if (isPdf(bron)) {
    return {
      soort: "pdf",
      url: buildPdfViewerUrl({
        bronUrl: bron,
        pagina: candidate.bron_pagina,
        citaat: candidate.bewijsfragment,
        token,
      }),
      kanInbedden: true,
    };
  }

  return {
    soort: "html",
    url: buildBronPaginaUrl({
      bronUrl: bron,
      titel: candidate.titel,
      citaat: candidate.bewijsfragment?.trim(),
      token,
    }),
    kanInbedden: true,
  };
}
