import {useEffect, useRef, useState} from "react";
import {FileDown, FileUp, Play, Square, Trash2} from "lucide-react";
import {Alert} from "../components/Alert.jsx";
import {IconButton} from "../components/IconButton.jsx";

function formatDatum(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("nl-NL", {
    day: "numeric", month: "short", year: "numeric",
  });
}

export function BatchesView({api, onOpenBatch}) {
  const fileRef = useRef(null);
  const [batches, setBatches] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const lijst = await api.batches();
    setBatches(lijst.sort(
      (a, b) => (b.created_at || "").localeCompare(a.created_at || ""),
    ));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  const heeftLopende = batches.some((batch) => batch.status === "running");

  useEffect(() => {
    if (!heeftLopende) return undefined;
    const timer = window.setInterval(() => load().catch(() => {}), 10000);
    return () => window.clearInterval(timer);
  }, [heeftLopende]);

  async function upload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const naam = file.name.replace(/\.[^.]+$/, "");
      const created = await api.uploadBatch(file, naam, new Date().getFullYear());
      await load();
      onOpenBatch(created.batch_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  async function voerUit(actie) {
    setBusy(true);
    setError("");
    try {
      await actie();
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl px-6 py-8">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink">Onderzoek</h1>
          <p className="mt-1 text-sm text-slate-500">
            Kies een populatie om bronnen voor te beoordelen.
          </p>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          className="hidden"
          onChange={upload}
        />
        <IconButton
          icon={FileUp}
          variant="primary"
          onClick={() => fileRef.current?.click()}
          disabled={busy}
        >
          Lijst uploaden
        </IconButton>
      </div>

      {error ? <Alert message={error} /> : null}

      <ul className="divide-y divide-line border-y border-line">
        {batches.map((batch) => (
          <li key={batch.id} className="flex items-center gap-4 py-4">
            <div className="min-w-0 flex-1">
              <button
                type="button"
                onClick={() => onOpenBatch(batch.id)}
                className="focus-ring rounded text-left font-medium text-ink hover:underline"
              >
                {batch.naam || batch.id}
              </button>
              <div className="mt-0.5 text-xs text-slate-500">
                {batch.jaar} · {formatDatum(batch.created_at)}
                {batch.geupload_door_naam ? ` · ${batch.geupload_door_naam}` : ""}
              </div>
            </div>
            <div className="w-32 shrink-0 text-right text-xs tabular-nums text-slate-500">
              {batch.verwerkt || 0} / {batch.totaal || 0}
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {batch.status === "running" ? (
                <IconButton
                  icon={Square}
                  variant="quiet"
                  disabled={busy}
                  onClick={() => voerUit(() => api.cancelBatch(batch.id))}
                >
                  Stoppen
                </IconButton>
              ) : (
                <IconButton
                  icon={Play}
                  variant="quiet"
                  disabled={busy}
                  onClick={() => voerUit(() => api.runBatch(batch.id))}
                >
                  Onderzoeken
                </IconButton>
              )}
              <IconButton
                icon={FileDown}
                variant="quiet"
                title="Exporteren"
                disabled={busy}
                onClick={() => voerUit(() => api.download(
                  `/batches/${batch.id}/export.xlsx`, "export.xlsx",
                ))}
              />
              <IconButton
                icon={Trash2}
                variant="quiet"
                title="Verwijderen"
                disabled={busy || batch.status === "running"}
                onClick={() => {
                  if (!window.confirm(`Lijst "${batch.naam}" verwijderen?`)) return;
                  voerUit(() => api.deleteBatch(batch.id));
                }}
              />
            </div>
          </li>
        ))}
        {!batches.length ? (
          <li className="py-12 text-center text-sm text-slate-500">
            Nog geen lijsten. Upload een CSV- of Excel-bestand om te beginnen.
          </li>
        ) : null}
      </ul>
      </div>
    </div>
  );
}
