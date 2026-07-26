import {useEffect, useState} from "react";
import {RefreshCw} from "lucide-react";
import {Alert} from "../components/Alert.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {OrganisatieLijst} from "../components/onderzoek/OrganisatieLijst.jsx";
import {KandidatenPaneel} from "../components/onderzoek/KandidatenPaneel.jsx";
import {MonitoringVondst} from "../components/onderzoek/MonitoringVondst.jsx";
import {BewijsPaneel} from "../components/onderzoek/BewijsPaneel.jsx";
import {monitoringStatus} from "../lib/onderzoekLabels.js";
import {useIsXl} from "../lib/useBreakpoint.js";

/**
 * Monitoring heeft een eigen vocabulaire: de agent vindt hooguit een
 * jaarverslag, niemand kiest hier een bron.
 */
const MONITORING_OPTIES = [
  {waarde: "nieuwe_vondst", label: "Nieuwe vondst"},
  {waarde: "gevonden", label: "Jaarverslag gevonden"},
  {waarde: "niet_gevonden", label: "Geen jaarverslag gevonden"},
  {waarde: "mislukt", label: "Controle mislukt"},
];

const MONITORING_TELLERS = [
  {sleutel: "nieuwe_vondst", label: "nieuwe vondst"},
  {sleutel: "gevonden", label: "met jaarverslag"},
];

export function MonitoringView({api}) {
  const isXl = useIsXl();
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
  const companies = status?.companies || [];
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
            statusVan={monitoringStatus}
            statusOpties={MONITORING_OPTIES}
            tellers={MONITORING_TELLERS}
          />
        </aside>

        <section className="min-h-0 overflow-y-auto border-line xl:border-r">
          {geselecteerd ? (
            <>
              {/* Eerst wat de monitoring zelf vond; die vondst leeft niet in de
                  onderzoekstabellen en zou anders onzichtbaar blijven. */}
              <MonitoringVondst
                key={`vondst-${geselecteerd.company_id}`}
                company={geselecteerd}
                geselecteerdeBronId={geselecteerdeBron?.id}
                onSelecteerBron={setGeselecteerdeBron}
              />
              <KandidatenPaneel
                key={geselecteerd.company_id}
                api={api}
                company={geselecteerd}
                batchJaar={batch.jaar}
                geselecteerdeBronId={geselecteerdeBron?.id}
                onSelecteerBron={setGeselecteerdeBron}
                onGewijzigd={() => load().catch(() => {})}
              />
            </>
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
