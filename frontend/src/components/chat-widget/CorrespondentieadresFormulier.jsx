import {useState} from "react";

export function CorrespondentieadresFormulier({vestigingsadres, onSubmit, disabled}) {
  const [keuze, setKeuze] = useState(null);
  const [adres, setAdres] = useState("");
  return (
    <div className="rounded-lg border border-etil/30 bg-etil/5 p-3">
      <div className="mb-2 text-xs font-semibold uppercase text-etil">Correspondentieadres</div>
      <div className="mb-2 text-sm text-slate-700">Is het correspondentieadres hetzelfde als het vestigingsadres{vestigingsadres ? ` (${vestigingsadres})` : ""}?</div>
      {keuze === null && (
        <div className="flex gap-2">
          <button type="button" disabled={disabled} onClick={() => { setKeuze("ja"); onSubmit("Ja, het correspondentieadres is hetzelfde als het vestigingsadres."); }}
            className="focus-ring flex-1 rounded-md bg-etil px-3 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-40">Ja, zelfde adres</button>
          <button type="button" disabled={disabled} onClick={() => setKeuze("nee")}
            className="focus-ring flex-1 rounded-md border border-line bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-panel disabled:opacity-40">Nee, ander adres</button>
        </div>
      )}
      {keuze === "nee" && (
        <div className="flex gap-2">
          <input type="text" className="focus-ring h-10 flex-1 rounded-md border border-line px-3 text-sm"
            value={adres} onChange={(e) => setAdres(e.target.value)} placeholder="Correspondentieadres" autoFocus disabled={disabled} />
          <button type="button" disabled={!adres.trim() || disabled} onClick={() => onSubmit(`Nee, het correspondentieadres is anders. Correspondentieadres: ${adres.trim()}`)}
            className="focus-ring rounded-md bg-etil px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-40">Verstuur</button>
        </div>
      )}
    </div>
  );
}
