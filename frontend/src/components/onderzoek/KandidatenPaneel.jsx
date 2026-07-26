import {useEffect, useState} from "react";
import {Plus, RefreshCw, Search} from "lucide-react";
import {Alert} from "../Alert.jsx";
import {BronKaart} from "./BronKaart.jsx";
import {Diagnostiek} from "./Diagnostiek.jsx";

export function KandidatenPaneel({
  api, company, batchJaar, geselecteerdeBronId, onSelecteerBron,
}) {
  const [items, setItems] = useState([]);
  const [diagnostiek, setDiagnostiek] = useState({});
  const [run, setRun] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [handmatigOpen, setHandmatigOpen] = useState(false);
  const [handmatigUrl, setHandmatigUrl] = useState("");

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

  async function beoordeel(candidate, beslissing) {
    setError("");
    try {
      await api.reviewResearchCandidate(candidate.id, beslissing);
      await laadKandidaten();
    } catch (err) {
      setError(err.message);
    }
  }

  async function voegHandmatigToe(event) {
    event.preventDefault();
    setError("");
    try {
      await api.addManualResearchSource(company.company_id, {url: handmatigUrl});
      setHandmatigUrl("");
      setHandmatigOpen(false);
      await laadKandidaten();
    } catch (err) {
      setError(err.message);
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
              onBekijk={onSelecteerBron}
              onAccepteer={(item) => beoordeel(item, "accepteren")}
              onWijsAf={(item) => beoordeel(item, "afwijzen")}
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
            className="focus-ring rounded-md bg-ink px-3 text-sm text-white transition hover:opacity-90"
          >
            Toevoegen
          </button>
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
