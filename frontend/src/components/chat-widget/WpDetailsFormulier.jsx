import {useState} from "react";
import {classNames} from "../../lib/format.js";
import {SomRij} from "./SomRij.jsx";

export function WpDetailsFormulier({wpTotaal, onSubmit, disabled}) {
  const [stap, setStap] = useState(0);
  const [values, setValues] = useState({});
  const dienstVelden = [
    {key: "eigen_personeel", label: "Eigen personeel"},
    {key: "uitzend", label: "Uitzendkrachten"},
    {key: "detachering", label: "Detachering"},
    {key: "wsw", label: "WSW"},
  ];
  const geslacht = [{key: "man", label: "Man"}, {key: "vrouw", label: "Vrouw"}];
  const arbeid = [{key: "voltijd", label: "Voltijd"}, {key: "deeltijd", label: "Deeltijd"}];
  const somDienst = dienstVelden.reduce((s, v) => s + (Number(values[v.key]) || 0), 0);
  const somGeslacht = geslacht.reduce((s, v) => s + (Number(values[v.key]) || 0), 0);
  const somArbeid = arbeid.reduce((s, v) => s + (Number(values[v.key]) || 0), 0);
  const pctIngevuld = values.pct_op_locatie !== undefined && values.pct_op_locatie !== "";
  function update(key, val) { setValues((p) => ({...p, [key]: val})); }
  function verstuur() {
    if (somGeslacht !== wpTotaal || somArbeid !== wpTotaal || !pctIngevuld) return;
    const parts = [
      ...dienstVelden.map((v) => `${v.label}: ${values[v.key] || 0}`),
      ...geslacht.map((v) => `${v.label}: ${values[v.key] || 0}`),
      ...arbeid.map((v) => `${v.label}: ${values[v.key] || 0}`),
      `% werkzaam op locatie: ${values.pct_op_locatie}%`,
    ];
    onSubmit(parts.join(", "));
  }
  return (
    <div className="rounded-lg border border-etil/30 bg-etil/5 p-3">
      {stap === 0 && (
        <>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-etil">Dienstverband</span>
            <span className="text-xs text-slate-500">Totaal WP: <strong>{wpTotaal}</strong></span>
          </div>
          <SomRij velden={dienstVelden} wpTotaal={wpTotaal} values={values} onUpdate={update} disabled={disabled} />
          <div className="flex justify-end">
            <button type="button" disabled={somDienst !== wpTotaal || disabled} onClick={() => setStap(1)}
              className="focus-ring rounded-md bg-etil px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-40">
              Volgende
            </button>
          </div>
        </>
      )}
      {stap === 1 && (
        <>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-etil">Geslacht & Arbeidsduur</span>
            <span className="text-xs text-slate-500">Totaal WP: <strong>{wpTotaal}</strong></span>
          </div>
          <SomRij velden={geslacht} wpTotaal={wpTotaal} values={values} onUpdate={update} disabled={disabled} />
          <SomRij velden={arbeid} wpTotaal={wpTotaal} values={values} onUpdate={update} disabled={disabled} />
          <div className="mb-3">
            <label className="mb-1 block text-xs text-slate-600">% werkzaam op locatie (≥60% van de tijd)</label>
            <input type="number" min="0" max="100" className="focus-ring h-9 w-32 rounded-md border border-line px-2 text-sm text-center"
              value={values.pct_op_locatie ?? ""} onChange={(e) => update("pct_op_locatie", e.target.value)} placeholder="%" disabled={disabled} />
          </div>
          <div className="flex justify-end">
            <button type="button" disabled={somGeslacht !== wpTotaal || somArbeid !== wpTotaal || !pctIngevuld || disabled} onClick={verstuur}
              className="focus-ring rounded-md bg-etil px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-40">
              Verstuur
            </button>
          </div>
        </>
      )}
      <div className="mt-2 flex gap-1">
        <div className="h-1 flex-1 rounded-full bg-etil" />
        <div className={classNames("h-1 flex-1 rounded-full", stap >= 1 ? "bg-etil" : "bg-slate-200")} />
      </div>
    </div>
  );
}
