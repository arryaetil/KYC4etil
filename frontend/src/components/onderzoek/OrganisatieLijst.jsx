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

const ONDERZOEK_OPTIES = [
  {waarde: "te_beoordelen", label: "Te beoordelen"},
  {waarde: "gekozen", label: "Bron gekozen"},
  {waarde: "niet_gevonden", label: "Geen bron gevonden"},
  // Een verplichte route is technisch mislukt; "niets gevonden" is dan geen
  // uitkomst maar een onbekende. Zonder eigen filter viel dit samen met
  // "Onderzoek afgerond" en was het niet terug te vinden.
  {waarde: "onvolledig", label: "Onderzoek onvolledig"},
  {waarde: "niet_onderzocht", label: "Nog niet onderzocht"},
  {waarde: "mislukt", label: "Mislukt"},
];

const ONDERZOEK_TELLERS = [
  {sleutel: "te_beoordelen", label: "te beoordelen"},
  {sleutel: "gekozen", label: "klaar"},
];

/**
 * Werkt met elk statusvocabulaire: `statusVan` bepaalt label, toon en sleutel,
 * `statusOpties` vult het filter en `tellers` de voetregel. Zo hoeft monitoring
 * zijn eigen begrippen niet te vertalen naar die van de onderzoeksmodule.
 */
export function OrganisatieLijst({
  companies,
  geselecteerdId,
  onSelect,
  statusVan = organisatieStatus,
  statusOpties = ONDERZOEK_OPTIES,
  tellers = ONDERZOEK_TELLERS,
}) {
  const [zoek, setZoek] = useState("");
  const [filter, setFilter] = useState("");

  const verrijkt = useMemo(
    () => companies.map((company) => ({...company, status: statusVan(company)})),
    [companies, statusVan],
  );

  const zichtbaar = useMemo(() => verrijkt.filter((company) => {
    if (filter && company.status.sleutel !== filter) return false;
    const tekst = `${company.naam || ""} ${company.gemeente || ""}`.toLowerCase();
    return tekst.includes(zoek.toLowerCase());
  }), [verrijkt, zoek, filter]);

  const voetregel = tellers.map((teller) => {
    const aantal = verrijkt.filter(
      (company) => company.status.sleutel === teller.sleutel,
    ).length;
    return `${aantal} ${teller.label}`;
  }).join(" · ");

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
          {statusOpties.map((optie) => (
            <option key={optie.waarde} value={optie.waarde}>{optie.label}</option>
          ))}
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
        {voetregel}
      </div>
    </div>
  );
}
