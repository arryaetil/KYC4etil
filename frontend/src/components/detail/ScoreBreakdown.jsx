import {classNames, pct} from "../../lib/format.js";
import {ZEKERHEID_STYLE} from "./constants.js";

const BREAKDOWN_NL = {
  fte_only: "FTE opgegeven, geen WP — niet 1:1 vergelijkbaar",
  proportionele_schatting: "Proportionele schatting — inherent onzeker",
  places_fuzzy: "Locatiecount via Google Places, niet KvK-exact",
  consensus: "Bevestigd door meerdere onafhankelijke bronnen",
};

export function ScoreBreakdown({breakdown, label}) {
  if (!breakdown) return <div className="text-sm text-slate-500">Geen score beschikbaar</div>;

  if (!breakdown.zekerheid_llm) {
    return (
      <div className="rounded-md border border-slate-200 bg-panel p-3 text-sm text-slate-700">
        <div className="mb-1 text-xs font-medium uppercase text-slate-500">Geen agent-data gevonden</div>
        {breakdown.reden || "Geen reden opgegeven"}
      </div>
    );
  }

  const zekerheid = breakdown.zekerheid_llm;
  const base = breakdown.base_score;
  const bonuses = breakdown.bonuses || {};
  const penalties = breakdown.penalties || {};
  const hasBonuses = Object.keys(bonuses).length > 0;
  const hasPenalties = Object.keys(penalties).length > 0;
  const isNietEenduidig = label === "middel" || label === "laag";

  return (
    <div className="space-y-3 text-sm">
      {isNietEenduidig && (hasPenalties || zekerheid !== "hoog") ? (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900">
          <div className="mb-1.5 font-semibold text-xs uppercase">Waarom niet eenduidig?</div>
          <ul className="space-y-1">
            {zekerheid !== "hoog" ? (
              <li className="flex items-start gap-1.5">
                <span className="mt-0.5 shrink-0 text-amber-500">▸</span>
                LLM-zekerheid is <strong>{zekerheid}</strong> — basesscore {pct(base)}%
              </li>
            ) : null}
            {Object.keys(penalties).map((key) => (
              <li key={key} className="flex items-start gap-1.5">
                <span className="mt-0.5 shrink-0 text-amber-500">▸</span>
                {BREAKDOWN_NL[key] || key.replaceAll("_", " ")}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="flex items-center justify-between">
        <span className="text-slate-500">LLM-zekerheid</span>
        <span className={classNames("rounded-md px-2 py-0.5 font-semibold capitalize", ZEKERHEID_STYLE[zekerheid] || ZEKERHEID_STYLE.laag)}>
          {zekerheid || "onbekend"}
        </span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-slate-500">Basisscore</span>
        <span className="font-medium">{pct(base)}%</span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-slate-500">Bron</span>
        <span>{breakdown.bron_type || "-"}{breakdown.n_bronnen > 1 ? ` · ${breakdown.n_bronnen} bronnen` : ""}</span>
      </div>
      {hasBonuses ? (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3">
          {Object.entries(bonuses).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-3 text-emerald-800 text-xs">
              <span>{BREAKDOWN_NL[key] || key.replaceAll("_", " ")}</span>
              <span className="shrink-0 font-semibold">+{pct(value)}%</span>
            </div>
          ))}
        </div>
      ) : null}
      {hasPenalties ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-red-900">
          {Object.entries(penalties).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-3 text-xs">
              <span>{BREAKDOWN_NL[key] || key.replaceAll("_", " ")}</span>
              <span className="shrink-0 font-semibold">-{pct(value)}%</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
