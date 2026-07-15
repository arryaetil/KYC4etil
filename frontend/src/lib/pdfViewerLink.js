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
  return `/pdfjs/viewer.html?${params.toString()}${hash}`;
}
