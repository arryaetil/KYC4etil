import {useRef, useState} from "react";
import {Eye, FileUp, Link as LinkIcon} from "lucide-react";
import {classNames, formatMoment} from "../../lib/format.js";
import {
  bewijsRelatie, monitoringStatus, peilmomentRelatie,
} from "../../lib/onderzoekLabels.js";

/**
 * Bouwt uit de monitoringvelden een kandidaat-vormig object, zodat het
 * bewijspaneel de gevonden bron op dezelfde manier kan openen als een bronkaart.
 *
 * Paginanummer en bewijsfragment horen erbij: `bewijsUrl` leidt daar de
 * `#page=`- en `search=`-fragmenten uit af. Ontbreken ze, dan opent het
 * jaarverslag op pagina 1 in plaats van bij het WP-getal.
 */
export function alsBewijsBron(company) {
  if (!company?.laatste_bron_url) return null;
  // De volledige kandidaat als de monitoring die heeft; anders het minimum dat
  // de bewijsviewer nodig heeft.
  if (company.bron) return company.bron;
  return {
    id: `monitoring:${company.company_id}`,
    url: company.laatste_bron_url,
    titel: `Jaarverslag${company.verslagjaar ? ` ${company.verslagjaar}` : ""} ${company.naam || ""}`.trim(),
    brontype: "jaarverslag",
    bron_pagina: company.bron_pagina ?? null,
    bewijsfragment: company.bewijsfragment ?? null,
  };
}

function Vondstrij({label, waarde}) {
  return (
    <div className="flex gap-3">
      <dt className="w-20 shrink-0 text-mist-65">{label}</dt>
      <dd className="flex-1 text-ink">{waarde.label}</dd>
    </div>
  );
}

/** Twee URL's naar hetzelfde document: querystring en slash doen er niet toe. */
function zelfdeBron(a, b) {
  const kaal = (url) => (url || "")
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/^www\./, "")
    .split("?")[0]
    .replace(/\/$/, "");
  return Boolean(a) && kaal(a) === kaal(b);
}

/**
 * Zelf een jaarverslag aanleveren dat de monitoring niet heeft gevonden.
 *
 * Op de watchlist van 17-09-2026 staan 110 van de 205 organisaties op "niet
 * gevonden" — Koraal Groep bijvoorbeeld — terwijl de reviewer het verslag
 * gewoon op zijn schijf heeft staan. Er was geen manier om dat de werkbank in
 * te krijgen. Het geüploade document krijgt dezelfde lezing als een gevonden
 * verslag, dus er komt een gewone bronkaart uit.
 */
function JaarverslagUploaden({api, companyId, doeljaar, onGeupload}) {
  const bestandRef = useRef(null);
  const [bezig, setBezig] = useState(false);
  const [melding, setMelding] = useState("");
  const [fout, setFout] = useState("");
  const [linkOpen, setLinkOpen] = useState(false);
  const [link, setLink] = useState("");

  /** Eén afhandeling voor beide manieren van aanleveren. */
  async function lever(actie) {
    setBezig(true);
    setMelding("");
    setFout("");
    try {
      const uitkomst = await actie();
      setMelding(uitkomst?.melding || "Het jaarverslag is uitgelezen.");
      onGeupload?.();
      return true;
    } catch (err) {
      setFout(err.message);
      return false;
    } finally {
      setBezig(false);
    }
  }

  async function upload(event) {
    const bestand = event.target.files?.[0];
    if (!bestand) return;
    // Het jaartal uit de bestandsnaam is vaak goed, maar niet altijd; de
    // backend valt daarop terug als we niets meegeven. Het doeljaar hier
    // opdringen zou een bewering zijn die we niet kunnen waarmaken.
    await lever(() => api.uploadJaarverslag(companyId, bestand));
    event.target.value = "";
  }

  async function koppelLink(event) {
    event.preventDefault();
    if (bezig) return;
    const gelukt = await lever(() => api.koppelJaarverslagLink(companyId, link));
    if (gelukt) {
      setLink("");
      setLinkOpen(false);
    }
  }

  return (
    <div className="mt-3">
      <input
        ref={bestandRef}
        type="file"
        accept=".pdf,application/pdf"
        className="hidden"
        onChange={upload}
      />
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => bestandRef.current?.click()}
          disabled={bezig}
          className="focus-ring inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-sm text-ink transition hover:bg-panel disabled:opacity-50"
        >
          <FileUp size={14} />
          {bezig ? "Uitlezen…" : "Jaarverslag uploaden"}
        </button>
        {/* De meeste verslagen staan gewoon online; dan is downloaden en weer
            uploaden een omweg. */}
        <button
          type="button"
          onClick={() => setLinkOpen((open) => !open)}
          disabled={bezig}
          className="focus-ring inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-mist-65 transition hover:text-ink disabled:opacity-50"
        >
          <LinkIcon size={14} />Link naar verslag
        </button>
      </div>

      {linkOpen ? (
        <form onSubmit={koppelLink} className="mt-2 flex gap-2">
          <input
            type="url"
            required
            value={link}
            onChange={(event) => setLink(event.target.value)}
            placeholder="https://organisatie.nl/jaarverslag-2025.pdf"
            aria-label="Link naar het jaarverslag"
            className="focus-ring h-9 flex-1 rounded-md border border-line px-2 text-sm"
          />
          <button
            type="submit"
            disabled={bezig}
            className="focus-ring rounded-md bg-ink px-3 text-sm text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {bezig ? "Uitlezen…" : "Koppelen"}
          </button>
        </form>
      ) : null}

      <p className="mt-1.5 text-xs text-mist-65">
        Een verslag dat de monitoring niet vond
        {doeljaar ? `, bij voorkeur dat over ${doeljaar}` : ""}. Het wordt
        doorzocht op een WP-getal en komt als bronkaart op de stapel — nog te
        beoordelen, niet al gekozen.
      </p>
      {melding ? <p className="mt-1 text-xs text-mist-85">{melding}</p> : null}
      {fout ? <p className="mt-1 text-xs text-fout">{fout}</p> : null}
    </div>
  );
}

export function MonitoringVondst({
  company, geselecteerdeBronId, onSelecteerBron,
  getoondeBronUrls = [], bronnenGeladen = false,
  api, onGeupload,
}) {
  const status = monitoringStatus(company);
  const bron = alsBewijsBron(company);
  const peilmomentRij = peilmomentRelatie(company.bron, {
    gevraagdJaar: company.doeljaar,
  }) || {term: "Verslagjaar", label: "Niet bekend"};
  // Staat deze bron al als kaart in het paneel hieronder? Dan hoeft dit blok
  // hem niet nog eens te tonen. Bij Sint Jozef stond hetzelfde jaarverslag
  // drie keer op één scherm: hier, in de samenvatting en als kaart.
  // Pas oordelen als het paneel zijn bronnen heeft gemeld. Anders staat dit
  // blok er eerst volledig en klapt het daarna in — de pagina springt dan
  // onder je ogen weg. Uitklappen als er niets onder blijkt te staan is
  // rustiger dan inklappen als er wél iets staat.
  const toonVondst = bronnenGeladen && !getoondeBronUrls.some(
    (url) => zelfdeBron(company.laatste_bron_url, url),
  );

  return (
    <section className="border-b border-line px-5 py-5" aria-label="Monitoringvondst">
      <div className="flex items-baseline gap-2">
        <h3 className="text-xs uppercase tracking-wide text-mist-50">
          Wat de monitoring vond
        </h3>
        <span className="ml-auto text-xs text-mist-50">
          Gecontroleerd: {formatMoment(company.laatst_gecontroleerd_op)}
        </span>
      </div>

      {!toonVondst ? null : company.fout ? (
        <p className="mt-3 rounded-md border border-spectrum-red/35 bg-spectrum-red/10 p-3 text-sm text-fout">
          De laatste controle is mislukt: {company.fout}
        </p>
      ) : bron ? (
        <>
          <p className="mt-3 break-all text-base leading-relaxed text-ink">
            <a
              href={bron.url}
              target="_blank"
              rel="noreferrer"
              className="focus-ring rounded underline decoration-mist-25 underline-offset-4 transition hover:decoration-ink"
            >
              {bron.url}
            </a>
          </p>
          {/* Het WP-getal en het jaar stonden hier niet, terwijl de monitoring
              ze al had uitgelezen: de reviewer moest de bron openen om te zien
              of er überhaupt een cijfer in stond. Dezelfde twee regels als op
              een bronkaart, in dezelfde woorden. */}
          {company.bron ? (
            <dl className="mt-3 space-y-1.5 text-sm">
              <Vondstrij label="Bewijs" waarde={bewijsRelatie(company.bron)} />
              <Vondstrij
                label={peilmomentRij.term}
                waarde={peilmomentRij}
              />
            </dl>
          ) : null}

          <div className="mt-3 flex flex-wrap items-center gap-3">
            {!company.bron && company.verslagjaar ? (
              <span className="text-sm font-medium text-ink">
                Verslagjaar {company.verslagjaar}
              </span>
            ) : null}
            <button
              type="button"
              onClick={() => onSelecteerBron(bron)}
              aria-pressed={bron.id === geselecteerdeBronId}
              className={classNames(
                "focus-ring inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-sm transition",
                bron.id === geselecteerdeBronId
                  ? "border-etil text-ink"
                  : "border-line text-ink hover:bg-panel",
              )}
            >
              <Eye size={14} />Bewijs bekijken
            </button>
          </div>
        </>
      ) : (
        <p className="mt-3 text-sm text-mist-65">
          {company.laatst_gecontroleerd_op
            ? "Bij de laatste controle is geen jaarverslag gevonden."
            : "Deze organisatie is nog niet gecontroleerd."}
        </p>
      )}

      {/* Alleen de status. Hier stonden twee zinnen bij: dat er sinds de vorige
          ronde een recenter verslag was, en dat monitoring bronnen vindt maar
          niet kiest. Het eerste zegt iets over de vórige ronde en niet over dit
          verslag; het tweede legt de module uit aan iemand die er al in werkt.
          Allebei stonden ze onder élke kaart, elke ronde. */}
      <p className="mt-3 text-xs text-mist-50">
        Status: {status.label}.
      </p>

      {/* Onderaan, en niet bovenaan. Hierboven staat wát er gevonden is; een
          uploadknop dáárvoor leest als de eerste stap terwijl het de laatste
          is — je levert pas zelf iets aan als je hebt gezien dat het ontbreekt
          of niet klopt. Buiten `toonVondst`, want ook een verslag dat al als
          bronkaart staat kan het verkeerde zijn. */}
      {api ? (
        <JaarverslagUploaden
          api={api}
          companyId={company.company_id}
          doeljaar={company.doeljaar}
          onGeupload={onGeupload}
        />
      ) : null}
    </section>
  );
}
