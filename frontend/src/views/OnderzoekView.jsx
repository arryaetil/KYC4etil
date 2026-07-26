import {useEffect, useState} from "react";
import {ChevronLeft} from "lucide-react";
import {Alert} from "../components/Alert.jsx";
import {BatchesView} from "./BatchesView.jsx";
import {OrganisatieLijst} from "../components/onderzoek/OrganisatieLijst.jsx";

export function OnderzoekView({api}) {
  const [batchId, setBatchId] = useState(null);
  const [batch, setBatch] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [geselecteerdId, setGeselecteerdId] = useState(null);
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

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(220px,1fr)_minmax(0,2fr)] xl:grid-cols-[minmax(240px,1fr)_minmax(0,2fr)_minmax(0,2fr)]">
        <aside className="min-h-0 border-line lg:border-r">
          <OrganisatieLijst
            companies={companies}
            geselecteerdId={geselecteerdId}
            onSelect={setGeselecteerdId}
          />
        </aside>

        <section className="min-h-0 overflow-y-auto border-line xl:border-r">
          {geselecteerd ? (
            <div className="px-5 py-5 text-sm text-slate-500">
              Kandidaten voor {geselecteerd.naam} volgen in de volgende stap.
            </div>
          ) : (
            <div className="px-5 py-16 text-center text-sm text-slate-500">
              Kies een organisatie om de gevonden bronnen te beoordelen.
            </div>
          )}
        </section>

        <section className="hidden min-h-0 overflow-hidden bg-panel xl:block">
          <div className="px-5 py-16 text-center text-sm text-slate-500">
            Bewijs verschijnt hier.
          </div>
        </section>
      </div>
    </div>
  );
}
