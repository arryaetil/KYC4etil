import {useEffect, useState} from "react";
import {Plus, RefreshCw, Search} from "lucide-react";
import {Alert} from "../Alert.jsx";
import {BronKaart} from "./BronKaart.jsx";
import {Diagnostiek} from "./Diagnostiek.jsx";

export function KandidatenPaneel({
  api, company, batchJaar, geselecteerdeBronId, onSelecteerBron, onGewijzigd,
}) {
  const [items, setItems] = useState([]);
  const [diagnostiek, setDiagnostiek] = useState({});
  const [run, setRun] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [bezig, setBezig] = useState(false);
  const [handmatigOpen, setHandmatigOpen] = useState(false);
  const [handmatigUrl, setHandmatigUrl] = useState("");
  const [afwijzen, setAfwijzen] = useState(null);
  const [afwijsreden, setAfwijsreden] = useState("");
  const [toelichting, setToelichting] = useState("");

  const gevraagdJaar = batchJaar ? batchJaar - 1 : null;

  async function laadKandidaten() {
    const data = await api.researchCandidates(company.company_id);
    setItems(data.items || []);
    setDiagnostiek(data.diagnostiek || {});
  }

  useEffect(() => {
    setRun(null);
    setError("");
    laadKandidaten().catch((err) => setError(err.message));
  }, [company.company_id]);

  useEffect(() => {
    if (!run?.id || !["pending", "running"].includes(run.status)) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const volgende = await api.researchRun(run.id);
        setRun(volgende);
        if (["completed", "error"].includes(volgende.status)) {
          setItems(volgende.kandidaten || []);
          setDiagnostiek(volgende.diagnostiek || {});
          // De organisatielijst kent nu een andere status: laat die verversen.
          onGewijzigd?.();
        }
      } catch (err) {
        setError(err.message);
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [run?.id, run?.status]);

  const loopt = run && ["pending", "running"].includes(run.status);

  async function startOnderzoek() {
    setBusy(true);
    setError("");
    try {
      const gestart = await api.startResearch(company.company_id, gevraagdJaar);
      setRun({id: gestart.run_id, status: gestart.status});
      setItems([]);
      setDiagnostiek({});
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // `bezig` voorkomt dat een dubbelklik twee beoordelingen verstuurt; dat racet
  // met de demotie-logica in de backend.
  async function beoordeel(candidate, beslissing, reasonCode = null, reden = null) {
    if (bezig) return;
    setBezig(true);
    setError("");
    try {
      await api.reviewResearchCandidate(candidate.id, beslissing, reasonCode, reden);
      await laadKandidaten();
      onGewijzigd?.();
      setAfwijzen(null);
      setAfwijsreden("");
      setToelichting("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBezig(false);
    }
  }

  async function voegHandmatigToe(event) {
    event.preventDefault();
    if (bezig) return;
    setBezig(true);
    setError("");
    try {
      await api.addManualResearchSource(company.company_id, {url: handmatigUrl});
      setHandmatigUrl("");
      setHandmatigOpen(false);
      await laadKandidaten();
      onGewijzigd?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBezig(false);
    }
  }

  return (
    <div className="px-5 py-5">
      <header className="mb-5">
        <h2 className="text-lg font-semibold text-ink">{company.naam}</h2>
        <p className="mt-0.5 text-xs text-slate-500">
          {[company.gemeente, company.vestigingsnummer, company.kvk_nummer
            ? `KvK ${company.kvk_nummer}` : null]
            .filter(Boolean).join(" · ")}
        </p>
      </header>

      {error ? <Alert message={error} /> : null}

      {items.length ? (
        <div className="divide-y divide-line border-y border-line">
          {items.map((candidate, index) => (
            <BronKaart
              key={candidate.id}
              candidate={candidate}
              rang={candidate.rang || index + 1}
              gevraagdJaar={gevraagdJaar}
              isGeselecteerd={candidate.id === geselecteerdeBronId}
              bezig={bezig}
              onBekijk={onSelecteerBron}
              onAccepteer={(item) => beoordeel(item, "accepteren")}
              onWijsAf={setAfwijzen}
            />
          ))}
        </div>
      ) : loopt ? (
        <p className="py-10 text-center text-sm text-slate-500">
          De agent onderzoekt websites, documenten en recente media…
        </p>
      ) : Object.keys(diagnostiek).length ? (
        <Diagnostiek diagnostiek={diagnostiek} />
      ) : (
        <p className="py-10 text-center text-sm text-slate-500">
          Nog geen bronnen. Start een onderzoek of voeg zelf een bron toe.
        </p>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={startOnderzoek}
          disabled={busy || loopt}
          className="focus-ring inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-sm text-ink transition hover:bg-panel disabled:opacity-50"
        >
          {loopt ? <RefreshCw size={14} /> : <Search size={14} />}
          {loopt ? "Onderzoek loopt…" : items.length ? "Opnieuw zoeken" : "Bronnen zoeken"}
        </button>
        <button
          type="button"
          onClick={() => setHandmatigOpen((open) => !open)}
          className="focus-ring inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-slate-500 transition hover:text-ink"
        >
          <Plus size={14} />Bron toevoegen
        </button>
      </div>

      {handmatigOpen ? (
        <form onSubmit={voegHandmatigToe} className="mt-3 flex gap-2">
          <input
            type="url"
            required
            value={handmatigUrl}
            onChange={(event) => setHandmatigUrl(event.target.value)}
            placeholder="https://organisatie.nl/over-ons"
            aria-label="Bron-URL"
            className="focus-ring h-9 flex-1 rounded-md border border-line px-2 text-sm"
          />
          <button
            type="submit"
            disabled={bezig}
            className="focus-ring rounded-md bg-ink px-3 text-sm text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {bezig ? "Bezig…" : "Toevoegen"}
          </button>
        </form>
      ) : null}

      {afwijzen ? (
        <form
          className="mt-4 rounded-md border border-line bg-panel p-3"
          onSubmit={(event) => {
            event.preventDefault();
            beoordeel(afwijzen, "afwijzen", afwijsreden, toelichting || null);
          }}
        >
          <label className="block text-sm font-medium text-ink" htmlFor="afwijsreden">
            Waarom wijs je deze bron af?
          </label>
          <select
            id="afwijsreden"
            required
            value={afwijsreden}
            onChange={(event) => setAfwijsreden(event.target.value)}
            className="focus-ring mt-2 h-9 w-full rounded-md border border-line bg-white px-2 text-sm"
          >
            <option value="">Kies een reden</option>
            <option value="verkeerde_organisatie">Verkeerde organisatie</option>
            <option value="verkeerde_scope">Verkeerde scope</option>
            <option value="verkeerd_jaar">Verkeerd jaar</option>
            <option value="fte_geen_wp">FTE, geen WP</option>
            <option value="onvoldoende_bewijs">Onvoldoende bewijs</option>
            <option value="bron_niet_toegankelijk">Bron niet toegankelijk</option>
            <option value="duplicaat">Duplicaat</option>
            <option value="sterkere_bron_beschikbaar">Sterkere bron beschikbaar</option>
            <option value="verouderde_bron">Verouderde bron</option>
            <option value="anders">Anders</option>
          </select>
          {afwijsreden === "anders" ? (
            <textarea
              required
              value={toelichting}
              onChange={(event) => setToelichting(event.target.value)}
              placeholder="Licht kort toe"
              className="focus-ring mt-2 min-h-20 w-full rounded-md border border-line bg-white p-2 text-sm"
            />
          ) : null}
          <div className="mt-3 flex gap-2">
            <button
              type="submit"
              disabled={bezig || !afwijsreden}
              className="focus-ring rounded-md bg-ink px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              Bron afwijzen
            </button>
            <button
              type="button"
              onClick={() => setAfwijzen(null)}
              className="focus-ring rounded-md px-3 py-1.5 text-sm text-slate-500"
            >
              Annuleren
            </button>
          </div>
        </form>
      ) : null}

      {run?.status === "error" ? (
        <p className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          Het onderzoek is mislukt: {run.fout || "onbekende fout"}
        </p>
      ) : null}
    </div>
  );
}
