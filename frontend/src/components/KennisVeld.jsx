import {Tooltip} from "./Tooltip.jsx";

export function KennisVeld({label, value, unit, type, tooltip}) {
  const isEmpty = value === null || value === undefined || value === "";

  function renderValue() {
    if (isEmpty) return <span className="text-slate-300">—</span>;
    if (type === "link") {
      const display = String(value).replace(/^https?:\/\//, "").replace(/\/$/, "");
      return <a href={value} target="_blank" rel="noreferrer" className="break-all font-semibold text-etil underline">{display}</a>;
    }
    if (type === "email") {
      return <a href={`mailto:${value}`} className="font-semibold text-etil underline">{value}</a>;
    }
    const text = unit
      ? `${value} ${unit}`
      : String(value === true ? "Ja" : value === false ? "Nee" : value);
    return <span className="font-semibold text-ink">{text}</span>;
  }

  const labelEl = tooltip ? (
    <Tooltip content={tooltip}>
      <span className="cursor-help border-b border-dotted border-slate-300">{label}</span>
    </Tooltip>
  ) : label;

  return (
    <div>
      <dt className="mb-0.5 text-xs font-medium uppercase tracking-wide text-slate-500">{labelEl}</dt>
      <dd className="mt-0.5">{renderValue()}</dd>
    </div>
  );
}
