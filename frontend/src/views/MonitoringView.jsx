import {useEffect, useRef, useState} from "react";
import {FileUp, RefreshCw} from "lucide-react";
import {Alert} from "../components/Alert.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {OrganisatieLijst} from "../components/onderzoek/OrganisatieLijst.jsx";
import {KandidatenPaneel} from "../components/onderzoek/KandidatenPaneel.jsx";
import {MonitoringVondst} from "../components/onderzoek/MonitoringVondst.jsx";
import {BedrijfToevoegen} from "../components/onderzoek/BedrijfToevoegen.jsx";
import {BewijsPaneel} from "../components/onderzoek/BewijsPaneel.jsx";
import {monitoringStatus} from "../lib/onderzoekLabels.js";
import {bekijkBewijs} from "../lib/evidenceLink.js";
import {useIsXl} from "../lib/useBreakpoint.js";

/**
 * Monitoring heeft een eigen vocabulaire: de agent vindt hooguit een
 * jaarverslag, niemand kiest hier een bron. De indeling volgt het
 * verslagjaar — hebben we het verslag over het doeljaar, alleen een ouder
 * verslag, of niets — en niet wat de laatste ronde toevallig veranderde.
 */
function monitoringOpties(doeljaar) {
  return [
    {
      waarde: "actueel",
      label: doeljaar ? `Nieuw — verslag ${doeljaar}` : "Nieuw verslag",
    },
    {waarde: "verouderd", label: "Gevonden, maar ouder"},
    {waarde: "ontbreekt", label: "Niet gevonden"},
    {waarde: "mislukt", label: "Controle mislukt"},
  ];
}

const MONITORING_TELLERS = [
  {sleutel: "actueel", label: "nieuw"},
  {sleutel: "verouderd", label: "ouder"},
  {sleutel: "ontbreekt", label: "niet gevonden"},
];

export function MonitoringView({api}) {
  const isXl = useIsXl();
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [geselecteerdId, setGeselecteerdId] = useState(null);
  const [geselecteerdeBron, setGeselecteerdeBron] = useState(null);
  const [ronde, setRonde] = useState(null);
  const [melding, setMelding] = useState("");
  const [getoondeBronUrls, setGetoondeBronUrls] = useState([]);
  const [bronnenGeladen, setBronnenGeladen] = useState(false);
  const fileRef = useRef(null);

  async function load() {
    setStatus(await api.monitoringStatus());
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = window.setInterval(() => load().catch(() => {}), 10000);
    return () => window.clearInterval(timer);
  }, []);

  /** Vult de lopende watchlist aan; de backend voegt samen op vestigingsnummer,
      KvK-nummer of naam plus gemeente, en laat bestaande rijen met rust. */
  async function uploadLijst(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    setMelding("");
    try {
      const naam = file.name.replace(/\.[^.]+$/, "");
      const uitkomst = await api.uploadBatch(
        file, naam, new Date().getFullYear(), null, {monitoringlijst: true},
      );
      setMelding(
        uitkomst.samengevoegd
          ? `${uitkomst.toegevoegd} toegevoegd, ${uitkomst.bijgewerkt} aangevuld, `
            + `${uitkomst.ongewijzigd} stonden er al.`
          : `Monitoringlijst aangemaakt met ${uitkomst.toegevoegd} organisaties.`,
      );
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  async function nuControleren() {
    setBusy(true);
    setError("");
    setRonde(null);
    try {
      // De respons zegt hoeveel organisaties deze ronde krijgt en hoeveel er
      // worden overgeslagen. Die werd weggegooid, waardoor een ronde die niets
      // te doen had niet te onderscheiden was van een ronde die draait — juist
      // nu organisaties met een actueel én beoordeelbaar verslag overslaan.
      setRonde(await api.monitorRun());
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
    // De uploadknop hoort juist hier te staan: zonder lijst was de module een
    // doodlopende mededeling, en een eerste watchlist alleen via de API aan te
    // maken.
    return (
      <div className="px-6 py-16 text-center text-sm text-mist-65">
        <p>{error || "Nog geen monitoringlijst ingesteld."}</p>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          className="hidden"
          onChange={uploadLijst}
        />
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          className="focus-ring mt-4 inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-1.5 text-sm text-ink transition hover:bg-panel disabled:opacity-50"
        >
          <FileUp size={14} />{busy ? "Bezig…" : "Lijst uploaden"}
        </button>
        {melding ? <p className="mt-2 text-xs">{melding}</p> : null}
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-4 py-2">
        <span className="text-sm font-medium text-ink">{batch.naam}</span>
        {/* De hoofdvraag van deze module in drie getallen: hoeveel hebben het
            verslag over het doeljaar, hoeveel alleen een ouder verslag, en van
            hoeveel is er niets. Nadrukkelijk in die volgorde en met "nieuw" voor
            het doeljaar — dat is het woord waarin de reviewer erover praat. */}
        <span className="flex flex-wrap items-baseline gap-x-3 text-xs tabular-nums">
          <span className="text-ink">
            <strong className="text-sm font-semibold">{status.actueel}</strong>
            {" "}nieuw{status.doeljaar ? ` — verslag ${status.doeljaar}` : ""}
          </span>
          <span className="text-aandacht">
            <strong className="text-sm font-semibold">{status.verouderd}</strong>
            {" "}gevonden, maar ouder
          </span>
          <span className="text-mist-65">
            <strong className="text-sm font-semibold">{status.ontbreekt}</strong>
            {" "}niet gevonden
          </span>
          <span className="text-mist-50">van {status.totaal}</span>
        </span>
        <span className="text-xs text-mist-50">
          {status.gecontroleerd} gecontroleerd
          {status.fouten ? ` · ${status.fouten} mislukt` : ""}
        </span>
        {ronde ? (
          <span className="text-xs text-mist-65">
            {ronde.aantal_companies === 0
              ? "Niets te doen: elk verslag over het doeljaar is al beoordeelbaar."
              : `Ronde gestart voor ${ronde.aantal_companies} organisatie${
                  ronde.aantal_companies === 1 ? "" : "s"
                }${
                  ronde.overgeslagen_actueel
                    ? `, ${ronde.overgeslagen_actueel} overgeslagen`
                    : ""
                }.`}
          </span>
        ) : null}
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          className="hidden"
          onChange={uploadLijst}
        />
        {/* Een watchlist was alleen via de API aan te maken of aan te vullen.
            Een tweede bestand vervangt de lopende lijst niet maar vult hem aan;
            dat gebeurt in de backend, hier is het gewoon "uploaden". */}
        <IconButton
          icon={FileUp}
          variant="quiet"
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          className="ml-auto"
        >
          Lijst uploaden
        </IconButton>
        <IconButton
          icon={RefreshCw}
          variant="quiet"
          onClick={nuControleren}
          disabled={busy}
        >
          {busy ? "Bezig…" : "Nu controleren"}
        </IconButton>
      </div>

      {error ? <div className="px-4 pt-4"><Alert message={error} /></div> : null}
      {melding ? (
        <p className="px-4 pt-3 text-xs text-mist-65">{melding}</p>
      ) : null}
      {batch ? (
        <BedrijfToevoegen
          api={api}
          batchId={batch.id}
          onToegevoegd={() => load().catch(() => {})}
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
              // Anders geldt bij de volgende organisatie nog even het oordeel
              // over de vorige, en verdwijnt haar vondst ten onrechte.
              setBronnenGeladen(false);
              setGetoondeBronUrls([]);
            }}
            statusVan={monitoringStatus}
            statusOpties={monitoringOpties(status.doeljaar)}
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
                onSelecteerBron={(candidate) => bekijkBewijs(candidate, setGeselecteerdeBron)}
                getoondeBronUrls={getoondeBronUrls}
                bronnenGeladen={bronnenGeladen}
              />
              <KandidatenPaneel
                key={geselecteerd.company_id}
                api={api}
                company={geselecteerd}
                batchJaar={batch.jaar}
                monitoringBron={geselecteerd.laatste_bron_url}
                onItemsGeladen={(items) => {
                  setGetoondeBronUrls(items.map((item) => item.url));
                  setBronnenGeladen(true);
                }}
                geselecteerdeBronId={geselecteerdeBron?.id}
                onSelecteerBron={(candidate) => bekijkBewijs(candidate, setGeselecteerdeBron)}
                onGewijzigd={() => load().catch(() => {})}
              />
            </>
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
