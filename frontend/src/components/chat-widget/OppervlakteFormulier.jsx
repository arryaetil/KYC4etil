import {useState} from "react";

export function OppervlakteFormulier({onSubmit, disabled}) {
  const [values, setValues] = useState({});
  const [uitbreiding, setUitbreiding] = useState(null);
  const [uitbreidingTekst, setUitbreidingTekst] = useState("");
  const velden = [
    {key: "perceeloppervlakte", label: "Perceel"},
    {key: "winkeloppervlakte", label: "Winkel"},
    {key: "kantooroppervlakte", label: "Kantoor"},
    {key: "bedrijfsvloeroppervlakte", label: "Bedrijfsvloer"},
  ];
  function update(key, val) { setValues((p) => ({...p, [key]: val})); }
  const alleIngevuld = velden.every((v) => values[v.key] !== undefined && values[v.key] !== "");
  const uitbreidingKlaar = uitbreiding === "nee" || (uitbreiding === "ja" && uitbreidingTekst.trim());
  const kanVersturen = alleIngevuld && uitbreidingKlaar;
  function verstuur() {
    if (!kanVersturen) return;
    const parts = velden.map((v) => `${v.label}oppervlakte: ${values[v.key]} m²`);
    parts.push(uitbreiding === "ja" ? `Uitbreidingsruimte: ${uitbreidingTekst.trim()}` : "Uitbreidingsruimte: geen");
    onSubmit(parts.join(", "));
  }
  return (
    <div className="rounded-lg border border-etil/30 bg-etil/5 p-3">
      <div className="mb-2 text-xs font-semibold uppercase text-etil">Oppervlaktes</div>
      <div className="mb-3 grid grid-cols-2 gap-2">
        {velden.map((v) => (
          <div key={v.key}>
            <label className="mb-1 block text-xs text-slate-600">{v.label}</label>
            <div className="relative">
              <input type="number" min="0" className="focus-ring h-9 w-full rounded-md border border-line px-2 pr-8 text-sm text-center"
                value={values[v.key] ?? ""} onChange={(e) => update(v.key, e.target.value)} disabled={disabled} />
              <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-500">m²</span>
            </div>
          </div>
        ))}
      </div>
      <div className="mb-2">
        <div className="mb-1 text-xs text-slate-600">Is er uitbreidingsruimte?</div>
        {uitbreiding === null && (
          <div className="flex gap-2">
            <button type="button" disabled={disabled} onClick={() => setUitbreiding("ja")}
              className="focus-ring flex-1 rounded-md border border-line bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-panel disabled:opacity-40">Ja</button>
            <button type="button" disabled={disabled} onClick={() => setUitbreiding("nee")}
              className="focus-ring flex-1 rounded-md border border-line bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-panel disabled:opacity-40">Nee</button>
          </div>
        )}
        {uitbreiding === "ja" && (
          <input type="text" className="focus-ring h-9 w-full rounded-md border border-line px-2 text-sm"
            value={uitbreidingTekst} onChange={(e) => setUitbreidingTekst(e.target.value)}
            placeholder="Beschrijf de uitbreidingsruimte" autoFocus disabled={disabled} />
        )}
        {uitbreiding === "nee" && <span className="text-xs text-slate-500">Geen uitbreidingsruimte</span>}
      </div>
      <div className="flex justify-end">
        <button type="button" disabled={!kanVersturen || disabled} onClick={verstuur}
          className="focus-ring rounded-md bg-etil px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-40">Verstuur</button>
      </div>
    </div>
  );
}
