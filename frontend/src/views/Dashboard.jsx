import {useEffect, useMemo, useRef, useState} from "react";
import {AlertTriangle, BookOpen, FileUp, Play, RefreshCw, SearchCheck, Settings, Square, Trash2} from "lucide-react";
import {Shell} from "../components/Shell.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {Alert} from "../components/Alert.jsx";
import {BatchTimestamp} from "../components/BatchTimestamp.jsx";
import {Progress} from "../components/Progress.jsx";
import {LabelCounts} from "../components/LabelCounts.jsx";
import {StatusPill} from "../components/StatusPill.jsx";
import {researchBevestiging} from "../lib/researchCost.js";

function isoWeekGrenzen(weekOffset) {
  const nu = new Date();
  const dagIndex = (nu.getDay() + 6) % 7; // maandag = 0
  const maandag = new Date(nu.getFullYear(), nu.getMonth(), nu.getDate() - dagIndex + weekOffset * 7);
  const volgendeMaandag = new Date(maandag.getFullYear(), maandag.getMonth(), maandag.getDate() + 7);
  return [maandag, volgendeMaandag];
}

export function Dashboard({api, user, onLogout, openBatch, openChatTemplates, openJaarverslagen, openMonitoring}) {
  const fileRef = useRef(null);
  const loadPromiseRef = useRef(null);
  const [batches, setBatches] = useState([]);
  const [periode, setPeriode] = useState("alle");
  const [vanaf, setVanaf] = useState("");
  const [tot, setTot] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    if (loadPromiseRef.current) return loadPromiseRef.current;
    const request = api.batches().then((list) => {
      setBatches(list.sort(
        (a, b) => (b.created_at || "").localeCompare(a.created_at || ""),
      ));
      return list;
    }).finally(() => {
      if (loadPromiseRef.current === request) loadPromiseRef.current = null;
    });
    loadPromiseRef.current = request;
    return request;
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  const heeftLopendeBatch = batches.some((batch) => batch.status === "running");

  useEffect(() => {
    if (!heeftLopendeBatch) return undefined;
    let stopped = false;
    let timer;
    const poll = async () => {
      try {
        await load();
      } catch {
        // Tijdelijke fout; probeer pas na de wachttijd opnieuw.
      } finally {
        if (!stopped) timer = window.setTimeout(poll, 10000);
      }
    };
    timer = window.setTimeout(poll, 10000);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [heeftLopendeBatch]);

  const gefilterd = useMemo(() => {
    if (periode === "alle") return batches;
    if (periode === "aangepast") {
      return batches.filter((batch) => {
        if (!batch.created_at) return false;
        const datum = batch.created_at.slice(0, 10);
        if (vanaf && datum < vanaf) return false;
        if (tot && datum > tot) return false;
        return true;
      });
    }
    const [van, totGrens] = isoWeekGrenzen(periode === "deze_week" ? 0 : -1);
    return batches.filter((batch) => {
      if (!batch.created_at) return false;
      const datum = new Date(batch.created_at);
      return datum >= van && datum < totGrens;
    });
  }, [batches, periode, vanaf, tot]);

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

  async function run(batch) {
    if (!window.confirm(researchBevestiging(batch.totaal))) return;
    setBusy(true);
    try {
      await api.runBatch(batch.id);
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
          <input ref={fileRef} type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" className="hidden" onChange={upload} />
          <IconButton icon={BookOpen} variant="quiet" onClick={openJaarverslagen}>Jaarverslagen</IconButton>
          <IconButton icon={SearchCheck} variant="quiet" onClick={openMonitoring}>Jaarverslag-monitoring</IconButton>
          <IconButton icon={Settings} variant="quiet" onClick={openChatTemplates}>Chat-templates</IconButton>
          <IconButton icon={RefreshCw} onClick={() => load().catch((err) => setError(err.message))}>Verversen</IconButton>
          <IconButton icon={FileUp} variant="primary" onClick={() => fileRef.current?.click()} disabled={busy}>Lijst uploaden</IconButton>
        </>
      }
    >
      {error ? <Alert message={error} /> : null}
      <div className="mb-4 flex flex-wrap items-center justify-end gap-2">
        <select className="focus-ring h-11 rounded-md border border-line bg-white px-3" value={periode} onChange={(event) => setPeriode(event.target.value)} aria-label="Filter op periode">
          <option value="alle">Alle periodes</option>
          <option value="deze_week">Deze week</option>
          <option value="vorige_week">Vorige week</option>
          <option value="aangepast">Aangepaste range</option>
        </select>
        {periode === "aangepast" ? (
          <>
            <input type="date" className="focus-ring h-11 rounded-md border border-line bg-white px-3" value={vanaf} onChange={(event) => setVanaf(event.target.value)} aria-label="Vanaf datum" />
            <input type="date" className="focus-ring h-11 rounded-md border border-line bg-white px-3" value={tot} onChange={(event) => setTot(event.target.value)} aria-label="Tot datum" />
          </>
        ) : null}
      </div>
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
            {gefilterd.map((batch) => (
              <tr key={batch.id} className="border-t border-line hover:bg-panel">
                <td className="px-4 py-3">
                  <button className="focus-ring rounded text-left font-semibold text-etil" onClick={() => openBatch(batch.id)}>
                    {batch.naam || batch.id}
                  </button>
                  <div className="text-xs text-slate-500">{batch.jaar}</div>
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">
                  <BatchTimestamp created_at={batch.created_at} completed_at={batch.completed_at} />
                  <div className="mt-1 text-xs text-slate-500">
                    Geüpload door {batch.geupload_door_naam || "Onbekend"}
                  </div>
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
                      : <IconButton icon={Play} onClick={() => run(batch)} disabled={busy}>Onderzoeken</IconButton>
                    }
                    <IconButton icon={Trash2} variant="quiet" onClick={() => deleteBatch(batch.id, batch.naam)} disabled={busy || batch.status === "running"} title="Batch verwijderen" />
                  </div>
                </td>
              </tr>
            ))}
            {!gefilterd.length ? (
              <tr>
                <td className="px-4 py-8 text-center text-slate-500" colSpan="5">
                  {batches.length ? "Geen batches in deze periode" : "Geen batches"}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
