import {useEffect, useState} from "react";
import {ChevronLeft} from "lucide-react";
import {Alert} from "../components/Alert.jsx";
import {BatchesView} from "./BatchesView.jsx";
import {OrganisatieLijst} from "../components/onderzoek/OrganisatieLijst.jsx";
import {KandidatenPaneel} from "../components/onderzoek/KandidatenPaneel.jsx";
import {BewijsPaneel} from "../components/onderzoek/BewijsPaneel.jsx";
import {bekijkBewijs} from "../lib/evidenceLink.js";
import {useIsXl} from "../lib/useBreakpoint.js";

export function OnderzoekView({api}) {
  const isXl = useIsXl();
  const [batchId, setBatchId] = useState(null);
  const [batch, setBatch] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [geselecteerdId, setGeselecteerdId] = useState(null);
  const [geselecteerdeBron, setGeselecteerdeBron] = useState(null);
  const [error, setError] = useState("");

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
    if (!batchId || batch?.status !== "running") return undefined;
    const timer = window.setInterval(
      () => load(batchId).catch(() => {}), 5000,
    );
    return () => window.clearInterval(timer);
  }, [batchId, batch?.status]);

  if (!batchId) return <BatchesView api={api} onOpenBatch={setBatchId} />;

  const geselecteerd = companies.find(
    (company) => company.company_id === geselecteerdId,
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-3 border-b border-line px-4 py-2">
        <button
          type="button"
          onClick={() => setBatchId(null)}
          className="focus-ring inline-flex items-center gap-1 rounded-md px-1 py-1 text-sm text-slate-500 transition hover:text-ink"
        >
          <ChevronLeft size={16} />Alle lijsten
        </button>
        <span className="text-sm font-medium text-ink">{batch?.naam}</span>
        <span className="text-xs text-slate-400">{batch?.jaar}</span>
      </div>

      {error ? <div className="px-4 pt-4"><Alert message={error} /></div> : null}

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
            <div className="px-5 py-16 text-center text-sm text-slate-500">
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
