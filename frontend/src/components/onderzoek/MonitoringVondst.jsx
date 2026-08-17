import {Eye} from "lucide-react";
import {classNames, formatMoment} from "../../lib/format.js";
import {monitoringStatus} from "../../lib/onderzoekLabels.js";

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
  return {
    id: `monitoring:${company.company_id}`,
    url: company.laatste_bron_url,
    titel: `Jaarverslag${company.verslagjaar ? ` ${company.verslagjaar}` : ""} ${company.naam || ""}`.trim(),
    brontype: "jaarverslag",
    bron_pagina: company.bron_pagina ?? null,
    bewijsfragment: company.bewijsfragment ?? null,
  };
}

export function MonitoringVondst({company, geselecteerdeBronId, onSelecteerBron}) {
  const status = monitoringStatus(company);
  const bron = alsBewijsBron(company);

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
          <div className="mt-3 flex flex-wrap items-center gap-3">
            {company.verslagjaar ? (
              <span className="text-sm font-medium text-ink">
                Verslagjaar {company.verslagjaar}
                {/* Zonder deze regel moet de reviewer zelf onthouden welk jaar
                    gevraagd is om te zien of dit verslag nog achterloopt. */}
                {company.doeljaar && company.verslagjaar < company.doeljaar
                  ? ` — gevraagd is ${company.doeljaar}`
                  : ""}
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

      <p className="mt-3 text-xs text-slate-400">
        Status: {status.label}.
        {/* Secundair, want het zegt iets over de vórige ronde en niet over de
            actualiteit van het verslag. Als hoofdstatus zette het juist
            verouderde vondsten bovenaan.

            Het woord "nieuw" staat hier bewust níet: in deze module betekent
            "nieuw" het verslag over het doeljaar (zie `monitoringStatus`), en
            twee betekenissen van hetzelfde woord op één kaart is vragen om
            verwarring. De backend zet dit signaal alleen bij pipelinestatus
            'new' — een betere extractie op dezelfde URL ('updated') of een
            bekende bron die alsnog beoordeelbaar werd ('bronkaart_toegevoegd')
            hoort er niet onder, zie
            test_monitoring_dashboard_noemt_betere_extractie_geen_nieuw_jaarverslag. */}
        {company.nieuwe_bevinding
          ? " Sinds de vorige controle is er een recenter verslag gevonden."
          : ""}
        {" "}Monitoring vindt bronnen; kiezen doe je zelf.
      </p>
    </section>
  );
}
