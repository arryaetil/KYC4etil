import {useEffect, useRef, useState} from "react";
import {Folder, FolderPlus, Inbox, Pencil, Trash2} from "lucide-react";
import {Alert} from "../components/Alert.jsx";
import {Dialog} from "../components/Dialog.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {lijstenLabel, verwijderBevestiging} from "../lib/mappen.js";

export function MappenView({api, onOpenMap}) {
  const [mappen, setMappen] = useState([]);
  const [losseLijsten, setLosseLijsten] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // Eén dialoogstate in plaats van drie losse vlaggen: er kan er maar één
  // tegelijk open staan, en zo kan dat ook niet misgaan.
  const [dialoog, setDialoog] = useState(null);
  const naamRef = useRef(null);

  async function load() {
    const data = await api.mappen();
    setMappen(data.mappen || []);
    setLosseLijsten(data.losse_lijsten || 0);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  async function voerUit(actie) {
    setBusy(true);
    setError("");
    try {
      await actie();
      await load();
      setDialoog(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function bevestigVerwijderen(map) {
    setDialoog({...verwijderBevestiging(map), map});
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl px-6 py-8">
        <div className="mb-6 flex items-end justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-ink">Onderzoek</h1>
            <p className="mt-1 text-sm text-slate-500">
              Kies een map om de lijsten erin te bekijken.
            </p>
          </div>
          <IconButton
            icon={FolderPlus}
            variant="primary"
            disabled={busy}
            onClick={() => setDialoog({soort: "nieuw"})}
          >
            Nieuwe map
          </IconButton>
        </div>

        {error ? <Alert message={error} /> : null}

        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {mappen.map((map) => (
            <li
              key={map.id}
              className="group relative rounded-lg border border-line bg-white transition hover:border-slate-300 hover:shadow-sm"
            >
              <button
                type="button"
                onClick={() => onOpenMap(map.id, map.naam)}
                className="focus-ring flex w-full items-start gap-3 rounded-lg p-4 text-left"
              >
                <Folder size={20} className="mt-0.5 shrink-0 text-slate-400" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-ink">
                    {map.naam}
                  </span>
                  <span className="mt-0.5 block text-xs text-slate-500">
                    {lijstenLabel(map.aantal_lijsten)}
                  </span>
                </span>
              </button>
              {/* Acties verschijnen bij hover, maar blijven altijd bereikbaar
                  via het toetsenbord (focus-within). */}
              <div className="absolute right-2 top-2 flex gap-1 opacity-0 transition group-focus-within:opacity-100 group-hover:opacity-100">
                <IconButton
                  icon={Pencil}
                  variant="quiet"
                  title={`"${map.naam}" hernoemen`}
                  disabled={busy}
                  className="h-8 px-2"
                  onClick={() => setDialoog({soort: "hernoemen", map})}
                />
                <IconButton
                  icon={Trash2}
                  variant="quiet"
                  title={`"${map.naam}" verwijderen`}
                  disabled={busy}
                  className="h-8 px-2"
                  onClick={() => bevestigVerwijderen(map)}
                />
              </div>
            </li>
          ))}

          {losseLijsten ? (
            <li className="rounded-lg border border-dashed border-line bg-white transition hover:border-slate-300">
              <button
                type="button"
                onClick={() => onOpenMap(null, "Zonder map")}
                className="focus-ring flex w-full items-start gap-3 rounded-lg p-4 text-left"
              >
                <Inbox size={20} className="mt-0.5 shrink-0 text-slate-400" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-ink">
                    Zonder map
                  </span>
                  <span className="mt-0.5 block text-xs text-slate-500">
                    {lijstenLabel(losseLijsten)}
                  </span>
                </span>
              </button>
            </li>
          ) : null}
        </ul>

        {!mappen.length && !losseLijsten ? (
          <div className="rounded-lg border border-dashed border-line py-16 text-center">
            <Folder size={22} className="mx-auto text-slate-300" />
            <p className="mt-3 text-sm text-slate-500">
              Nog geen mappen. Maak er een aan om je lijsten te ordenen.
            </p>
          </div>
        ) : null}
      </div>

      <Dialog
        open={dialoog?.soort === "nieuw" || dialoog?.soort === "hernoemen"}
        titel={dialoog?.soort === "hernoemen" ? "Map hernoemen" : "Nieuwe map"}
        onClose={() => setDialoog(null)}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const naam = naamRef.current?.value.trim();
            if (!naam) return;
            voerUit(() => (dialoog.soort === "hernoemen"
              ? api.hernoemMap(dialoog.map.id, naam)
              : api.maakMap(naam)));
          }}
        >
          <label className="block text-sm font-medium text-ink" htmlFor="mapnaam">
            Naam
          </label>
          <input
            id="mapnaam"
            ref={naamRef}
            autoFocus
            maxLength={120}
            defaultValue={dialoog?.map?.naam || ""}
            placeholder="Bijvoorbeeld: Zorg 2026"
            className="focus-ring mt-1 w-full rounded-md border border-line px-3 py-2 text-sm"
          />
          <div className="mt-4 flex justify-end gap-2">
            <IconButton type="button" onClick={() => setDialoog(null)} disabled={busy}>
              Annuleren
            </IconButton>
            <IconButton type="submit" variant="primary" disabled={busy}>
              {dialoog?.soort === "hernoemen" ? "Opslaan" : "Map aanmaken"}
            </IconButton>
          </div>
        </form>
      </Dialog>

      <Dialog
        open={dialoog?.soort?.startsWith("verwijderen")}
        titel={dialoog?.titel}
        beschrijving={dialoog?.beschrijving}
        onClose={() => setDialoog(null)}
      >
        <div className="flex flex-wrap justify-end gap-2">
          <IconButton onClick={() => setDialoog(null)} disabled={busy}>
            Annuleren
          </IconButton>
          <IconButton
            variant="danger"
            disabled={busy}
            onClick={() => voerUit(() => api.verwijderMap(
              dialoog.map.id, dialoog.ontkoppelLijsten,
            ))}
          >
            {dialoog?.bevestigLabel}
          </IconButton>
        </div>
      </Dialog>

    </div>
  );
}
