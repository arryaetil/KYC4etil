import {useEffect, useMemo, useState} from "react";
import {AlertTriangle, Check, FileDown, ListChecks, MessageSquare, Phone, Play, RefreshCw, Search, Square, Trash2} from "lucide-react";
import {classNames, pct} from "../lib/format.js";
import {Shell} from "../components/Shell.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {Alert} from "../components/Alert.jsx";
import {Metric} from "../components/Metric.jsx";
import {LabelCounts} from "../components/LabelCounts.jsx";
import {LabelBadge} from "../components/LabelBadge.jsx";
import {StatusPill} from "../components/StatusPill.jsx";

export function BatchView({api, user, onLogout, batchId, openDashboard, openCompany, openBellijst, openChatSessies}) {
  const [batch, setBatch] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [label, setLabel] = useState("");
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const labelParam = label === "fouten" ? "" : label;
    const [batchData, companyData] = await Promise.all([
      api.batch(batchId),
      api.companies(batchId, labelParam),
    ]);
    setBatch(batchData);
    setCompanies(companyData);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = window.setInterval(() => load().catch(() => {}), 3000);
    return () => window.clearInterval(timer);
  }, [batchId, label]);

  const sectoren = useMemo(() => Array.from(new Set(
    companies.map((company) => company.sbi_omschrijving).filter(Boolean),
  )).sort(), [companies]);

  const filtered = useMemo(() => companies.filter((company) => {
    if (label === "fouten") return !!company.pipeline_error;
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

  async function toggleAfgewerkt(company) {
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
            <IconButton icon={Play} variant="primary" onClick={runBatch} disabled={busy}>Run</IconButton>
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
      <div className="mb-4 grid gap-3 md:grid-cols-[1fr_200px_200px]">
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
        )} value={label} onChange={(event) => setLabel(event.target.value)} aria-label="Filter op confidence-label">
          <option value="">Alle labels</option>
          <option value="hoog">Eenduidig</option>
          <option value="middel">Twijfelachtig</option>
          <option value="laag">Onduidelijk</option>
          <option value="fouten">{batch?.fouten > 0 ? `Fouten (${batch.fouten})` : "Fouten"}</option>
        </select>
      </div>
      {batch ? (
        <div className="mb-4 grid gap-3 md:grid-cols-3">
          <Metric title="Voortgang" value={`${batch.verwerkt || 0}/${batch.totaal || 0}`} />
          <Metric title="Status" value={
            <div className="flex items-center gap-2">
              <StatusPill status={batch.status} />
              {batch.fouten > 0 && (
                <span className="inline-flex items-center gap-1 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs font-semibold text-red-700">
                  <AlertTriangle size={12} />{batch.fouten} {batch.fouten === 1 ? "fout" : "fouten"}
                </span>
              )}
            </div>
          } />
          <Metric title="Labels" value={<LabelCounts labels={batch.labels} />} />
        </div>
      ) : null}
      <div className="overflow-hidden rounded-lg border border-line bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-panel text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Vestiging</th>
              <th className="px-4 py-3">WP</th>
              <th className="px-4 py-3">Confidence</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Afgewerkt</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((company) => (
              <tr key={company.company_id} className="cursor-pointer border-t border-line hover:bg-panel" onClick={() => openCompany(batchId, company.company_id)}>
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
                <td className="px-4 py-3 font-medium">
                  {company.wp_kandidaat ?? (
                    company.wp_gevonden_ruw != null ? (
                      <span className="text-slate-400" title="Gevonden, maar niet bevestigd als kandidaat — controleer de bron">
                        {company.wp_gevonden_ruw}*
                      </span>
                    ) : "-"
                  )}
                </td>
                <td className="px-4 py-3">
                  {company.confidence_label ? (
                    <div className="flex items-center gap-3">
                      <LabelBadge label={company.confidence_label} />
                      <span className="text-xs text-slate-500">{pct(company.confidence_score)}%</span>
                    </div>
                  ) : "-"}
                </td>
                <td className="px-4 py-3"><StatusPill status={company.status} /></td>
                <td className="px-4 py-3" onClick={(event) => event.stopPropagation()}>
                  <input
                    type="checkbox"
                    className="focus-ring h-4 w-4 rounded border-line"
                    checked={!!company.afgewerkt}
                    onChange={() => toggleAfgewerkt(company)}
                    aria-label={`Markeer ${company.naam} als afgewerkt`}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
