import {Eye} from "lucide-react";
import {classNames, formatMoment} from "../../lib/format.js";
import {
  bewijsRelatie, monitoringStatus, peilmomentRelatie,
} from "../../lib/onderzoekLabels.js";

/**
 * Bouwt uit de monitoringvelden een kandidaat-vormig object, zodat het
 * bewijspaneel de gevonden bron op dezelfde manier kan openen als een bronkaart.
 *
 * Paginanummer en bewijsfragment horen erbij: `bewijsUrl` leidt daar de
 * `#page=`- en `search=`-fragmenten uit af. Ontbreken ze, dan opent het
 * jaarverslag op pagina 1 in plaats van bij het WP-getal.
 */
export function alsBewijsBron(company) {
  if (!company?.laatste_bron_url) return null;
  // De volledige kandidaat als de monitoring die heeft; anders het minimum dat
  // de bewijsviewer nodig heeft.
  if (company.bron) return company.bron;
  return {
    id: `monitoring:${company.company_id}`,
    url: company.laatste_bron_url,
    titel: `Jaarverslag${company.verslagjaar ? ` ${company.verslagjaar}` : ""} ${company.naam || ""}`.trim(),
    brontype: "jaarverslag",
    bron_pagina: company.bron_pagina ?? null,
    bewijsfragment: company.bewijsfragment ?? null,
  };
}

function Vondstrij({label, waarde}) {
  return (
    <div className="flex gap-3">
      <dt className="w-20 shrink-0 text-slate-500">{label}</dt>
      <dd className="flex-1 text-ink">{waarde.label}</dd>
    </div>
  );
}

export function MonitoringVondst({company, geselecteerdeBronId, onSelecteerBron}) {
  const status = monitoringStatus(company);
  const bron = alsBewijsBron(company);
  const peilmomentRij = peilmomentRelatie(company.bron, {
    gevraagdJaar: company.doeljaar,
  }) || {term: "Verslagjaar", label: "Niet bekend"};

  return (
    <section className="border-b border-line px-5 py-5">
      <div className="flex items-baseline gap-2">
        <h3 className="text-xs uppercase tracking-wide text-slate-400">
          Wat de monitoring vond
        </h3>
        <span className="ml-auto text-xs text-slate-400">
          Gecontroleerd: {formatMoment(company.laatst_gecontroleerd_op)}
        </span>
      </div>

      {company.fout ? (
        <p className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          De laatste controle is mislukt: {company.fout}
        </p>
      ) : bron ? (
        <>
          <p className="mt-3 break-all text-base leading-relaxed text-ink">
            <a
              href={bron.url}
              target="_blank"
              rel="noreferrer"
              className="focus-ring rounded underline decoration-slate-300 underline-offset-4 transition hover:decoration-ink"
            >
              {bron.url}
            </a>
          </p>
          {/* Het WP-getal en het jaar stonden hier niet, terwijl de monitoring
              ze al had uitgelezen: de reviewer moest de bron openen om te zien
              of er überhaupt een cijfer in stond. Dezelfde twee regels als op
              een bronkaart, in dezelfde woorden. */}
          {company.bron ? (
            <dl className="mt-3 space-y-1.5 text-sm">
              <Vondstrij label="Bewijs" waarde={bewijsRelatie(company.bron)} />
              <Vondstrij
                label={peilmomentRij.term}
                waarde={peilmomentRij}
              />
            </dl>
          ) : null}

          <div className="mt-3 flex flex-wrap items-center gap-3">
            {!company.bron && company.verslagjaar ? (
              <span className="text-sm font-medium text-ink">
                Verslagjaar {company.verslagjaar}
              </span>
            ) : null}
            <button
              type="button"
              onClick={() => onSelecteerBron(bron)}
              aria-pressed={bron.id === geselecteerdeBronId}
              className={classNames(
                "focus-ring inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-sm transition",
                bron.id === geselecteerdeBronId
                  ? "border-etil text-ink"
                  : "border-line text-ink hover:bg-panel",
              )}
            >
              <Eye size={14} />Bewijs bekijken
            </button>
          </div>
        </>
      ) : (
        <p className="mt-3 text-sm text-slate-500">
          {company.laatst_gecontroleerd_op
            ? "Bij de laatste controle is geen jaarverslag gevonden."
            : "Deze organisatie is nog niet gecontroleerd."}
        </p>
      )}

      {/* Alleen de status. Hier stonden twee zinnen bij: dat er sinds de vorige
          ronde een recenter verslag was, en dat monitoring bronnen vindt maar
          niet kiest. Het eerste zegt iets over de vórige ronde en niet over dit
          verslag; het tweede legt de module uit aan iemand die er al in werkt.
          Allebei stonden ze onder élke kaart, elke ronde. */}
      <p className="mt-3 text-xs text-slate-400">
        Status: {status.label}.
      </p>
    </section>
  );
}
