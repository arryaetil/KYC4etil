const API_URL = import.meta.env?.VITE_API_URL || "http://127.0.0.1:8000";

/**
 * Bouwt het adres waarmee de backend een brondocument doorgeeft.
 *
 * De viewer haalt het document niet rechtstreeks bij de organisatie op: veel
 * servers sturen geen CORS-headers, waardoor de browser het ophalen blokkeert
 * en de reviewer een leeg venster ziet. Via de backend komt het document van
 * een domein dat de browser wél accepteert.
 *
 * Het token gaat mee in de query omdat de PDF-viewer het document met een
 * gewone fetch ophaalt en daar geen Authorization-header aan kan toevoegen.
 */
export function buildBronProxyUrl(bronUrl, token) {
  if (!bronUrl) return null;
  const params = new URLSearchParams({url: bronUrl});
  if (token) params.set("token", token);
  return `${API_URL}/research/bron-pdf?${params.toString()}`;
}

/**
 * Bouwt de URL voor de interne leesweergave van een webbron (het
 * website-equivalent van de PDF-modal, zie backend research/bewijspagina.py).
 * Het `#citaat`-anker laat de browser vanzelf naar de markering scrollen,
 * zonder dat daar JavaScript voor nodig is.
 */
export function buildBronPaginaUrl({bronUrl, titel, citaat, token}) {
  if (!bronUrl) return null;
  const params = new URLSearchParams({url: bronUrl});
  if (titel) params.set("titel", titel);
  if (citaat) params.set("citaat", citaat);
  if (token) params.set("token", token);
  const hash = citaat ? "#citaat" : "";
  return `${API_URL}/research/bron-pagina?${params.toString()}${hash}`;
}

export function buildPdfViewerUrl({bronUrl, pagina, citaat, token}) {
  if (!bronUrl) return null;
  const params = new URLSearchParams();
  params.set("file", buildBronProxyUrl(bronUrl, token));
  const fragments = [];
  if (pagina) fragments.push(`page=${pagina}`);
  if (citaat) {
    const zoekterm = citaat.trim().slice(0, 80);
    fragments.push(`search=${encodeURIComponent(zoekterm)}`);
    fragments.push("phrase=true");
  }
  const hash = fragments.length ? `#${fragments.join("&")}` : "";
  // pdf.js verwacht zijn eigen standaardindeling: viewer in web/, naast build/.
  // De viewer laadt zijn worker, cmaps en lettertypes relatief via ../build/ en
  // ../web/, dus dit pad mag niet worden afgeplat.
  return `/pdfjs/web/viewer.html?${params.toString()}${hash}`;
}
