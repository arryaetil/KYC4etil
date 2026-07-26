export function buildPdfViewerUrl({bronUrl, pagina, citaat}) {
  if (!bronUrl) return null;
  const params = new URLSearchParams();
  params.set("file", bronUrl);
  const fragments = [];
  if (pagina) fragments.push(`page=${pagina}`);
  if (citaat) {
    const zoekterm = citaat.trim().slice(0, 80);
    params.set("phrase", "true");
    fragments.push(`search=${encodeURIComponent(zoekterm)}`);
  }
  const hash = fragments.length ? `#${fragments.join("&")}` : "";
  // pdf.js verwacht zijn eigen standaardindeling: viewer in web/, naast build/.
  // De viewer laadt zijn worker, cmaps en lettertypes relatief via ../build/ en
  // ../web/, dus dit pad mag niet worden afgeplat.
  return `/pdfjs/web/viewer.html?${params.toString()}${hash}`;
}
