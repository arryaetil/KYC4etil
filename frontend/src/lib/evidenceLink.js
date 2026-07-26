import {buildPdfViewerUrl} from "./pdfViewerLink.js";

const MAX_FRAGMENT_LENGTE = 60;

function isPdf(url) {
  try {
    return new URL(url).pathname.toLowerCase().endsWith(".pdf");
  } catch {
    return url.toLowerCase().includes(".pdf");
  }
}

/**
 * Kort het citaat in tot een korte, distinctieve passage. Te lange fragmenten
 * matchen vaker niet, omdat de gerenderde pagina subtiel kan afwijken van de
 * tekst die de agent extraheerde.
 */
function kortFragment(citaat) {
  const schoon = citaat.trim().replace(/\s+/g, " ");
  if (schoon.length <= MAX_FRAGMENT_LENGTE) return schoon;
  const afgekapt = schoon.slice(0, MAX_FRAGMENT_LENGTE);
  const laatsteSpatie = afgekapt.lastIndexOf(" ");
  return (laatsteSpatie > 0 ? afgekapt.slice(0, laatsteSpatie) : afgekapt).trim();
}

/**
 * Codeert een tekstfragment voor een `#:~:text=`-directive. Komma's scheiden
 * de onderdelen van zo'n directive en koppeltekens markeren prefix/suffix,
 * dus die moeten percent-gecodeerd worden. encodeURIComponent laat het
 * koppelteken ongemoeid, vandaar de extra vervanging.
 */
function codeerFragment(tekst) {
  return encodeURIComponent(tekst).replaceAll("-", "%2D");
}

/**
 * Bepaalt hoe het bewijs van een bronkandidaat getoond kan worden.
 *
 * PDF's gaan door de meegeleverde pdf.js-viewer en kunnen daardoor ingesloten
 * worden getoond op de juiste pagina, met highlight. HTML-bronnen kunnen dat
 * niet: browsers passen tekstfragmenten niet toe binnen een iframe, en een
 * cross-origin pagina kan niet door ons worden gemanipuleerd. Voor HTML wordt
 * daarom een tekstfragment-URL gebouwd die in een nieuw tabblad geopend moet
 * worden, waar de browser zelf naar het citaat scrollt en het markeert.
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

  const citaat = candidate.bewijsfragment?.trim();
  if (!citaat) return {soort: "html", url: bron, kanInbedden: false};

  const basis = bron.split("#")[0];
  return {
    soort: "html",
    url: `${basis}#:~:text=${codeerFragment(kortFragment(citaat))}`,
    kanInbedden: false,
  };
}
