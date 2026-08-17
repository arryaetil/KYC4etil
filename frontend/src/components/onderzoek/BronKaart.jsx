import {useState} from "react";
import {Check, ChevronDown, ChevronUp, Eye, X} from "lucide-react";
import {classNames} from "../../lib/format.js";
import {
  TOON_STYLE, bedrijfRelatie, bereikLabel, bereikRelatie, bewijsRelatie,
  bronjaarLabel, bronwaarschuwingen, brontypeLabel, identiteitLabel,
  menselijkeWaarde, primaireConclusie, telopdracht,
} from "../../lib/onderzoekLabels.js";

const TOON_TEKST = {
  neutraal: "text-ink",
  aandacht: "text-amber-800",
  fout: "text-red-800",
  gekozen: "text-emerald-800",
};

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

function Kaartrij({label, waarde}) {
  return (
    <div className="flex gap-3">
      <dt className="w-16 shrink-0 text-slate-500">{label}</dt>
      <dd className={classNames("flex-1", TOON_TEKST[waarde.toon])}>
        <span
          aria-hidden="true"
          className={classNames(
            "mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle",
            waarde.toon === "aandacht" ? "bg-amber-500"
              : waarde.toon === "fout" ? "bg-red-500"
              : waarde.toon === "gekozen" ? "bg-emerald-500" : "bg-slate-300",
          )}
        />
        {waarde.label}
      </dd>
    </div>
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
  const conclusie = primaireConclusie(candidate);
  const bedrijf = bedrijfRelatie(candidate.identity_class);
  const bereikRij = bereikRelatie(candidate.scope_class);
  const bewijsRij = bewijsRelatie(candidate);
  const waarde = menselijkeWaarde(candidate);
  const identiteit = identiteitLabel(candidate.identity_class);
  const bereik = bereikLabel(candidate.scope_class);
  const waarschuwingen = bronwaarschuwingen({...candidate, gevraagd_jaar: gevraagdJaar});
  const bronjaar = bronjaarLabel(candidate);
  const telling = telopdracht(candidate);
  const beoordeeld = ["geaccepteerd", "alternatief", "afgewezen"].includes(candidate.status);

  return (
    <article className={classNames(
      "px-4 py-5 transition",
      candidate.status === "geaccepteerd"
        ? "bg-emerald-50/60"
        : isGeselecteerd ? "bg-panel" : "bg-transparent",
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
        {/* Het jaar van de bron staat vooraan en niet in de onderbouwing: of een
            bron over het goede jaar gaat is de eerste vraag bij een jaarverslag,
            en die hoort niet achter een klik te zitten. */}
        {bronjaar ? (
          <span className="whitespace-nowrap text-xs tabular-nums text-slate-500">
            {bronjaar}
          </span>
        ) : null}
        {candidate.status === "geaccepteerd" ? (
          <span className="ml-auto inline-flex items-center gap-1 rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-900">
            <Check size={11} />Gekozen
          </span>
        ) : candidate.status === "alternatief" ? (
          <span className="ml-auto rounded border border-line bg-white px-1.5 py-0.5 text-xs text-slate-700">
            Relevante bron
          </span>
        ) : null}
      </div>

      {candidate.gedeeld_met_vestigingen > 1 ? (
        <p className="mt-1 text-xs text-slate-500">
          Gedeelde bron voor {candidate.gedeeld_met_vestigingen} vestigingen
        </p>
      ) : null}

      <div className="mt-3">
        <p className="max-w-[65ch] text-base font-medium leading-snug text-ink">
          {conclusie.hoofd}
        </p>
        {conclusie.vervolg ? (
          <p className="mt-1 max-w-[65ch] text-sm text-slate-600">{conclusie.vervolg}</p>
        ) : null}
      </div>

      <dl className="mt-4 space-y-1.5 text-sm">
        <Kaartrij label="Bedrijf" waarde={bedrijf} />
        <Kaartrij label="Bereik" waarde={bereikRij} />
        <Kaartrij label="Bewijs" waarde={bewijsRij} />
        {/* Het peilmoment hoort bij het getal, niet bij het document: een
            jaarverslag over 2025 kan een stand per 1 oktober noemen. Stond
            eerder alleen in de dichtgeklapte onderbouwing. */}
        {candidate.informatie_peilmoment ? (
          <Kaartrij
            label="Peilmoment"
            waarde={{label: candidate.informatie_peilmoment, toon: "neutraal"}}
          />
        ) : null}
        <Kaartrij label="Actie" waarde={{label: waarde.actie, toon: "neutraal"}} />
      </dl>

      {candidate.bewijsfragment ? (
        <blockquote className="mt-3 max-w-[65ch] border-l-2 border-line pl-3 text-sm italic leading-relaxed text-slate-600">
          “{candidate.bewijsfragment}”
        </blockquote>
      ) : null}

      {telling ? (
        <div className="mt-3 max-w-[65ch] rounded-md border border-amber-200 bg-amber-50/60 p-3">
          <p className="text-sm font-medium text-amber-900">
            Tel de medewerkers zelf
          </p>
          <p className="mt-0.5 text-sm text-amber-800">
            {telling.uitleg}{" "}
            {telling.afgeleidAantal != null
              ? `De agent telde ${telling.afgeleidAantal} `
                + `${telling.afgeleidAantal === 1 ? "naam" : "namen"}; `
                + "dat is niet overgenomen als WP-getal."
              : "Het afgeleide getal is niet overgenomen als WP-getal."}
          </p>
          {telling.namen.length ? (
            <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm text-amber-900">
              {telling.namen.map((naam) => (
                <li
                  key={naam}
                  className="before:mr-1 before:text-amber-400 before:content-['•']"
                >
                  {naam}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {waarschuwingen.length ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {waarschuwingen.map((item) => (
            <Signaal key={item.label} {...item} />
          ))}
        </div>
      ) : null}

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
              <Check size={14} />Beoordelen
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
          <div className="flex flex-wrap items-center gap-1.5 pb-1">
            <Signaal {...identiteit} />
            <Signaal {...bereik} />
            {candidate.wp_gevonden != null ? (
              <span className="tabular-nums text-slate-600">
                {candidate.wp_gevonden} {
                  candidate.eenheid === "fte"
                    ? "FTE"
                    : candidate.eenheid === "onderwijspersoneel_personen"
                      ? "onderwijspersoneel"
                      : "WP"
                }
                {candidate.gecorrigeerd_wp != null
                  ? ` → ${candidate.gecorrigeerd_wp} gecorrigeerd`
                  : ""}
              </span>
            ) : null}
            {candidate.verslagjaar ? (
              <span className="text-slate-500">verslagjaar {candidate.verslagjaar}</span>
            ) : null}
          </div>
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
          {/* Peilmoment staat nu in de altijd zichtbare regels hierboven; hier
              herhalen zou dezelfde constatering twee keer op de kaart zetten. */}
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
