import {AlertTriangle} from "lucide-react";
import {classNames} from "../../lib/format.js";
import {Panel} from "../Panel.jsx";

export function VorigJaarVergelijking({vorig_jaar, huidig_wp, collapsible}) {
  if (!vorig_jaar) return null;
  const {wp_jaar, wp_waarde, verschil_abs, verschil_pct, signaal} = vorig_jaar;
  const isHoog = signaal === "hoog";
  const isPositief = verschil_abs != null && verschil_abs > 0;
  const isNegatief = verschil_abs != null && verschil_abs < 0;
  const pctTekst = verschil_pct != null
    ? `${isPositief ? "+" : ""}${(verschil_pct * (isNegatief ? -100 : 100)).toFixed(1)}%`
    : null;

  return (
    <Panel title="Vergelijking vorig jaar" collapsible={collapsible}>
      {isHoog ? (
        <div className="mb-4 flex items-start gap-2 rounded-md border border-orange-300 bg-orange-50 p-3 text-sm text-orange-900">
          <AlertTriangle size={17} className="mt-0.5 shrink-0" />
          <div>
            <strong>Grote afwijking (&gt;25%)</strong> — controleer of dit plausibel is vóór goedkeuring.
            Label "eenduidig" sluit een grote jaarfluctuatie niet uit.
          </div>
        </div>
      ) : null}
      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="rounded-md border border-line bg-panel p-3">
          <div className="text-xs font-medium uppercase text-slate-500 mb-1">{wp_jaar}</div>
          <div className="text-2xl font-semibold">{wp_waarde}</div>
          <div className="text-xs text-slate-500 mt-0.5">vorig jaar</div>
        </div>
        <div className="rounded-md border border-line bg-panel p-3">
          <div className="text-xs font-medium uppercase text-slate-500 mb-1">Verschil</div>
          <div className={classNames(
            "text-2xl font-semibold",
            isPositief ? "text-emerald-700" : isNegatief ? "text-red-700" : "text-slate-500",
          )}>
            {verschil_abs != null ? (isPositief ? "+" : "") + verschil_abs : "—"}
          </div>
          {pctTekst ? <div className="text-xs text-slate-500 mt-0.5">{pctTekst}</div> : null}
        </div>
        <div className="rounded-md border border-line bg-panel p-3">
          <div className="text-xs font-medium uppercase text-slate-500 mb-1">Huidig</div>
          <div className="text-2xl font-semibold">{huidig_wp ?? "—"}</div>
          <div className="text-xs text-slate-500 mt-0.5">kandidaat</div>
        </div>
      </div>
    </Panel>
  );
}
