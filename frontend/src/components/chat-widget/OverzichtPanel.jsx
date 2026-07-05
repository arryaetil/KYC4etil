import {useEffect, useRef} from "react";
import {classNames} from "../../lib/format.js";

const OVERZICHT_GROEPEN = [
  {
    titel: "Personeel",
    velden: [
      {key: "wp_totaal", label: "WP totaal"},
      {key: "eigen_personeel", label: "Eigen personeel"},
      {key: "uitzend", label: "Uitzendkrachten"},
      {key: "detachering", label: "Detachering"},
      {key: "wsw", label: "WSW"},
      {key: "man", label: "Man"},
      {key: "vrouw", label: "Vrouw"},
      {key: "voltijd", label: "Voltijd"},
      {key: "deeltijd", label: "Deeltijd"},
      {key: "pct_op_locatie", label: "% op locatie"},
    ],
  },
  {
    titel: "Vastgoed",
    velden: [
      {key: "adres", label: "Vestigingsadres"},
      {key: "correspondentieadres", label: "Correspondentieadres"},
      {key: "perceeloppervlakte", label: "Perceeloppervlakte"},
      {key: "winkeloppervlakte", label: "Winkeloppervlakte"},
      {key: "kantooroppervlakte", label: "Kantooroppervlakte"},
      {key: "bedrijfsvloeroppervlakte", label: "Bedrijfsvloeroppervlakte"},
      {key: "uitbreidingsruimte", label: "Uitbreidingsruimte"},
    ],
  },
  {
    titel: "Overig",
    velden: [
      {key: "seizoensverschil", label: "Seizoensverschil"},
      {key: "opmerking", label: "Opmerking", optioneel: true},
    ],
  },
];

export function OverzichtPanel({gegevens}) {
  const prevGegevensRef = useRef({});
  const merged = gegevens || {};
  const alleVelden = OVERZICHT_GROEPEN.flatMap((g) => g.velden);
  const verplichtVelden = alleVelden.filter((v) => !v.optioneel);
  const ingevuld = verplichtVelden.filter((v) => merged[v.key] != null).length;
  const totaal = verplichtVelden.length;
  const pctVoortgang = totaal ? Math.round((ingevuld / totaal) * 100) : 0;
  const changedKeys = new Set();
  const prev = prevGegevensRef.current;
  for (const key of Object.keys(merged)) {
    if (merged[key] != null && prev[key] !== merged[key]) changedKeys.add(key);
  }
  useEffect(() => { prevGegevensRef.current = {...merged}; }, [gegevens]);
  return (
    <div className="flex flex-col rounded-lg border border-line bg-white shadow-sm max-h-[40vh] md:max-h-[85vh]">
      <div className="sticky top-0 z-10 rounded-t-lg border-b border-line bg-white p-4">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-semibold text-slate-700">Voortgang</span>
          <span className="font-bold text-etil">{pctVoortgang}%</span>
        </div>
        <div className="h-2 rounded-full bg-slate-200">
          <div className="h-2 rounded-full bg-etil transition-all duration-500" style={{width: `${pctVoortgang}%`}} />
        </div>
        <div className="mt-1 text-xs text-slate-500">{ingevuld} van {totaal} velden</div>
      </div>
      <div className="flex flex-col gap-4 overflow-y-auto p-4">
        {OVERZICHT_GROEPEN.map((groep) => {
          const groepIngevuld = groep.velden.filter((v) => merged[v.key] != null).length;
          const groepTotaal = groep.velden.length;
          const groepKlaar = groepIngevuld === groepTotaal;
          return (
            <div key={groep.titel}>
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
                {groepKlaar
                  ? <span className="flex h-4 w-4 items-center justify-center rounded-full bg-etil text-[10px] text-white">✓</span>
                  : <span className="flex h-4 w-4 items-center justify-center rounded-full border border-slate-300 text-[10px] text-slate-500">○</span>
                }
                {groep.titel}
                <span className="ml-auto font-normal text-slate-500">{groepIngevuld}/{groepTotaal}</span>
              </div>
              <div className="space-y-0.5">
                {groep.velden.map((veld) => {
                  const waarde = merged[veld.key];
                  const heeftWaarde = waarde != null;
                  const isChanged = changedKeys.has(veld.key);
                  return (
                    <div key={veld.key} className={classNames("flex items-center gap-2 rounded px-2 py-1 text-sm", isChanged && "field-pulse")}>
                      {heeftWaarde ? <span className="text-etil text-xs">✓</span> : <span className="text-xs text-slate-300">○</span>}
                      <span className={classNames("flex-1", heeftWaarde ? "text-slate-700" : "text-slate-500")}>{veld.label}</span>
                      <span className={classNames("text-right", heeftWaarde ? "font-semibold text-slate-900" : "text-slate-300")}>
                        {heeftWaarde ? String(waarde) : "—"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
