import {useEffect, useState} from "react";
import {Plus, RefreshCw, Search} from "lucide-react";
import {Alert} from "../Alert.jsx";
import {BronKaart} from "./BronKaart.jsx";
import {Diagnostiek} from "./Diagnostiek.jsx";
import {classNames} from "../../lib/format.js";
import {TOON_STYLE, onderzoeksadvies} from "../../lib/onderzoekLabels.js";

/**
 * Samenvattend oordeel boven de bronnenlijst. Eén kop, één toelichting en de
 * voorbehouden die bij het bewijs horen — geen tweede opsomming van wat de
 * bronkaarten zelf al zeggen.
 */
function Advies({advies}) {
  return (
    <section
      aria-label="Samenvattend oordeel"
      className={classNames(
        "mb-4 rounded-md border px-3 py-3",
        TOON_STYLE[advies.toon] || TOON_STYLE.neutraal,
      )}
    >
      <p className="text-sm font-semibold">{advies.kop}</p>
      <p className="mt-1 max-w-[70ch] text-sm leading-relaxed opacity-90">
        {advies.toelichting}
      </p>
      {advies.letOp.length ? (
        <ul className="mt-2 space-y-0.5 text-xs">
          {advies.letOp.map((punt) => (
            <li key={punt} className="before:mr-1 before:content-['—']">
              {punt}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export function KandidatenPaneel({
  api, company, batchJaar, geselecteerdeBronId, onSelecteerBron, onGewijzigd,
}) {
  const [items, setItems] = useState([]);
  const [diagnostiek, setDiagnostiek] = useState({});
  const [onderzoekspaden, setOnderzoekspaden] = useState([]);
  const [run, setRun] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [bezig, setBezig] = useState(false);
  const [handmatigOpen, setHandmatigOpen] = useState(false);
  const [handmatigUrl, setHandmatigUrl] = useState("");
  const [beoordelen, setBeoordelen] = useState(null);
  const [bronrol, setBronrol] = useState("accepteren");
  const [wpOordeel, setWpOordeel] = useState("correct");
  const [gecorrigeerdWp, setGecorrigeerdWp] = useState("");
  const [volledigIngelezen, setVolledigIngelezen] = useState("");
  const [extractieReden, setExtractieReden] = useState("");
  const [afwijzen, setAfwijzen] = useState(null);
  const [afwijsreden, setAfwijsreden] = useState("");
  const [toelichting, setToelichting] = useState("");

  // Het jaar dat de run zelf vroeg gaat voor op de afleiding uit het batchjaar:
  // een monitoringronde en een handmatige run kunnen een ander jaar vragen, en
  // de bronkaart zet dat jaartal naast het verslagjaar van de bron.
  const [runJaar, setRunJaar] = useState(null);
  const gevraagdJaar = runJaar ?? (batchJaar ? batchJaar - 1 : null);

  async function laadKandidaten() {
    const data = await api.researchCandidates(company.company_id);
    setItems(data.items || []);
    setDiagnostiek(data.diagnostiek || {});
    setOnderzoekspaden(data.onderzoekspaden || []);
    setRunJaar(data.gevraagd_jaar ?? null);
  }

  useEffect(() => {
    setRun(null);
    setError("");
    setRunJaar(null);
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
          setOnderzoekspaden(volgende.onderzoekspaden || []);
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
      setOnderzoekspaden(gestart.onderzoekspaden || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // `bezig` voorkomt dat een dubbelklik twee beoordelingen verstuurt; dat racet
  // met de demotie-logica in de backend.
  async function beoordeel(candidate, body) {
    if (bezig) return;
    setBezig(true);
    setError("");
    try {
      await api.reviewResearchCandidate(candidate.id, body);
      await laadKandidaten();
      onGewijzigd?.();
      setAfwijzen(null);
      setBeoordelen(null);
      setAfwijsreden("");
      setToelichting("");
      setGecorrigeerdWp("");
      setVolledigIngelezen("");
      setExtractieReden("");
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

      {onderzoekspaden.length ? (
        <details className="mb-4 border-y border-line bg-panel px-3 py-2 text-sm">
          <summary className="focus-ring cursor-pointer rounded font-medium text-ink">
            Onderzoeksroutes · {onderzoekspaden.filter((item) => item.status === "afgerond").length}
            /{onderzoekspaden.length} afgerond
          </summary>
          <ul className="mt-2 space-y-1.5 text-xs text-slate-700">
            {onderzoekspaden.map((item) => (
              <li key={item.route}>
                <div className="flex flex-wrap justify-between gap-x-4 gap-y-1">
                  <span>{item.route.replaceAll("_", " ")} · {item.reden}</span>
                  <span className="tabular-nums text-slate-500">
                    {item.status}{item.aantal_bronnen != null ? ` · ${item.aantal_bronnen} bronnen` : ""}
                  </span>
                </div>
                {/* De backend legt per route vast waarom die status eruit kwam
                    ("niet uitgevoerd binnen het querybudget", "de agent vond het
                    verslag over het doeljaar al"). Dat stond nergens in de UI,
                    dus "overgeslagen" en "mislukt" waren niet van elkaar te
                    onderscheiden in oorzaak. */}
                {item.statusreden ? (
                  <p className="text-slate-500">{item.statusreden}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {/* Het oordeel staat boven de bronnen, niet eronder: de reviewer moet in
          één regel kunnen zien wat er gevonden is en hoe hard dat is, voordat
          hij door de kaarten scrolt. */}
      {items.length || Object.keys(diagnostiek).length ? (
        <Advies advies={onderzoeksadvies(items, {onderzoekspaden})} />
      ) : null}

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
              onAccepteer={(item) => {
                setBeoordelen(item);
                setBronrol("accepteren");
                setWpOordeel(item.wp_gevonden == null ? "geen_getal" : "correct");
                setGecorrigeerdWp("");
                setVolledigIngelezen("");
                setExtractieReden("");
                setToelichting("");
                setAfwijzen(null);
              }}
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

      {beoordelen ? (
        <form
          className="mt-4 border-y border-line bg-panel px-3 py-4"
          onSubmit={(event) => {
            event.preventDefault();
            beoordeel(beoordelen, {
              beslissing: bronrol,
              wp_oordeel: wpOordeel,
              gecorrigeerd_wp: ["te_laag", "te_hoog"].includes(wpOordeel)
                ? Number(gecorrigeerdWp) : null,
              bron_volledig_ingelezen: volledigIngelezen === ""
                ? null : volledigIngelezen === "ja",
              extractie_reason_code: extractieReden || null,
              reden: toelichting || null,
            });
          }}
        >
          <h3 className="text-sm font-semibold text-ink">Bron beoordelen</h3>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="text-sm text-ink">
              Rol van deze bron
              <select
                value={bronrol}
                onChange={(event) => setBronrol(event.target.value)}
                className="focus-ring mt-1 h-10 w-full rounded-md border border-line bg-white px-2"
              >
                <option value="accepteren">Primair bewijs</option>
                <option value="ondersteunen">Ondersteunende relevante bron</option>
              </select>
            </label>
            <label className="text-sm text-ink">
              Klopt het gevonden aantal?
              <select
                value={wpOordeel}
                onChange={(event) => {
                  setWpOordeel(event.target.value);
                  if (!["te_laag", "te_hoog"].includes(event.target.value)) {
                    setGecorrigeerdWp("");
                    setExtractieReden("");
                  }
                }}
                className="focus-ring mt-1 h-10 w-full rounded-md border border-line bg-white px-2"
              >
                <option value="correct">Ja, het klopt</option>
                <option value="te_laag">Nee, het is te laag</option>
                <option value="te_hoog">Nee, het is te hoog</option>
                <option value="niet_te_bepalen">Niet te bepalen</option>
                <option value="geen_getal">Geen getal gevonden</option>
              </select>
            </label>
          </div>

          {["te_laag", "te_hoog"].includes(wpOordeel) ? (
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="text-sm text-ink">
                Correct aantal werkzame personen
                <input
                  type="number"
                  min="0"
                  required
                  value={gecorrigeerdWp}
                  onChange={(event) => setGecorrigeerdWp(event.target.value)}
                  className="focus-ring mt-1 h-10 w-full rounded-md border border-line bg-white px-2"
                />
              </label>
              <label className="text-sm text-ink">
                Waarom wijkt het af?
                <select
                  required
                  value={extractieReden}
                  onChange={(event) => setExtractieReden(event.target.value)}
                  className="focus-ring mt-1 h-10 w-full rounded-md border border-line bg-white px-2"
                >
                  <option value="">Kies een reden</option>
                  <option value="personen_gemist">Personen of elementen gemist</option>
                  <option value="personen_onterecht_meegeteld">Personen onterecht meegeteld</option>
                  <option value="pagina_onvolledig_geladen">Pagina onvolledig geladen</option>
                  <option value="informatie_in_afbeelding">Informatie stond in een afbeelding</option>
                  <option value="verkeerde_scope">Verkeerde vestiging of scope</option>
                  <option value="verkeerde_eenheid">Verkeerde eenheid</option>
                  <option value="verouderde_informatie">Verouderde informatie</option>
                  <option value="interpretatiefout">Interpretatiefout</option>
                  <option value="afwijkende_definitie">Afwijkende definitie van medewerker</option>
                  <option value="anders">Anders</option>
                </select>
              </label>
              <label className="text-sm text-ink sm:col-span-2">
                Was de bron volledig ingelezen?
                <select
                  value={volledigIngelezen}
                  onChange={(event) => setVolledigIngelezen(event.target.value)}
                  className="focus-ring mt-1 h-10 w-full rounded-md border border-line bg-white px-2 sm:max-w-xs"
                >
                  <option value="">Onbekend</option>
                  <option value="ja">Ja</option>
                  <option value="nee">Nee</option>
                </select>
              </label>
            </div>
          ) : null}

          {(["te_laag", "te_hoog"].includes(wpOordeel) || extractieReden === "anders") ? (
            <textarea
              required={extractieReden === "anders"}
              value={toelichting}
              onChange={(event) => setToelichting(event.target.value)}
              placeholder="Korte toelichting, bijvoorbeeld: twee teamleden onderaan de pagina gemist"
              className="focus-ring mt-3 min-h-20 w-full rounded-md border border-line bg-white p-2 text-sm"
            />
          ) : null}
          <div className="mt-3 flex gap-2">
            <button
              type="submit"
              disabled={bezig}
              className="focus-ring rounded-md bg-etil px-3 py-2 text-sm text-white disabled:opacity-50"
            >
              Beoordeling opslaan
            </button>
            <button
              type="button"
              onClick={() => setBeoordelen(null)}
              className="focus-ring rounded-md px-3 py-2 text-sm text-slate-600"
            >
              Annuleren
            </button>
          </div>
        </form>
      ) : null}

      {afwijzen ? (
        <form
          className="mt-4 rounded-md border border-line bg-panel p-3"
          onSubmit={(event) => {
            event.preventDefault();
            beoordeel(afwijzen, {
              beslissing: "afwijzen",
              reason_code: afwijsreden,
              reden: toelichting || null,
            });
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
