import {useMemo, useState} from "react";
import {Search} from "lucide-react";
import {classNames} from "../../lib/format.js";
import {organisatieStatus} from "../../lib/onderzoekLabels.js";

const STATUS_PUNT = {
  neutraal: "bg-slate-300",
  aandacht: "bg-amber-500",
  fout: "bg-red-500",
  gekozen: "bg-emerald-500",
};

export function OrganisatieLijst({companies, geselecteerdId, onSelect}) {
  const [zoek, setZoek] = useState("");
  const [filter, setFilter] = useState("");

  const verrijkt = useMemo(
    () => companies.map((company) => ({...company, status: organisatieStatus(company)})),
    [companies],
  );

  const zichtbaar = useMemo(() => verrijkt.filter((company) => {
    if (filter && company.status.sleutel !== filter) return false;
    const tekst = `${company.naam || ""} ${company.gemeente || ""}`.toLowerCase();
    return tekst.includes(zoek.toLowerCase());
  }), [verrijkt, zoek, filter]);

  const teBeoordelen = verrijkt.filter(
    (company) => company.status.sleutel === "te_beoordelen",
  ).length;
  const gekozen = verrijkt.filter(
    (company) => company.status.sleutel === "gekozen",
  ).length;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="space-y-2 border-b border-line px-3 py-3">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-2.5 text-slate-400"
            size={15}
          />
          <input
            value={zoek}
            onChange={(event) => setZoek(event.target.value)}
            placeholder="Zoek organisatie"
            aria-label="Zoek organisatie"
            className="focus-ring h-9 w-full rounded-md border border-line bg-white pl-8 pr-2 text-sm"
          />
        </div>
        <select
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          aria-label="Filter op status"
          className="focus-ring h-9 w-full rounded-md border border-line bg-white px-2 text-sm text-slate-600"
        >
          <option value="">Alle statussen</option>
          <option value="te_beoordelen">Te beoordelen</option>
          <option value="gekozen">Bron gekozen</option>
          <option value="niet_gevonden">Geen bron gevonden</option>
          <option value="niet_onderzocht">Nog niet onderzocht</option>
          <option value="mislukt">Mislukt</option>
        </select>
      </div>

      <ul className="min-h-0 flex-1 overflow-y-auto">
        {zichtbaar.map((company) => (
          <li key={company.company_id}>
            <button
              type="button"
              onClick={() => onSelect(company.company_id)}
              aria-current={company.company_id === geselecteerdId ? "true" : undefined}
              className={classNames(
                "focus-ring flex w-full items-start gap-2 border-l-2 px-3 py-2.5 text-left transition",
                company.company_id === geselecteerdId
                  ? "border-l-etil bg-panel"
                  : "border-l-transparent hover:bg-panel",
              )}
            >
              <span
                aria-hidden="true"
                className={classNames(
                  "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                  STATUS_PUNT[company.status.toon],
                )}
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-ink">
                  {company.naam}
                </span>
                <span className="block truncate text-xs text-slate-500">
                  {company.gemeente} · {company.status.label}
                </span>
              </span>
            </button>
          </li>
        ))}
        {!zichtbaar.length ? (
          <li className="px-3 py-8 text-center text-xs text-slate-500">
            Geen organisaties
          </li>
        ) : null}
      </ul>

      <div className="border-t border-line px-3 py-2 text-xs tabular-nums text-slate-500">
        {teBeoordelen} te beoordelen · {gekozen} klaar
      </div>
    </div>
  );
}
