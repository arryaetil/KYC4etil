export function Diagnostiek({diagnostiek}) {
  if (!diagnostiek || !Object.keys(diagnostiek).length) return null;

  const website = diagnostiek.website_resolution;
  const redenen = Object.entries(diagnostiek.afwijsredenen || {});

  return (
    <section className="rounded-md border border-line bg-panel p-4">
      <h3 className="text-sm font-medium text-ink">
        Geen bruikbare bron gevonden
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-mist-85">
        De agent vond {diagnostiek.zoekresultaten || 0} zoekresultaten,
        onderzocht {diagnostiek.onderzochte_paginas || 0} pagina's en las{" "}
        {diagnostiek.gelezen_documenten || 0} documenten. Daarvan vielen er{" "}
        {diagnostiek.afgewezen_documenten || 0} af bij de kwaliteitscontrole.
      </p>

      <p className="mt-3 text-xs text-mist-65">
        Officiële website:{" "}
        {website?.website_url ? (
          <a
            href={website.website_url}
            target="_blank"
            rel="noreferrer"
            className="focus-ring text-ink underline"
          >
            {website.website_url}
          </a>
        ) : (
          "niet gevonden"
        )}
      </p>

      {redenen.length ? (
        <p className="mt-1 text-xs text-mist-65">
          Redenen:{" "}
          {redenen
            .map(([reden, aantal]) => `${reden.replaceAll("_", " ")} (${aantal})`)
            .join(", ")}
        </p>
      ) : null}

      {diagnostiek.afwijzingen?.length ? (
        <details className="mt-3">
          <summary className="focus-ring cursor-pointer text-xs text-mist-65 hover:text-ink">
            Bekijk de {diagnostiek.afwijzingen.length} afgewezen bronnen
          </summary>
          <ul className="mt-2 space-y-1.5">
            {diagnostiek.afwijzingen.map((item) => (
              <li key={item.url} className="text-xs leading-relaxed">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="focus-ring text-ink underline"
                >
                  {item.titel || item.url}
                </a>
                <span className="text-mist-65">
                  {" — "}
                  {item.review_reden
                    || item.redenen?.join(", ").replaceAll("_", " ")
                    || "afgewezen"}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
