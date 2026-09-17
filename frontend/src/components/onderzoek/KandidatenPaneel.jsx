import {useEffect, useState} from "react";
import {Plus, RefreshCw, Search} from "lucide-react";
import {Alert} from "../Alert.jsx";
import {BronKaart} from "./BronKaart.jsx";
import {Diagnostiek} from "./Diagnostiek.jsx";
import {Opmerkingen} from "./Opmerkingen.jsx";
import {classNames} from "../../lib/format.js";
import {
  TOON_STYLE, dienststoringLabel, onderzoeksadvies,
} from "../../lib/onderzoekLabels.js";

/**
 * Samenvattend oordeel boven de bronnenlijst. Eén kop, één toelichting en de
 * voorbehouden die bij het bewijs horen — geen tweede opsomming van wat de
 * bronkaarten zelf al zeggen.
 */
function Advies({advies, onWijsBronAan}) {
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
      {/* De kop en de kleur komen uit vaste regels; alleen deze alinea is
          geschreven. Dat verschil hoort zichtbaar te zijn — niet omdat het
          onbetrouwbaar is, maar omdat de reviewer moet weten waar hij een
          formulering leest en waar een vaststelling. */}
      {advies.isGegenereerd ? (
        <p className="mt-1 text-[11px] opacity-60">Samengevat door AI</p>
      ) : null}
      {/* De kop noemt getallen; deze knoppen zeggen wélke kaart erachter zit.
          Bij twee bronnen zoekt de reviewer die zelf nog wel, bij acht niet.

          Bij één bron niet: dan staat er "Eén bron met een getal: 286 WP (2025)"
          met daaronder een knop "286 WP (2025)" naar de enige kaart die er is.
          Dat is dezelfde mededeling, twee keer. */}
      {advies.bronnen?.length > 1 ? (
        <p className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
          <span className="opacity-70">Uit:</span>
          {advies.bronnen.map((bron) => (
            <button
              key={bron.id}
              type="button"
              onClick={() => onWijsBronAan(bron.id)}
              className="focus-ring rounded border border-current/30 bg-white/60 px-1.5 py-0.5 underline-offset-2 transition hover:underline"
            >
              {bron.label}
            </button>
          ))}
        </p>
      ) : null}
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

/**
 * Boven alles, in rood: een uitgevallen dienst maakt de hele uitkomst
 * onbetrouwbaar. Zonder deze melding leest "geen bronnen gevonden" als een
 * conclusie, terwijl er niet eens gezocht is.
 */
function Dienststoring({storingen}) {
  return (
    <section
      aria-label="Dienst niet beschikbaar"
      className="mb-4 rounded-md border border-spectrum-red/35 bg-spectrum-red/10 px-3 py-3 text-fout"
    >
      <p className="text-sm font-semibold">
        Dit onderzoek is onvolledig: niet alles kon worden geraadpleegd.
      </p>
      <ul className="mt-1 space-y-0.5 text-sm">
        {storingen.map((storing) => (
          <li key={storing.dienst}>{dienststoringLabel(storing)}</li>
        ))}
      </ul>
      <p className="mt-2 text-xs opacity-90">
        Zoek opnieuw zodra dit is opgelost.
      </p>
    </section>
  );
}

export function KandidatenPaneel({
  api, company, batchJaar, geselecteerdeBronId, onSelecteerBron, onGewijzigd,
  // Alleen in de monitoringmodule gevuld: de bron die de monitoring vond.
  // Zonder dat gegeven kan dit paneel niet weten of "geen bronnen" klopt.
  monitoringBron = null,
  // Meldt welke bron-URL's dit paneel toont, zodat het blok erboven zich
  // niet hoeft te herhalen. Zonder dat gegeven staat dezelfde bron twee
  // keer op één scherm.
  onItemsGeladen = null,
}) {
  const [items, setItems] = useState([]);
  const [gemarkeerdeBronId, setGemarkeerdeBronId] = useState(null);
  // Zonder dit staat er bij elke organisatie eerst "Nog geen bronnen",
  // ook als er zo drie kaarten verschijnen. Een mededeling doen voordat je
  // het antwoord hebt is erger dan even niets zeggen.
  const [geladen, setGeladen] = useState(false);
  const [diagnostiek, setDiagnostiek] = useState({});
  const [bronsamenvatting, setBronsamenvatting] = useState(null);
  const [onderzoekspaden, setOnderzoekspaden] = useState([]);
  const [run, setRun] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [bezig, setBezig] = useState(false);
  const [handmatigOpen, setHandmatigOpen] = useState(false);
  const [handmatigUrl, setHandmatigUrl] = useState("");
  // Wat het uitlezen van een aangedragen bron opleverde als het níets
  // opleverde. Geen fout — de bron staat er — maar wel iets om te melden.
  const [handmatigMelding, setHandmatigMelding] = useState("");
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
    onItemsGeladen?.(data.items || []);
    setDiagnostiek(data.diagnostiek || {});
    setBronsamenvatting(data.bronsamenvatting || null);
    setOnderzoekspaden(data.onderzoekspaden || []);
    setRunJaar(data.gevraagd_jaar ?? null);
    setGeladen(true);
  }

  useEffect(() => {
    setRun(null);
    setError("");
    setRunJaar(null);
    setGeladen(false);
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
          onItemsGeladen?.(volgende.kandidaten || []);
          setDiagnostiek(volgende.diagnostiek || {});
          setBronsamenvatting(volgende.bronsamenvatting || null);
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
      setBronsamenvatting(null);
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
    setHandmatigMelding("");
    try {
      // De backend haalt de bron meteen op en leest er een WP-getal uit, dus
      // dit duurt seconden en niet milliseconden. Vandaar "Uitlezen…" op de
      // knop: anders lijkt het scherm te hangen.
      const uitkomst = await api.addManualResearchSource(company.company_id, {
        url: handmatigUrl,
      });
      setHandmatigUrl("");
      setHandmatigOpen(false);
      // Alleen gevuld als het lezen niets opleverde. De bron staat er dan wel,
      // en dat verschil hoort de reviewer te zien.
      setHandmatigMelding(uitkomst?.melding || "");
      await laadKandidaten();
      onGewijzigd?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBezig(false);
    }
  }

  /** Spring naar de kaart achter een uitspraak in de samenvatting en markeer hem. */
  function wijsBronAan(bronId) {
    setGemarkeerdeBronId(bronId);
    // De kaart kan buiten beeld staan; `center` zet hem middenin zodat de
    // reviewer meteen ziet welke bedoeld wordt.
    document.getElementById(`bron-${bronId}`)?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }

  return (
    // Een vast handvat voor de rookproef en de scan: zonder dat moet elke
    // controle raden welke kolom de beoordeling is, en breekt ze op de eerste
    // opmaakwijziging.
    <div className="px-5 py-5" aria-label="Bronbeoordeling">
      <header className="mb-5">
        <h2 className="text-lg font-semibold text-ink">{company.naam}</h2>
        <p className="mt-0.5 text-xs text-mist-65">
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
          <ul className="mt-2 space-y-1.5 text-xs text-mist-85">
            {onderzoekspaden.map((item) => (
              <li key={item.route}>
                <div className="flex flex-wrap justify-between gap-x-4 gap-y-1">
                  <span>{item.route.replaceAll("_", " ")} · {item.reden}</span>
                  <span className="tabular-nums text-mist-65">
                    {item.status}{item.aantal_bronnen != null ? ` · ${item.aantal_bronnen} bronnen` : ""}
                  </span>
                </div>
                {/* De backend legt per route vast waarom die status eruit kwam
                    ("niet uitgevoerd binnen het querybudget", "de agent vond het
                    verslag over het doeljaar al"). Dat stond nergens in de UI,
                    dus "overgeslagen" en "mislukt" waren niet van elkaar te
                    onderscheiden in oorzaak. */}
                {item.statusreden ? (
                  <p className="text-mist-65">{item.statusreden}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {diagnostiek.dienststoringen?.length ? (
        <Dienststoring storingen={diagnostiek.dienststoringen} />
      ) : null}

      {/* Het oordeel staat boven de bronnen, niet eronder: de reviewer moet in
          één regel kunnen zien wat er gevonden is en hoe hard dat is, voordat
          hij door de kaarten scrolt. */}
      {items.length || Object.keys(diagnostiek).length ? (
        <Advies
          advies={onderzoeksadvies(items, {
            onderzoekspaden, gevraagdJaar, bronsamenvatting,
          })}
          onWijsBronAan={wijsBronAan}
        />
      ) : null}

      {items.length ? (
        <div className="divide-y divide-line border-y border-line">
          {items.map((candidate, index) => (
            <BronKaart
              key={candidate.id}
              candidate={candidate}
              // Een handmatig toegevoegde bron staat buiten de rangorde van de
              // agent; een nummer erbij zou een positie suggereren die ze niet heeft.
              rang={candidate.brontype === "handmatig" ? null : candidate.rang || index + 1}
              gevraagdJaar={gevraagdJaar}
              isGeselecteerd={candidate.id === geselecteerdeBronId}
              isAangewezen={candidate.id === gemarkeerdeBronId}
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
        <p className="py-10 text-center text-sm text-mist-65">
          De agent onderzoekt websites, documenten en recente media…
        </p>
      ) : Object.keys(diagnostiek).length ? (
        <Diagnostiek diagnostiek={diagnostiek} />
      ) : !geladen ? (
        <p className="py-10 text-center text-sm text-mist-50">Bronnen laden…</p>
      ) : (
        <p className="py-10 text-center text-sm text-mist-65">
          {/* "Nog geen bronnen" is onwaar zodra de monitoring hierboven een
              jaarverslag toont. Die twee stonden onder elkaar op hetzelfde
              scherm, en dan weet niemand meer wat er nu is. */}
          {monitoringBron
            ? "Het gevonden jaarverslag hierboven is nog niet als bronkaart beoordeeld. "
              + "Start een onderzoek om er een beoordeelbare kaart van te maken."
            : "Nog geen bronnen. Start een onderzoek of voeg zelf een bron toe."}
        </p>
      )}

      <Opmerkingen api={api} companyId={company.company_id} />

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
          className="focus-ring inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-mist-65 transition hover:text-ink"
        >
          <Plus size={14} />Bron toevoegen
        </button>
      </div>

      {handmatigOpen ? (
        <form onSubmit={voegHandmatigToe} className="mt-3">
          <div className="flex gap-2">
            <input
              type="url"
              required
              value={handmatigUrl}
              onChange={(event) => setHandmatigUrl(event.target.value)}
              placeholder="https://organisatie.nl/jaarverslag-2025.pdf"
              aria-label="Bron-URL"
              className="focus-ring h-9 flex-1 rounded-md border border-line px-2 text-sm"
            />
            <button
              type="submit"
              disabled={bezig}
              className="focus-ring rounded-md bg-ink px-3 text-sm text-white transition hover:opacity-90 disabled:opacity-50"
            >
              {bezig ? "Uitlezen…" : "Toevoegen en uitlezen"}
            </button>
          </div>
          {/* Zeggen wat er gebeurt. Deze knop legde eerder alleen de URL vast;
              nu wordt het document opgehaald en gelezen, en dat duurt even. */}
          <p className="mt-1.5 text-xs text-mist-65">
            De bron wordt opgehaald en doorzocht op een WP-getal, alleen voor
            deze vestiging. Dat duurt een paar seconden.
          </p>
        </form>
      ) : null}

      {handmatigMelding ? (
        <p className="mt-2 text-xs text-aandacht">
          {handmatigMelding}
        </p>
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
              className="focus-ring rounded-md px-3 py-2 text-sm text-mist-85"
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
              className="focus-ring rounded-md px-3 py-1.5 text-sm text-mist-65"
            >
              Annuleren
            </button>
          </div>
        </form>
      ) : null}

      {run?.status === "error" ? (
        <p className="mt-4 rounded-md border border-spectrum-red/35 bg-spectrum-red/10 p-3 text-sm text-fout">
          Het onderzoek is mislukt: {run.fout || "onbekende fout"}
        </p>
      ) : null}
    </div>
  );
}
