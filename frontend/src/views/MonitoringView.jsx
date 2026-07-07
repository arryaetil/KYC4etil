import {useEffect, useState} from "react";
import {AlertTriangle, ListChecks, RefreshCw, Sparkles} from "lucide-react";
import {classNames} from "../lib/format.js";
import {Shell} from "../components/Shell.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {Alert} from "../components/Alert.jsx";
import {Metric} from "../components/Metric.jsx";
import {LabelBadge} from "../components/LabelBadge.jsx";

function formatDatumTijd(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleString("nl-NL", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function MonitoringView({api, user, onLogout, batchId, openBatch, openCompany}) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [gestartOm, setGestartOm] = useState(null);

  async function load() {
    const data = await api.monitoringStatus(batchId);
    setStatus(data);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = window.setInterval(() => load().catch(() => {}), 3000);
    return () => window.clearInterval(timer);
  }, [batchId]);

  async function nuControleren() {
    setBusy(true);
    setError("");
    try {
      await api.monitorBatch(batchId);
      setGestartOm(new Date());
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const companies = status?.companies || [];

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title="Jaarverslag-monitoring"
      actions={
        <>
          <IconButton icon={ListChecks} onClick={() => openBatch(batchId)}>Batchoverzicht</IconButton>
          <IconButton icon={RefreshCw} variant="primary" onClick={nuControleren} disabled={busy}>
            {busy ? "Bezig…" : "Nu controleren"}
          </IconButton>
        </>
      }
    >
      {error ? <Alert message={error} /> : null}
      {gestartOm ? (
        <p className="mb-4 text-sm text-slate-500">
          Controle gestart om {formatDatumTijd(gestartOm.toISOString())} — dit kan enkele minuten duren
          voor grote lijsten; het overzicht ververst vanzelf.
        </p>
      ) : null}
      {status ? (
        <div className="mb-4 grid gap-3 md:grid-cols-4">
          <Metric title="Totaal" value={status.totaal} />
          <Metric title="Gecontroleerd" value={`${status.gecontroleerd}/${status.totaal}`} />
          <Metric title="Nieuwe bevindingen" value={
            <span className={classNames(status.nieuwe_bevindingen > 0 && "text-emerald-700")}>
              {status.nieuwe_bevindingen}
            </span>
          } />
          <Metric title="Fouten" value={
            <span className={classNames(status.fouten > 0 && "text-red-600")}>{status.fouten}</span>
          } />
        </div>
      ) : null}
      <div className="overflow-hidden rounded-lg border border-line bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-panel text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Vestiging</th>
              <th className="px-4 py-3">Laatst gecontroleerd</th>
              <th className="px-4 py-3">Laatste bron</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {companies.map((company) => {
              const klikbaar = company.nieuwe_bevinding;
              return (
                <tr
                  key={company.company_id}
                  className={classNames("border-t border-line", klikbaar && "cursor-pointer hover:bg-panel")}
                  onClick={klikbaar ? () => openCompany(batchId, company.company_id) : undefined}
                >
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
                      <span className="text-slate-500">—</span>
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
                    ) : (
                      <span className="text-slate-500">Geen wijziging</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {!companies.length ? (
              <tr>
                <td className="px-4 py-8 text-center text-slate-500" colSpan="4">Geen vestigingen in deze batch</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
