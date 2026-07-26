import {useState} from "react";
import {Check, ChevronDown, ChevronUp, Eye, X} from "lucide-react";
import {classNames} from "../../lib/format.js";
import {
  TOON_STYLE, bereikLabel, bronwaarschuwingen, brontypeLabel, identiteitLabel,
  menselijkeWaarde,
} from "../../lib/onderzoekLabels.js";

function Signaal({label, toon}) {
  return (
    <span className={classNames(
      "inline-flex items-center rounded border px-1.5 py-0.5 text-xs",
      TOON_STYLE[toon],
    )}>
      {label}
    </span>
  );
}

function herkomst(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function BronKaart({
  candidate, rang, gevraagdJaar, isGeselecteerd, bezig,
  onBekijk, onAccepteer, onWijsAf,
}) {
  const [toonOnderbouwing, setToonOnderbouwing] = useState(false);
  const identiteit = identiteitLabel(candidate.identity_class);
  const bereik = bereikLabel(candidate.scope_class);
  const waarde = menselijkeWaarde(candidate);
  const waarschuwingen = bronwaarschuwingen({...candidate, gevraagd_jaar: gevraagdJaar});
  const beoordeeld = ["geaccepteerd", "afgewezen"].includes(candidate.status);

  return (
    <article className={classNames(
      "border-l-2 py-5 pl-4 pr-1 transition",
      candidate.status === "geaccepteerd"
        ? "border-l-emerald-500"
        : isGeselecteerd ? "border-l-etil" : "border-l-transparent",
      candidate.status === "afgewezen" && "opacity-50",
    )}>
      <div className="flex items-baseline gap-2">
        <span className="text-xs tabular-nums text-slate-400">{rang}</span>
        <span className="text-sm font-medium text-ink">
          {brontypeLabel(candidate.brontype)}
        </span>
        <span className="truncate text-xs text-slate-400">
          {herkomst(candidate.url)}
        </span>
        {candidate.status === "geaccepteerd" ? (
          <span className="ml-auto inline-flex items-center gap-1 rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-900">
            <Check size={11} />Gekozen
          </span>
        ) : null}
      </div>

      {candidate.gedeeld_met_vestigingen > 1 ? (
        <p className="mt-1 text-xs text-slate-500">
          Gedeelde bron voor {candidate.gedeeld_met_vestigingen} vestigingen
        </p>
      ) : null}

      {candidate.bewijsfragment ? (
        <blockquote className="mt-3 text-base leading-relaxed text-ink">
          “{candidate.bewijsfragment}”
        </blockquote>
      ) : (
        <p className="mt-3 text-sm italic text-slate-500">
          Geen citaat geëxtraheerd — beoordeel de bron zelf.
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <Signaal {...identiteit} />
        <Signaal {...bereik} />
        {candidate.wp_gevonden != null ? (
          <span className="text-xs tabular-nums text-slate-600">
            {candidate.wp_gevonden} {candidate.eenheid === "fte" ? "FTE" : "WP"}
          </span>
        ) : null}
        {candidate.verslagjaar ? (
          <span className="text-xs text-slate-500">
            verslagjaar {candidate.verslagjaar}
          </span>
        ) : null}
      </div>

      {waarschuwingen.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {waarschuwingen.map((item) => (
            <Signaal key={item.label} {...item} />
          ))}
        </div>
      ) : null}

      <div className="mt-3 border-t border-line pt-3 text-sm">
        <p className="font-medium text-ink">{waarde.label}</p>
        <p className="mt-0.5 max-w-[70ch] text-slate-600">{waarde.actie}</p>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => onBekijk(candidate)}
          className="focus-ring inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-sm text-ink transition hover:bg-panel"
        >
          <Eye size={14} />Bewijs bekijken
        </button>
        {!beoordeeld ? (
          <>
            <button
              type="button"
              onClick={() => onAccepteer(candidate)}
              disabled={bezig}
              className="focus-ring inline-flex items-center gap-1.5 rounded-md bg-ink px-2.5 py-1.5 text-sm text-white transition hover:opacity-90 disabled:opacity-50"
            >
              <Check size={14} />Accepteren
            </button>
            <button
              type="button"
              onClick={() => onWijsAf(candidate)}
              disabled={bezig}
              className="focus-ring inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-slate-500 transition hover:text-ink disabled:opacity-50"
            >
              <X size={14} />Afwijzen
            </button>
          </>
        ) : null}
        <button
          type="button"
          onClick={() => setToonOnderbouwing((open) => !open)}
          aria-expanded={toonOnderbouwing}
          className="focus-ring ml-auto inline-flex items-center gap-1 rounded px-1 py-1 text-xs text-slate-400 transition hover:text-slate-600"
        >
          Onderbouwing
          {toonOnderbouwing ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {toonOnderbouwing ? (
        <dl className="mt-3 space-y-1 border-t border-line pt-3 text-xs text-slate-500">
          {candidate.validaties?.intelligente_review?.reden ? (
            <div>
              <dt className="inline font-medium text-slate-600">Bronreview: </dt>
              <dd className="inline">{candidate.validaties.intelligente_review.reden}</dd>
            </div>
          ) : null}
          {candidate.publicatiedatum ? (
            <div>
              <dt className="inline font-medium text-slate-600">Gepubliceerd: </dt>
              <dd className="inline">{candidate.publicatiedatum}</dd>
            </div>
          ) : null}
          {candidate.informatie_peilmoment ? (
            <div>
              <dt className="inline font-medium text-slate-600">Peilmoment: </dt>
              <dd className="inline">{candidate.informatie_peilmoment}</dd>
            </div>
          ) : null}
          <div>
            <dt className="inline font-medium text-slate-600">Bron-URL: </dt>
            <dd className="inline break-all">
              <a
                href={candidate.url}
                target="_blank"
                rel="noreferrer"
                className="focus-ring rounded underline decoration-slate-300 underline-offset-2 transition hover:text-ink"
              >
                {candidate.url}
              </a>
            </dd>
          </div>
        </dl>
      ) : null}
    </article>
  );
}
