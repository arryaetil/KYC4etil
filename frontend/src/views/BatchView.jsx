import {Fragment, useEffect, useMemo, useRef, useState} from "react";
import {
  AlertTriangle, Check, ChevronUp, ExternalLink, FileDown, FlaskConical,
  ListChecks, MessageSquare, Phone, Play, RefreshCw, Search, SearchCheck,
  Square, Trash2,
} from "lucide-react";
import {classNames} from "../lib/format.js";
import {Shell} from "../components/Shell.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {Alert} from "../components/Alert.jsx";
import {Metric} from "../components/Metric.jsx";
import {StatusPill} from "../components/StatusPill.jsx";
import {ResearchPanel} from "../components/ResearchPanel.jsx";

export function BatchView({api, user, onLogout, batchId, openDashboard, openCompany, openBellijst, openChatSessies}) {
  const [batch, setBatch] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [label, setLabel] = useState("");
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [researchCompanyId, setResearchCompanyId] = useState(null);
  const [afgewerktBezig, setAfgewerktBezig] = useState(new Set());
  const loadPromiseRef = useRef(null);

  async function load() {
    if (loadPromiseRef.current) return loadPromiseRef.current;
    const request = Promise.all([
      api.batch(batchId),
      api.companies(batchId, ""),
    ]).then(([batchData, companyData]) => {
      setBatch(batchData);
      setCompanies(companyData);
      return batchData;
    }).finally(() => {
      if (loadPromiseRef.current === request) loadPromiseRef.current = null;
    });
    loadPromiseRef.current = request;
    return request;
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, [batchId]);

  useEffect(() => {
    if (batch?.status !== "running") return undefined;
    let stopped = false;
    let timer;
    const poll = async () => {
      try {
        await load();
      } catch {
        // Een tijdelijke netwerkfout wordt bij de volgende poll opnieuw geprobeerd.
      } finally {
        if (!stopped) timer = window.setTimeout(poll, 5000);
      }
    };
    timer = window.setTimeout(poll, 5000);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [batch?.status, batchId]);

  const sectoren = useMemo(() => Array.from(new Set(
    companies.map((company) => company.sbi_omschrijving).filter(Boolean),
  )).sort(), [companies]);

  const filtered = useMemo(() => companies.filter((company) => {
    if (label === "review" && company.research_review_status !== "voorgesteld") return false;
    if (label === "accepted" && company.research_review_status !== "geaccepteerd") return false;
    if (label === "difference" && company.vergelijking !== "afwijkend") return false;
    if (label === "errors" && company.research_status !== "error") return false;
    if (label === "missing" && company.research_resultaat_status !== "niet_gevonden") return false;
    if (sector && company.sbi_omschrijving !== sector) return false;
    const text = `${company.naam || ""} ${company.gemeente || ""} ${company.vestigingsnummer || ""} ${company.cb_er || ""} ${company.kvk_nummer || ""}`.toLowerCase();
    return text.includes(search.toLowerCase());
  }), [companies, label, search, sector]);

  async function approveAll() {
    try {
      await api.approveAllGreen(batchId);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function runBatch() {
    if (!window.confirm(
      `Autonoom bronnenonderzoek starten voor ${batch?.totaal || 0} organisaties?\n\n` +
      "Verwachte externe kosten voor 20 organisaties: circa $0,70–$1,50. " +
      "De agent stelt bronnen voor; een reviewer blijft beslissen.",
    )) return;
    setBusy(true);
    setError("");
    try {
      await api.runBatch(batchId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function runLegacyBatch() {
    if (!window.confirm(
      "Legacy WP-pipeline draaien voor interne vergelijking?\n\n" +
      "Dit is niet langer de standaardworkflow.",
    )) return;
    setBusy(true);
    setError("");
    try {
      await api.runLegacyBatch(batchId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function cancelBatch() {
    setBusy(true);
    setError("");
    try {
      await api.cancelBatch(batchId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function resetVastgelopen() {
    if (!window.confirm("Batch terugzetten naar 'pending'?\n\nAlleen doen als de server herstart is en de taak echt niet meer draait.")) return;
    setBusy(true);
    setError("");
    try {
      await api.resetVastgelopen(batchId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleAfgewerkt(company) {
    if (afgewerktBezig.has(company.company_id)) return;
    setAfgewerktBezig((huidige) => new Set(huidige).add(company.company_id));
    const nieuweWaarde = !company.afgewerkt;
    setCompanies((huidige) => huidige.map((c) =>
      c.company_id === company.company_id ? {...c, afgewerkt: nieuweWaarde} : c
    ));
    try {
      await api.updateCompany(batchId, company.company_id, {afgewerkt: nieuweWaarde});
    } catch (err) {
      setCompanies((huidige) => huidige.map((c) =>
        c.company_id === company.company_id ? {...c, afgewerkt: company.afgewerkt} : c
      ));
      setError(err.message);
    } finally {
      setAfgewerktBezig((huidige) => {
        const volgende = new Set(huidige);
        volgende.delete(company.company_id);
        return volgende;
      });
    }
  }

  async function deleteBatch() {
    if (!window.confirm(`Batch "${batch?.naam}" definitief verwijderen?`)) return;
    setBusy(true);
    try {
      await api.deleteBatch(batchId);
      openDashboard();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  const isRunning = batch?.status === "running";

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title={batch?.naam || "Batch"}
      actions={
        <>
          <IconButton icon={ListChecks} onClick={openDashboard}>Dashboard</IconButton>
          {isRunning ? (
            <>
              <IconButton icon={Square} variant="quiet" onClick={cancelBatch} disabled={busy}>Annuleren</IconButton>
              <IconButton icon={RefreshCw} variant="quiet" onClick={resetVastgelopen} disabled={busy} title="Gebruik alleen na server-herstart als de taak niet meer draait">Vastgelopen?</IconButton>
            </>
          ) : (
            <>
              <IconButton icon={Play} variant="primary" onClick={runBatch} disabled={busy}>
                Bronnenonderzoek starten
              </IconButton>
              <IconButton icon={FlaskConical} variant="quiet" onClick={runLegacyBatch} disabled={busy}>
                Legacy vergelijken
              </IconButton>
            </>
          )}
          <IconButton icon={Check} onClick={approveAll} disabled={isRunning}>Eenduidige goedkeuren</IconButton>
          <IconButton icon={FileDown} onClick={() => api.download(`/batches/${batchId}/export.xlsx`, "export.xlsx")}>Export</IconButton>
          <IconButton icon={Phone} onClick={() => openBellijst(batchId)}>Bellijst</IconButton>
          <div className="relative inline-flex">
            <IconButton icon={MessageSquare} onClick={() => openChatSessies(batchId)}>Chat-sessies</IconButton>
            {batch?.chat_sessies_open > 0 && (
              <span className="pointer-events-none absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-xs font-bold text-white">
                {batch.chat_sessies_open}
              </span>
            )}
          </div>
          <IconButton icon={Trash2} variant="quiet" onClick={deleteBatch} disabled={busy || isRunning} title="Batch verwijderen" />
        </>
      }
    >
      {error ? <Alert message={error} /> : null}
      <section className="mb-5 border-y border-line bg-white">
        <div className="flex flex-col gap-3 px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-base font-semibold text-ink">Autonome bronnenresearch</h2>
            <p className="mt-1 max-w-3xl text-sm text-slate-600">
              De agent onderzoekt websites, openbare documenten en recente media.
              Resultaten worden pas definitief nadat een reviewer een primaire bron kiest.
            </p>
          </div>
          <div className="text-sm text-slate-600">
            {batch?.research?.gestart || 0} van {batch?.totaal || 0} onderzoeken gestart
          </div>
        </div>
        {batch ? (
          <div className="grid border-t border-line sm:grid-cols-3 lg:grid-cols-6">
            <Metric title="Voortgang" value={`${batch.verwerkt || 0}/${batch.totaal || 0}`} />
            <Metric title="Review nodig" value={batch.research?.review_nodig || 0} />
            <Metric title="Geaccepteerd" value={batch.research?.geaccepteerd || 0} />
            <Metric title="Niet gevonden" value={batch.research?.niet_gevonden || 0} />
            <Metric title="Fouten" value={batch.research?.fouten || 0} />
            <Metric title="Batchstatus" value={<StatusPill status={batch.status} />} />
          </div>
        ) : null}
      </section>
      <div className="mb-4 grid gap-3 md:grid-cols-[1fr_200px_220px]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-3 text-slate-500" size={17} />
          <input className="focus-ring h-11 w-full rounded-md border border-line bg-white pl-9 pr-3" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Zoeken op naam, gemeente, vestigingsnummer, CBR of KvK" aria-label="Zoeken op naam, gemeente, vestigingsnummer, CBR of KvK-nummer" />
        </div>
        <select className="focus-ring h-11 rounded-md border border-line bg-white px-3" value={sector} onChange={(event) => setSector(event.target.value)} aria-label="Filter op sector">
          <option value="">Alle sectoren</option>
          {sectoren.map((naam) => <option key={naam} value={naam}>{naam}</option>)}
        </select>
        <select className={classNames(
          "focus-ring h-11 rounded-md border bg-white px-3",
          label === "fouten" ? "border-red-400 text-red-700 font-medium" : "border-line",
        )} value={label} onChange={(event) => setLabel(event.target.value)} aria-label="Filter op researchstatus">
          <option value="">Alle onderzoeksstatussen</option>
          <option value="review">Review nodig</option>
          <option value="accepted">Bron geaccepteerd</option>
          <option value="difference">Afwijkend van legacy</option>
          <option value="missing">Geen bron gevonden</option>
          <option value="errors">Onderzoeksfouten</option>
        </select>
      </div>
      <div className="overflow-x-auto rounded-lg border border-line bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-panel text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Vestiging</th>
              <th className="px-4 py-3">Voorgestelde bron</th>
              <th className="px-4 py-3">Research-WP</th>
              <th className="px-4 py-3">Legacy-WP</th>
              <th className="px-4 py-3">Vergelijking</th>
              <th className="px-4 py-3">Review</th>
              <th className="px-4 py-3">Afgewerkt</th>
              <th className="px-4 py-3 text-right">Actie</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((company) => (
              <Fragment key={company.company_id}>
              <tr className="border-t border-line hover:bg-panel">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="font-semibold">{company.naam}</div>
                    {company.pipeline_error && <AlertTriangle size={14} className="shrink-0 text-red-500" />}
                  </div>
                  <div className="text-xs text-slate-500">{company.gemeente}</div>
                  {company.pipeline_error && (
                    <div className="mt-1 max-w-xs truncate text-xs font-medium text-red-600" title={company.pipeline_error}>
                      {company.pipeline_error}
                    </div>
                  )}
                </td>
                <td className="max-w-xs px-4 py-3">
                  {company.research_top_url ? (
                    <a href={company.research_top_url} target="_blank" rel="noreferrer" className="focus-ring inline-flex max-w-full items-center gap-1 font-medium text-etil underline">
                      <span className="truncate">{company.research_top_titel || "Bron openen"}</span>
                      <ExternalLink size={13} className="shrink-0" />
                    </a>
                  ) : (
                    <span className="text-slate-500">
                      {company.research_status === "running" ? "Onderzoek loopt…" : "Nog geen bron"}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {company.research_top_wp_bruikbaar ? (
                    <span className="font-semibold">{company.research_top_wp}</span>
                  ) : company.research_top_wp_raw != null ? (
                    <span
                      className="text-amber-800"
                      title={`Niet bruikbaar als vestigings-WP; scope: ${company.research_top_scope || "onbekend"}`}
                    >
                      {company.research_top_wp_raw}*
                    </span>
                  ) : "—"}
                </td>
                <td className="px-4 py-3 text-slate-600">{company.legacy_wp ?? "—"}</td>
                <td className="px-4 py-3">
                  {company.vergelijking === "gelijk" ? (
                    <span className="text-emerald-700">Gelijk</span>
                  ) : company.vergelijking === "afwijkend" ? (
                    <span className="font-medium text-amber-800">
                      {company.verschil_abs > 0 ? "+" : ""}{company.verschil_abs}
                    </span>
                  ) : (
                    <span className="text-slate-500">Nog niet vergelijkbaar</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <StatusPill status={
                    company.research_review_status === "geaccepteerd"
                      ? "approved"
                      : company.research_status
                  } />
                </td>
                <td className="px-4 py-3" onClick={(event) => event.stopPropagation()}>
                  <input
                    type="checkbox"
                    className="focus-ring h-4 w-4 rounded border-line"
                    checked={!!company.afgewerkt}
                    disabled={afgewerktBezig.has(company.company_id)}
                    onChange={() => toggleAfgewerkt(company)}
                    aria-label={`Markeer ${company.naam} als afgewerkt`}
                  />
                </td>
                <td className="px-4 py-3 text-right">
                  <IconButton
                    icon={researchCompanyId === company.company_id ? ChevronUp : SearchCheck}
                    variant="quiet"
                    onClick={() => setResearchCompanyId((current) => (
                      current === company.company_id ? null : company.company_id
                    ))}
                  >
                    {researchCompanyId === company.company_id ? "Sluiten" : "Beoordelen"}
                  </IconButton>
                </td>
              </tr>
              {researchCompanyId === company.company_id ? (
                <tr className="border-t border-line">
                  <td colSpan="8" className="p-0">
                    <ResearchPanel api={api} company={company} batchJaar={batch?.jaar} />
                  </td>
                </tr>
              ) : null}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
