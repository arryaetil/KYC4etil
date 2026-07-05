export function EnrichmentStrip({enrichment}) {
  const website = enrichment.website_url;
  const tel = enrichment.telefoonnummer;
  const email = enrichment.email;
  const nlCount = enrichment.locatie_count_nl;
  const lbCount = enrichment.locatie_count_lb;
  const bron = enrichment.locatie_bron;
  const bronLabel = {places: "Places", kvk: "KvK", web_search: "web search"}[bron] || bron;

  const hasAny = website || tel || email || nlCount;
  if (!hasAny) return null;

  return (
    <div className="mt-4 border-t border-line pt-4">
      <div className="mb-2 text-xs font-medium uppercase text-slate-500">Gevonden door agent</div>
      <div className="flex flex-wrap gap-4 text-sm">
        {website ? (
          <div>
            <span className="text-slate-500">Website </span>
            <a className="font-medium text-etil underline" href={website} target="_blank" rel="noreferrer">{website.replace(/^https?:\/\//, "")}</a>
          </div>
        ) : null}
        {tel ? (
          <div>
            <span className="text-slate-500">Tel </span>
            <span className="font-medium">{tel}</span>
          </div>
        ) : null}
        {email ? (
          <div>
            <span className="text-slate-500">E-mail </span>
            <a className="font-medium text-etil underline" href={`mailto:${email}`}>{email}</a>
          </div>
        ) : null}
        {nlCount != null ? (
          <div>
            <span className="text-slate-500">Locaties </span>
            <span className="font-medium">{lbCount ?? "?"} in LB / {nlCount} NL</span>
            {bronLabel ? <span className="ml-1 text-xs text-slate-500">({bronLabel})</span> : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
