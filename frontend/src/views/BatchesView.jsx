import {useEffect, useRef, useState} from "react";
import {ChevronLeft, FileDown, FileUp, Play, Square, Trash2} from "lucide-react";
import {Alert} from "../components/Alert.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {researchBevestiging} from "../lib/researchCost.js";
import {magUploaden} from "../lib/mappen.js";

function formatDatum(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("nl-NL", {
    day: "numeric", month: "short", year: "numeric",
  });
}

export function BatchesView({api, onOpenBatch, mapId, mapNaam, onTerug}) {
  const fileRef = useRef(null);
  const [batches, setBatches] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const lijst = await api.batches(mapId);
    setBatches(lijst.sort(
      (a, b) => (b.created_at || "").localeCompare(a.created_at || ""),
    ));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, [mapId]);

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
      const created = await api.uploadBatch(
        file, naam, new Date().getFullYear(), mapId,
      );
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

  function startOnderzoek(batch) {
    if (!window.confirm(researchBevestiging(batch.totaal))) return;
    voerUit(() => api.runBatch(batch.id));
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl px-6 py-8">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div className="min-w-0">
          {onTerug ? (
            <button
              type="button"
              onClick={onTerug}
              className="focus-ring -ml-1 mb-1 inline-flex items-center gap-1 rounded-md px-1 py-0.5 text-sm text-slate-500 transition hover:text-ink"
            >
              <ChevronLeft size={16} />Alle mappen
            </button>
          ) : null}
          <h1 className="truncate text-xl font-semibold text-ink">
            {mapNaam || "Onderzoek"}
          </h1>
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
        {magUploaden(mapId) ? (
          <IconButton
            icon={FileUp}
            variant="primary"
            onClick={() => fileRef.current?.click()}
            disabled={busy}
          >
            Lijst uploaden
          </IconButton>
        ) : null}
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
                  onClick={() => startOnderzoek(batch)}
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
            {mapNaam && mapId !== undefined
              ? `Nog geen lijsten in "${mapNaam}". Upload een CSV- of Excel-bestand om te beginnen.`
              : "Nog geen lijsten. Upload een CSV- of Excel-bestand om te beginnen."}
          </li>
        ) : null}
      </ul>
      </div>
    </div>
  );
}
