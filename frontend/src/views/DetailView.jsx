import {useEffect, useState} from "react";
import {AlertTriangle, ListChecks} from "lucide-react";
import {classNames, bronLink} from "../lib/format.js";
import {deriveZekerheid} from "../lib/zekerheid.js";
import {Shell} from "../components/Shell.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {Alert} from "../components/Alert.jsx";
import {Panel} from "../components/Panel.jsx";
import {ZEKERHEID_NIVEAU_STYLE} from "../components/detail/constants.js";
import {BronModal} from "../components/detail/BronModal.jsx";
import {VestigingsgegevensKaart} from "../components/detail/VestigingsgegevensKaart.jsx";
import {ContactgegevensKaart} from "../components/detail/ContactgegevensKaart.jsx";
import {WpUitsplitsing} from "../components/detail/WpUitsplitsing.jsx";
import {VastgoedKaart} from "../components/detail/VastgoedKaart.jsx";
import {ScoreBreakdown} from "../components/detail/ScoreBreakdown.jsx";
import {VorigJaarVergelijking} from "../components/detail/VorigJaarVergelijking.jsx";
import {WpKaart} from "../components/detail/WpKaart.jsx";
import {OutboundPanel} from "../components/detail/OutboundPanel.jsx";

function BronKaart({result, onOpenPdf}) {
  const zekerheid = deriveZekerheid(result);
  const isJaarverslag = result.bron_type === "jaarverslag" && result.bron_pagina;
  return (
    <div className="rounded-md border border-line bg-panel p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold">{result.agent_type} — WP {result.wp_gevonden ?? "-"}</div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={classNames("rounded px-1.5 py-0.5 text-xs font-semibold", ZEKERHEID_NIVEAU_STYLE[zekerheid.niveau])}
            title={zekerheid.uitleg}
          >
            {zekerheid.label}
          </span>
          {result.is_fte && (
            <span className="rounded bg-red-100 px-1.5 py-0.5 text-xs font-semibold text-red-800">FTE</span>
          )}
          <span className="text-xs text-slate-500">{result.bron_type} · {result.peilmoment || "geen peilmoment"}</span>
        </div>
      </div>
      <blockquote className="border-l-4 border-etil pl-3 text-sm text-slate-700">{result.context || "Geen citaat"}</blockquote>
      {result.bron_url ? (
        isJaarverslag ? (
          <button
            type="button"
            className="focus-ring mt-2 inline-block text-sm font-medium text-etil underline"
            onClick={() => onOpenPdf(result)}
          >
            Bron bekijken (pagina {result.bron_pagina})
          </button>
        ) : (
          <a className="mt-2 inline-block text-sm font-medium text-etil underline" href={bronLink(result)} target="_blank" rel="noreferrer">
            Bron openen
          </a>
        )
      ) : null}
    </div>
  );
}

function BronnenSectie({agentResults}) {
  const [pdfBron, setPdfBron] = useState(null);
  const hoofdbronnen = (agentResults || []).filter((r) => r.agent_type !== "extra_bron");
  const extraBronnen = (agentResults || []).filter((r) => r.agent_type === "extra_bron");
  return (
    <section className="space-y-3 rounded-lg border border-line bg-white p-4 shadow-sm">
      <h2 className="text-base font-semibold">Bronnen</h2>
      <div className="space-y-3">
        {hoofdbronnen.map((result, index) => (
          <BronKaart key={`hoofd-${result.agent_type}-${index}`} result={result} onOpenPdf={setPdfBron} />
        ))}
        {!hoofdbronnen.length ? <div className="text-sm text-slate-500">Geen bronresultaten</div> : null}
      </div>
      {extraBronnen.length ? (
        <div className="space-y-2 border-t border-line pt-3">
          <h3 className="text-sm font-semibold text-slate-500">Extra context — telt niet mee in score</h3>
          <div className="space-y-2 opacity-75">
            {extraBronnen.map((result, index) => (
              <BronKaart key={`extra-${index}`} result={result} onOpenPdf={setPdfBron} />
            ))}
          </div>
        </div>
      ) : null}
      <BronModal
        open={pdfBron !== null}
        onClose={() => setPdfBron(null)}
        bronUrl={pdfBron?.bron_url}
        pagina={pdfBron?.bron_pagina}
        citaat={pdfBron?.context}
        titel={pdfBron ? `${pdfBron.agent_type} — WP ${pdfBron.wp_gevonden ?? "-"}` : ""}
      />
    </section>
  );
}

export function DetailView({api, user, onLogout, batchId, companyId, openBatch}) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setDetail(await api.company(batchId, companyId));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, [batchId, companyId]);

  const candidate = detail?.candidate;

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title={detail?.company?.naam || "Vestiging"}
      actions={<IconButton icon={ListChecks} onClick={() => openBatch(batchId)}>Batchoverzicht</IconButton>}
    >
      {error ? <Alert message={error} /> : null}
      {detail ? (
        <div className="grid gap-5 lg:grid-cols-[2fr_1fr]">
          <section className="space-y-5">
            {candidate?.reviewer_signaal ? (
              <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                <AlertTriangle size={17} className="mt-0.5 shrink-0" />
                <span>{candidate.reviewer_signaal}</span>
              </div>
            ) : null}
            <BronnenSectie agentResults={detail.agent_results} />
            <VestigingsgegevensKaart
              company={detail.company}
              enrichment={detail.enrichment}
              api={api}
              batchId={batchId}
              onRefresh={load}
            />
            <ContactgegevensKaart
              enrichment={detail.enrichment}
              vastgoed={detail?.vastgoed}
              api={api}
              batchId={batchId}
              companyId={companyId}
              onRefresh={load}
            />
            <WpUitsplitsing wp_historie={detail?.wp_historie} agent_results={detail?.agent_results} api={api} batchId={batchId} companyId={companyId} onRefresh={load} />
            <VastgoedKaart api={api} batchId={batchId} companyId={companyId} vastgoed={detail?.vastgoed} />
            <Panel title="Score-uitleg" collapsible defaultOpen={false}>
              <ScoreBreakdown breakdown={candidate?.score_breakdown} label={candidate?.confidence_label} />
            </Panel>
            <VorigJaarVergelijking vorig_jaar={detail?.vorig_jaar} huidig_wp={candidate?.wp_kandidaat} collapsible />
            {detail.pipeline_fouten?.length > 0 && (
              <Panel title="Pipeline-fouten">
                <div className="space-y-2">
                  {detail.pipeline_fouten.map((f, i) => (
                    <div key={i} className="rounded-md border border-red-200 bg-red-50 p-3 text-sm">
                      <div className="mb-1 flex items-center gap-2 font-semibold text-red-800">
                        <AlertTriangle size={14} />{f.stap}
                      </div>
                      <pre className="overflow-x-auto whitespace-pre-wrap break-all font-mono text-xs text-red-700">{f.error}</pre>
                    </div>
                  ))}
                </div>
              </Panel>
            )}
          </section>
          <aside className="space-y-5">
            <WpKaart
              candidate={candidate}
              wp_historie={detail?.wp_historie}
              vorig_jaar={detail?.vorig_jaar}
              api={api}
              onRefresh={load}
            />
            <OutboundPanel
              candidate={candidate}
              api={api}
              batchId={batchId}
              companyId={companyId}
              onRefresh={load}
            />
          </aside>
        </div>
      ) : null}
    </Shell>
  );
}
