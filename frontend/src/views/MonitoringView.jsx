import {Fragment, useEffect, useMemo, useState} from "react";
import {
  AlertTriangle, Building2, ChevronUp, FileSearch, RefreshCw,
  Search, SearchCheck, Sparkles,
} from "lucide-react";
import {classNames} from "../lib/format.js";
import {IconButton} from "../components/IconButton.jsx";
import {Alert} from "../components/Alert.jsx";
import {Metric} from "../components/Metric.jsx";
import {LabelBadge} from "../components/LabelBadge.jsx";
import {ResearchPanel} from "../components/ResearchPanel.jsx";

function formatDatumTijd(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleString("nl-NL", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function MonitoringView({api}) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [gestartOm, setGestartOm] = useState(null);
  const [zoek, setZoek] = useState("");
  const [filter, setFilter] = useState("alles");
  const [researchCompanyId, setResearchCompanyId] = useState(null);

  async function load() {
    const data = await api.monitoringStatus();
    setStatus(data);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = window.setInterval(() => load().catch(() => {}), 3000);
    return () => window.clearInterval(timer);
  }, []);

  async function nuControleren() {
    setBusy(true);
    setError("");
    try {
      await api.monitorRun();
      setGestartOm(new Date());
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const batch = status?.batch;
  const companies = status?.companies || [];
  const gefilterd = useMemo(() => companies.filter((company) => {
    const text = `${company.naam || ""} ${company.gemeente || ""}`.toLowerCase();
    const matchZoek = text.includes(zoek.toLowerCase());
    const matchFilter = filter === "alles"
      || (filter === "actie" && (company.fout || company.nieuwe_bevinding || !company.laatste_bron_url))
      || (filter === "gevonden" && company.laatste_bron_url);
    return matchZoek && matchFilter;
  }), [companies, filter, zoek]);

  return (
    <div className="px-6 py-6">
      {batch ? (
        <div className="mb-4 flex justify-end">
          <IconButton icon={RefreshCw} onClick={nuControleren} disabled={busy}>
            {busy ? "Bezig…" : "Nu controleren"}
          </IconButton>
        </div>
      ) : null}
      {error ? <Alert message={error} /> : null}
      {!batch ? (
        <div className="rounded-lg border border-dashed border-line bg-white p-8 text-center text-sm text-slate-600">
          Nog geen vaste monitorlijst ingesteld. Laat de backend-seed draaien om de jaarverslag-monitoring te starten.
        </div>
      ) : (
        <>
          <section className="mb-5 overflow-hidden rounded-lg border border-line bg-white">
            <div className="flex flex-col gap-4 border-b border-line px-5 py-5 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-etil text-white">
                  <Building2 size={20} />
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Actieve onderzoekspopulatie
                  </p>
                  <h2 className="mt-1 text-lg font-semibold text-ink">{batch.naam}</h2>
                  <p className="mt-1 text-sm text-slate-600">
                    Jaar {batch.jaar} · bronnen vinden, vergelijken en door een reviewer laten goedkeuren.
                  </p>
                </div>
              </div>
              <div className="text-sm text-slate-600">
                <span className="font-semibold text-ink">{status.gecontroleerd}</span> van {status.totaal} gecontroleerd
              </div>
            </div>
            <div className="grid divide-y divide-line sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-5">
              <Metric title="Organisaties" value={status.totaal} />
              <Metric title="Gecontroleerd" value={`${status.gecontroleerd}/${status.totaal}`} />
              <Metric title="Bron gevonden" value={`${status.bronnen_gevonden || 0}/${status.totaal}`} />
              <Metric title="Review nodig" value={
                <span className={classNames(status.nieuwe_bevindingen > 0 && "text-emerald-700")}>
                  {status.nieuwe_bevindingen}
                </span>
              } />
              <Metric title="Fouten" value={
                <span className={classNames(status.fouten > 0 && "text-red-600")}>{status.fouten}</span>
              } />
            </div>
          </section>
          {gestartOm ? (
            <p className="mb-4 rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
              Controle gestart om {formatDatumTijd(gestartOm.toISOString())}. Het overzicht ververst vanzelf.
            </p>
          ) : null}
          <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative w-full max-w-md">
              <Search className="pointer-events-none absolute left-3 top-3 text-slate-500" size={17} />
              <input className="focus-ring h-11 w-full rounded-md border border-line bg-white pl-9 pr-3" value={zoek} onChange={(event) => setZoek(event.target.value)} placeholder="Zoek organisatie of gemeente" aria-label="Zoeken op naam of gemeente" />
            </div>
            <div className="inline-flex w-fit rounded-md border border-line bg-white p-1" aria-label="Filter organisaties">
              {[
                ["alles", "Alles"],
                ["actie", "Actie nodig"],
                ["gevonden", "Bron gevonden"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={filter === value}
                  onClick={() => setFilter(value)}
                  className={classNames(
                    "focus-ring rounded px-3 py-2 text-sm font-medium",
                    filter === value ? "bg-ink text-white" : "text-slate-600 hover:bg-panel",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <p className="mb-3 text-xs text-slate-500">
            {gefilterd.length} van {companies.length} organisaties zichtbaar
          </p>
          <div className="overflow-x-auto rounded-lg border border-line bg-white">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-panel text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Organisatie</th>
                  <th className="px-4 py-3">Laatst gecontroleerd</th>
                  <th className="px-4 py-3">Laatste bron</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Onderzoek</th>
                </tr>
              </thead>
              <tbody>
                {gefilterd.map((company) => (
                  <Fragment key={company.company_id}>
                    <tr className="border-t border-line hover:bg-panel">
                      <td className="px-4 py-3">
                        <div className="font-semibold">{company.naam}</div>
                        <div className="text-xs text-slate-500">{company.gemeente}</div>
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {formatDatumTijd(company.laatst_gecontroleerd_op) || (
                          <span className="text-slate-500">Nog niet gecontroleerd</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {company.laatste_bron_url ? (
                          <a
                            href={company.laatste_bron_url}
                            target="_blank" rel="noreferrer"
                            onClick={(event) => event.stopPropagation()}
                            className="text-etil underline"
                          >
                            Bron openen
                          </a>
                        ) : (
                          <span className="text-slate-500">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {company.fout ? (
                          <span className="inline-flex items-center gap-1 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs font-semibold text-red-700" title={company.fout}>
                            <AlertTriangle size={11} />Fout
                          </span>
                        ) : company.nieuwe_bevinding ? (
                          <div className="flex items-center gap-2">
                            <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-800">
                              <Sparkles size={11} />Nieuwe bevinding
                            </span>
                            {company.wp_kandidaat != null && <LabelBadge label={company.confidence_label} />}
                          </div>
                        ) : !company.laatste_bron_url ? (
                          <span className="inline-flex items-center gap-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-800">
                            <FileSearch size={11} />Bron ontbreekt
                          </span>
                        ) : (
                          <span className="text-slate-500">Geen wijziging</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <IconButton
                          icon={researchCompanyId === company.company_id ? ChevronUp : SearchCheck}
                          variant="quiet"
                          aria-expanded={researchCompanyId === company.company_id}
                          onClick={(event) => {
                            event.stopPropagation();
                            setResearchCompanyId((current) => (
                              current === company.company_id ? null : company.company_id
                            ));
                          }}
                        >
                          {researchCompanyId === company.company_id ? "Sluiten" : "Brononderzoek"}
                        </IconButton>
                      </td>
                    </tr>
                    {researchCompanyId === company.company_id ? (
                      <tr className="border-t border-line">
                        <td colSpan="5" className="p-0">
                          <ResearchPanel api={api} company={company} batchJaar={batch.jaar} />
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                ))}
                {!gefilterd.length ? (
                  <tr>
                    <td className="px-4 py-8 text-center text-slate-500" colSpan="5">
                      {companies.length ? "Geen resultaten voor deze zoekopdracht" : "Geen organisaties in de watchlist"}
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
