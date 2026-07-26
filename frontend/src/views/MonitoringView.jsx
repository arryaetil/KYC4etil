import {useEffect, useMemo, useState} from "react";
import {RefreshCw} from "lucide-react";
import {Alert} from "../components/Alert.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {OrganisatieLijst} from "../components/onderzoek/OrganisatieLijst.jsx";
import {KandidatenPaneel} from "../components/onderzoek/KandidatenPaneel.jsx";
import {BewijsPaneel} from "../components/onderzoek/BewijsPaneel.jsx";

/**
 * De monitoringlijst levert een eigen statusvorm. Vertaal die naar dezelfde
 * vorm als de onderzoeksmodule verwacht, zodat OrganisatieLijst herbruikbaar
 * blijft en er precies één manier is om een bron te beoordelen.
 */
function alsOnderzoeksCompany(company) {
  if (company.fout) return {...company, research_status: "error"};
  if (company.nieuwe_bevinding) {
    return {
      ...company,
      research_status: "completed",
      research_resultaat_status: "review_nodig",
    };
  }
  if (!company.laatste_bron_url) {
    return {
      ...company,
      research_status: "completed",
      research_resultaat_status: "niet_gevonden",
    };
  }
  return {
    ...company,
    research_status: "completed",
    research_review_status: "geaccepteerd",
  };
}

export function MonitoringView({api}) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [geselecteerdId, setGeselecteerdId] = useState(null);
  const [geselecteerdeBron, setGeselecteerdeBron] = useState(null);

  async function load() {
    setStatus(await api.monitoringStatus());
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = window.setInterval(() => load().catch(() => {}), 10000);
    return () => window.clearInterval(timer);
  }, []);

  async function nuControleren() {
    setBusy(true);
    setError("");
    try {
      await api.monitorRun();
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const batch = status?.batch;
  const companies = useMemo(
    () => (status?.companies || []).map(alsOnderzoeksCompany),
    [status],
  );
  const geselecteerd = companies.find(
    (company) => company.company_id === geselecteerdId,
  );

  if (!batch) {
    return (
      <div className="px-6 py-16 text-center text-sm text-slate-500">
        {error
          ? error
          : "Nog geen monitoringlijst ingesteld."}
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-3 border-b border-line px-4 py-2">
        <span className="text-sm font-medium text-ink">{batch.naam}</span>
        <span className="text-xs text-slate-400">
          {status.gecontroleerd} van {status.totaal} gecontroleerd
        </span>
        <IconButton
          icon={RefreshCw}
          variant="quiet"
          onClick={nuControleren}
          disabled={busy}
          className="ml-auto"
        >
          {busy ? "Bezig…" : "Nu controleren"}
        </IconButton>
      </div>

      {error ? <div className="px-4 pt-4"><Alert message={error} /></div> : null}

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(220px,1fr)_minmax(0,2fr)] xl:grid-cols-[minmax(240px,1fr)_minmax(0,2fr)_minmax(0,2fr)]">
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
              batchJaar={batch.jaar}
              geselecteerdeBronId={geselecteerdeBron?.id}
              onSelecteerBron={setGeselecteerdeBron}
            />
          ) : (
            <div className="px-5 py-16 text-center text-sm text-slate-500">
              Kies een organisatie om de gevonden bronnen te beoordelen.
            </div>
          )}
        </section>

        <section className="hidden min-h-0 overflow-hidden bg-panel xl:block">
          <BewijsPaneel candidate={geselecteerdeBron} />
        </section>
      </div>

      {geselecteerdeBron ? (
        <section className="h-96 shrink-0 overflow-hidden border-t border-line bg-panel xl:hidden">
          <BewijsPaneel candidate={geselecteerdeBron} />
        </section>
      ) : null}
    </div>
  );
}
