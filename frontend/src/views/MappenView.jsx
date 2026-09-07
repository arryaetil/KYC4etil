import {useEffect, useRef, useState} from "react";
import {
  Archive, ArchiveRestore, ChevronLeft, Folder, FolderPlus, Inbox, Pencil,
  Trash2,
} from "lucide-react";
import {ActieMenu} from "../components/ActieMenu.jsx";
import {Alert} from "../components/Alert.jsx";
import {Dialog} from "../components/Dialog.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {
  archiveerBevestiging, lijstenLabel, mapActies, verwijderBevestiging,
} from "../lib/mappen.js";

const ACTIE_ICOON = {
  hernoemen: Pencil,
  archiveren: Archive,
  herstellen: ArchiveRestore,
  verwijderen: Trash2,
};
const ACTIE_LABEL = {
  hernoemen: "Hernoemen",
  archiveren: "Archiveren",
  herstellen: "Terugzetten",
  verwijderen: "Verwijderen",
};

export function MappenView({api, onOpenMap}) {
  const [mappen, setMappen] = useState([]);
  const [losseLijsten, setLosseLijsten] = useState(0);
  const [aantalGearchiveerd, setAantalGearchiveerd] = useState(0);
  const [toonArchief, setToonArchief] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // Eén dialoogstate in plaats van losse vlaggen: er kan er maar één tegelijk
  // open staan, en zo kan dat ook niet misgaan.
  const [dialoog, setDialoog] = useState(null);
  const naamRef = useRef(null);

  async function load(archief = toonArchief) {
    const data = await api.mappen(archief);
    setMappen(data.mappen || []);
    setLosseLijsten(data.losse_lijsten || 0);
    setAantalGearchiveerd(data.aantal_gearchiveerd || 0);
  }

  useEffect(() => {
    load(toonArchief).catch((err) => setError(err.message));
  }, [toonArchief]);

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

  function kies(actie, map) {
    if (actie === "hernoemen") return setDialoog({soort: "hernoemen", map});
    if (actie === "archiveren") {
      return setDialoog({...archiveerBevestiging(map), map});
    }
    if (actie === "herstellen") {
      return voerUit(() => api.herstelMap(map.id));
    }
    return setDialoog({...verwijderBevestiging(map), map});
  }

  function bevestigUitvoeren() {
    if (dialoog.soort === "archiveren") {
      return voerUit(() => api.archiveerMap(dialoog.map.id));
    }
    return voerUit(
      () => api.verwijderMap(dialoog.map.id, dialoog.ontkoppelLijsten),
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl px-6 py-8">
        <div className="mb-6 flex items-end justify-between gap-4">
          <div className="min-w-0">
            {toonArchief ? (
              <button
                type="button"
                onClick={() => setToonArchief(false)}
                className="focus-ring -ml-1 mb-1 inline-flex items-center gap-1 rounded-md px-1 py-0.5 text-sm text-mist-65 transition hover:text-ink"
              >
                <ChevronLeft size={16} />Alle mappen
              </button>
            ) : null}
            <h1 className="text-xl font-semibold text-ink">
              {toonArchief ? "Archief" : "Onderzoek"}
            </h1>
            <p className="mt-1 text-sm text-mist-65">
              {toonArchief
                ? "Gearchiveerde mappen. De lijsten erin zijn niet verwijderd."
                : "Kies een map om de lijsten erin te bekijken."}
            </p>
          </div>
          {!toonArchief ? (
            <IconButton
              icon={FolderPlus}
              variant="primary"
              disabled={busy}
              onClick={() => setDialoog({soort: "nieuw"})}
            >
              Nieuwe map
            </IconButton>
          ) : null}
        </div>

        {error ? <Alert message={error} /> : null}

        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {mappen.map((map) => (
            <li
              key={map.id}
              className="flex items-start gap-2 rounded-lg border border-line bg-white p-2 transition hover:border-mist-25 hover:shadow-sm"
            >
              <button
                type="button"
                onClick={() => onOpenMap(map.id, map.naam)}
                className="focus-ring flex min-w-0 flex-1 items-start gap-3 rounded-md p-2 text-left"
              >
                <Folder
                  size={20}
                  className={`mt-0.5 shrink-0 ${toonArchief ? "text-mist-25" : "text-mist-50"}`}
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-ink">
                    {map.naam}
                  </span>
                  <span className="mt-0.5 block text-xs text-mist-65">
                    {lijstenLabel(map.aantal_lijsten)}
                  </span>
                </span>
              </button>
              {/* Altijd zichtbaar. Acties die alleen bij hover verschijnen zijn
                  op touch onvindbaar én blijven klikbaar — een onzichtbare
                  verwijderknop precies waar iemand tikt om de map te openen. */}
              <ActieMenu
                label={`Acties voor "${map.naam}"`}
                items={mapActies(map, {gearchiveerd: toonArchief}).map((actie) => ({
                  label: ACTIE_LABEL[actie],
                  icon: ACTIE_ICOON[actie],
                  destructief: actie === "verwijderen",
                  onSelect: () => kies(actie, map),
                }))}
              />
            </li>
          ))}

          {!toonArchief && losseLijsten ? (
            <li className="rounded-lg border border-dashed border-line bg-white transition hover:border-mist-25">
              <button
                type="button"
                onClick={() => onOpenMap(null, "Zonder map")}
                className="focus-ring flex w-full items-start gap-3 rounded-lg p-4 text-left"
              >
                <Inbox size={20} className="mt-0.5 shrink-0 text-mist-50" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-ink">
                    Zonder map
                  </span>
                  <span className="mt-0.5 block text-xs text-mist-65">
                    {lijstenLabel(losseLijsten)}
                  </span>
                </span>
              </button>
            </li>
          ) : null}
        </ul>

        {!mappen.length ? (
          <div className="rounded-lg border border-dashed border-line py-16 text-center">
            <Folder size={22} className="mx-auto text-mist-25" />
            <p className="mt-3 text-sm text-mist-65">
              {toonArchief
                ? "Het archief is leeg."
                : "Nog geen mappen. Maak er een aan om je lijsten te ordenen."}
            </p>
          </div>
        ) : null}

        {!toonArchief && aantalGearchiveerd ? (
          <button
            type="button"
            onClick={() => setToonArchief(true)}
            className="focus-ring mt-6 inline-flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-mist-65 transition hover:text-ink"
          >
            <Archive size={16} />
            Archief bekijken ({aantalGearchiveerd})
          </button>
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
        open={
          dialoog?.soort === "archiveren"
          || Boolean(dialoog?.soort?.startsWith("verwijderen"))
        }
        titel={dialoog?.titel}
        beschrijving={dialoog?.beschrijving}
        onClose={() => setDialoog(null)}
      >
        <div className="flex flex-wrap justify-end gap-2">
          <IconButton onClick={() => setDialoog(null)} disabled={busy}>
            Annuleren
          </IconButton>
          <IconButton
            variant={dialoog?.soort === "archiveren" ? "primary" : "danger"}
            disabled={busy}
            onClick={bevestigUitvoeren}
          >
            {dialoog?.bevestigLabel}
          </IconButton>
        </div>
      </Dialog>
    </div>
  );
}
