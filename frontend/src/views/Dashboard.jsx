import {useEffect, useRef, useState} from "react";
import {AlertTriangle, BookOpen, FileUp, Play, RefreshCw, SearchCheck, Settings, Square, Trash2} from "lucide-react";
import {Shell} from "../components/Shell.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {Alert} from "../components/Alert.jsx";
import {BatchTimestamp} from "../components/BatchTimestamp.jsx";
import {Progress} from "../components/Progress.jsx";
import {LabelCounts} from "../components/LabelCounts.jsx";
import {StatusPill} from "../components/StatusPill.jsx";

export function Dashboard({api, user, onLogout, openBatch, openChatTemplates, openJaarverslagen, openMonitoring}) {
  const fileRef = useRef(null);
  const [batches, setBatches] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const list = await api.batches();
    const withLabels = await Promise.all(list.map(async (batch) => {
      try {
        return {...batch, ...(await api.batch(batch.id))};
      } catch {
        return batch;
      }
    }));
    setBatches(withLabels.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = window.setInterval(() => load().catch(() => {}), 3000);
    return () => window.clearInterval(timer);
  }, []);

  async function upload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const naam = file.name.replace(/\.[^.]+$/, "");
      const created = await api.uploadBatch(file, naam, new Date().getFullYear());
      await load();
      openBatch(created.batch_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  async function run(batchId) {
    setBusy(true);
    try {
      await api.runBatch(batchId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function cancel(batchId) {
    setBusy(true);
    try {
      await api.cancelBatch(batchId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteBatch(batchId, naam) {
    if (!window.confirm(`Batch "${naam}" definitief verwijderen?`)) return;
    setBusy(true);
    try {
      await api.deleteBatch(batchId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title=""
      actions={
        <>
          <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={upload} />
          <IconButton icon={BookOpen} variant="quiet" onClick={openJaarverslagen}>Jaarverslagen</IconButton>
          <IconButton icon={SearchCheck} variant="quiet" onClick={openMonitoring}>Jaarverslag-monitoring</IconButton>
          <IconButton icon={Settings} variant="quiet" onClick={openChatTemplates}>Chat-templates</IconButton>
          <IconButton icon={RefreshCw} onClick={() => load().catch((err) => setError(err.message))}>Verversen</IconButton>
          <IconButton icon={FileUp} variant="primary" onClick={() => fileRef.current?.click()} disabled={busy}>CSV uploaden</IconButton>
        </>
      }
    >
      {error ? <Alert message={error} /> : null}
      <div className="overflow-hidden rounded-lg border border-line bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-panel text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Batch</th>
              <th className="px-4 py-3">Aangemaakt</th>
              <th className="w-36 px-4 py-3">Voortgang</th>
              <th className="w-48 px-4 py-3">Labels</th>
              <th className="px-4 py-3">Status</th>
              <th className="w-40 px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {batches.map((batch) => (
              <tr key={batch.id} className="border-t border-line hover:bg-panel">
                <td className="px-4 py-3">
                  <button className="focus-ring rounded text-left font-semibold text-etil" onClick={() => openBatch(batch.id)}>
                    {batch.naam || batch.id}
                  </button>
                  <div className="text-xs text-slate-500">{batch.jaar}</div>
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">
                  <BatchTimestamp created_at={batch.created_at} completed_at={batch.completed_at} />
                </td>
                <td className="px-4 py-3">
                  <Progress value={batch.verwerkt || 0} total={batch.totaal || 0} />
                </td>
                <td className="px-4 py-3">
                  <LabelCounts labels={batch.labels} />
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusPill status={batch.status} />
                    {batch.fouten > 0 && (
                      <span className="inline-flex items-center gap-1 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs font-semibold text-red-700">
                        <AlertTriangle size={11} />{batch.fouten}
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="inline-flex items-center gap-2">
                    {batch.status === "running"
                      ? <IconButton icon={Square} variant="quiet" onClick={() => cancel(batch.id)} disabled={busy}>Annuleren</IconButton>
                      : <IconButton icon={Play} onClick={() => run(batch.id)} disabled={busy}>Run</IconButton>
                    }
                    <IconButton icon={Trash2} variant="quiet" onClick={() => deleteBatch(batch.id, batch.naam)} disabled={busy || batch.status === "running"} title="Batch verwijderen" />
                  </div>
                </td>
              </tr>
            ))}
            {!batches.length ? (
              <tr>
                <td className="px-4 py-8 text-center text-slate-500" colSpan="5">Geen batches</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
