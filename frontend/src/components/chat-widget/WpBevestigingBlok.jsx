import {useState} from "react";

export function WpBevestigingBlok({preFillWp, onSubmit, disabled}) {
  const heeftSchatting = preFillWp > 0;
  const [keuze, setKeuze] = useState(heeftSchatting ? null : "invoeren");
  const [invoer, setInvoer] = useState("");
  function bevestig(totaal, label) { onSubmit(totaal, label); }
  return (
    <div className="rounded-lg border border-etil/30 bg-etil/5 p-3">
      <div className="mb-2 text-xs font-semibold uppercase text-etil">
        {heeftSchatting ? "WP-getal bevestigen" : "WP-totaal invoeren"}
      </div>
      {heeftSchatting && keuze === null && (
        <>
          <div className="mb-2 text-sm text-slate-700">
            Geschat aantal werkzame personen: <strong>{preFillWp}</strong>
          </div>
          <div className="flex gap-2">
            <button type="button" disabled={disabled}
              onClick={() => bevestig(preFillWp, `WP totaal: ${preFillWp} (bevestigd)`)}
              className="focus-ring flex-1 rounded-md bg-etil px-3 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-40">
              Ja, klopt
            </button>
            <button type="button" disabled={disabled} onClick={() => setKeuze("corrigeren")}
              className="focus-ring flex-1 rounded-md border border-line bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-panel disabled:opacity-40">
              Nee, klopt niet
            </button>
          </div>
        </>
      )}
      {(keuze === "corrigeren" || keuze === "invoeren") && (
        <>
          {keuze === "corrigeren" && (
            <div className="mb-2 text-sm text-slate-500">
              Geschat: <strong>{preFillWp}</strong> — voer het juiste aantal in
            </div>
          )}
          <div className="flex gap-2">
            <input type="number" min="1"
              className="focus-ring h-10 flex-1 rounded-md border border-line px-3 text-sm"
              value={invoer} onChange={(e) => setInvoer(e.target.value)}
              placeholder={heeftSchatting ? "Juiste aantal WP" : "Totaal aantal WP"}
              autoFocus disabled={disabled} />
            <button type="button" disabled={!invoer || disabled}
              onClick={() => {
                const totaal = Number(invoer);
                const label = keuze === "corrigeren"
                  ? `WP totaal: ${totaal} (gecorrigeerd van ${preFillWp})`
                  : `WP totaal: ${totaal}`;
                bevestig(totaal, label);
              }}
              className="focus-ring rounded-md bg-etil px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-40">
              Verzenden
            </button>
          </div>
        </>
      )}
    </div>
  );
}
