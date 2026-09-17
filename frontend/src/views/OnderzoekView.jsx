import {useEffect, useState} from "react";
import {ChevronLeft, Play, Square} from "lucide-react";
import {Alert} from "../components/Alert.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {researchBevestiging} from "../lib/researchCost.js";
import {BatchesView} from "./BatchesView.jsx";
import {MappenView} from "./MappenView.jsx";
import {OrganisatieLijst} from "../components/onderzoek/OrganisatieLijst.jsx";
import {BedrijfToevoegen} from "../components/onderzoek/BedrijfToevoegen.jsx";
import {KandidatenPaneel} from "../components/onderzoek/KandidatenPaneel.jsx";
import {BewijsPaneel} from "../components/onderzoek/BewijsPaneel.jsx";
import {bekijkBewijs} from "../lib/evidenceLink.js";
import {useIsXl} from "../lib/useBreakpoint.js";

export function OnderzoekView({api}) {
  const isXl = useIsXl();
  // Drie niveaus: mappen → lijsten in een map → organisaties in een lijst.
  // `undefined` betekent "nog geen map gekozen"; `null` is de virtuele map
  // met lijsten die buiten elke map vallen, en dat is een geldige keuze.
  const [map, setMap] = useState(undefined);
  const [batchId, setBatchId] = useState(null);
  const [batch, setBatch] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [geselecteerdId, setGeselecteerdId] = useState(null);
  const [geselecteerdeBron, setGeselecteerdeBron] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // Zelfde bron als in het lijstoverzicht: het bedrag per organisatie komt uit
  // de vorige runs, niet uit een getal in deze code.
  const [kostenband, setKostenband] = useState(null);

  async function load(id) {
    const [batchData, companyData] = await Promise.all([
      api.batch(id),
      api.companies(id, ""),
    ]);
    setBatch(batchData);
    setCompanies(companyData);
    return batchData;
  }

  useEffect(() => {
    if (!batchId) return;
    setGeselecteerdId(null);
    setGeselecteerdeBron(null);
    load(batchId).catch((err) => setError(err.message));
  }, [batchId]);

  useEffect(() => {
    // Mislukt dit, dan valt de bevestiging terug op de gemeten standaardband.
    api.kostenindicatie().then(setKostenband).catch(() => {});
  }, []);

  useEffect(() => {
    if (!batchId || batch?.status !== "running") return undefined;
    const timer = window.setInterval(
      () => load(batchId).catch(() => {}), 5000,
    );
    return () => window.clearInterval(timer);
  }, [batchId, batch?.status]);

  if (map === undefined) {
    return (
      <MappenView
        api={api}
        onOpenMap={(id, naam) => setMap({id, naam})}
      />
    );
  }

  if (!batchId) {
    return (
      <BatchesView
        api={api}
        onOpenBatch={setBatchId}
        mapId={map.id}
        mapNaam={map.naam}
        onTerug={() => setMap(undefined)}
      />
    );
  }

  const geselecteerd = companies.find(
    (company) => company.company_id === geselecteerdId,
  );
  const loopt = batch?.status === "running";

  async function voerUit(actie) {
    setBusy(true);
    setError("");
    try {
      await actie();
      await load(batchId);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  /** Dezelfde bevestiging als in het lijstoverzicht, met hetzelfde aantal:
      een herstart slaat over wat al onderzocht is. */
  function startOnderzoek() {
    const teDoen = batch?.nog_te_onderzoeken ?? batch?.totaal ?? 0;
    if (!window.confirm(researchBevestiging(teDoen, kostenband, batch?.totaal))) {
      return;
    }
    voerUit(() => api.runBatch(batchId));
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-3 border-b border-line px-4 py-2">
        <button
          type="button"
          onClick={() => setBatchId(null)}
          className="focus-ring inline-flex items-center gap-1 rounded-md px-1 py-1 text-sm text-mist-65 transition hover:text-ink"
        >
          <ChevronLeft size={16} />Alle lijsten
        </button>
        <span className="text-sm font-medium text-ink">{batch?.naam}</span>
        <span className="text-xs text-mist-50">{batch?.jaar}</span>
        {/* De onderzoeksknop stond alleen in het lijstoverzicht. Wie een lijst
            openhad en wilde onderzoeken moest eerst terug, en kwam daarna weer
            binnen zonder selectie. Hier staat dezelfde actie op dezelfde lijst. */}
        <span className="ml-auto text-xs tabular-nums text-mist-50">
          {batch?.verwerkt || 0} / {batch?.totaal || 0} onderzocht
        </span>
        {loopt ? (
          <IconButton
            icon={Square}
            variant="quiet"
            disabled={busy}
            onClick={() => voerUit(() => api.cancelBatch(batchId))}
          >
            Stoppen
          </IconButton>
        ) : (
          <IconButton
            icon={Play}
            variant="quiet"
            disabled={busy}
            onClick={startOnderzoek}
          >
            Onderzoeken
          </IconButton>
        )}
      </div>

      {error ? <div className="px-4 pt-4"><Alert message={error} /></div> : null}
      {/* Ook hier: een lijst is niet af zodra hij geüpload is. Een vestiging die
          er per ongeluk niet in stond, moest tot nu toe via een nieuwe upload. */}
      {batchId ? (
        <BedrijfToevoegen
          api={api}
          batchId={batchId}
          onToegevoegd={() => load(batchId).catch(() => {})}
        />
      ) : null}

      {/* Onder lg staan de panelen gestapeld; zonder eigen scroller zou de
          onderste helft buiten beeld vallen. */}
      <div className="grid min-h-0 flex-1 grid-cols-1 overflow-y-auto lg:overflow-visible lg:grid-cols-[minmax(220px,1fr)_minmax(0,2fr)] xl:grid-cols-[minmax(240px,1fr)_minmax(0,2fr)_minmax(0,2fr)]">
        <aside className="min-h-0 border-line lg:border-r">
          <OrganisatieLijst
            companies={companies}
            geselecteerdId={geselecteerdId}
            onSelect={(id) => {
              setGeselecteerdId(id);
              setGeselecteerdeBron(null);
            }}
          />
        </aside>

        <section className="min-h-0 overflow-y-auto border-line xl:border-r">
          {geselecteerd ? (
            <KandidatenPaneel
              key={geselecteerd.company_id}
              api={api}
              company={geselecteerd}
              batchJaar={batch?.jaar}
              geselecteerdeBronId={geselecteerdeBron?.id}
              onSelecteerBron={(candidate) => bekijkBewijs(candidate, setGeselecteerdeBron)}
              onGewijzigd={() => load(batchId).catch(() => {})}
            />
          ) : (
            <div className="px-5 py-16 text-center text-sm text-mist-65">
              Kies een organisatie om de gevonden bronnen te beoordelen.
            </div>
          )}
        </section>

        {/* Precies één keer renderen: een verborgen iframe laadt gewoon door. */}
        {isXl ? (
          <section className="min-h-0 overflow-hidden bg-panel">
            <BewijsPaneel candidate={geselecteerdeBron} />
          </section>
        ) : null}
      </div>

      {!isXl && geselecteerdeBron ? (
        <section className="h-96 shrink-0 overflow-hidden border-t border-line bg-panel">
          <BewijsPaneel candidate={geselecteerdeBron} />
        </section>
      ) : null}
    </div>
  );
}
