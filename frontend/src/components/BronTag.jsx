import {classNames} from "../lib/format.js";

const BRON_TAG = {
  chat:      {label: "Via chat",      cls: "bg-blue-50 text-blue-600 border-blue-200"},
  belactie:  {label: "Via belactie",  cls: "bg-amber-50 text-amber-600 border-amber-200"},
  handmatig: {label: "Handmatig",     cls: "bg-slate-50 text-slate-500 border-slate-200"},
  pipeline:  {label: "Via pipeline",  cls: "bg-violet-50 text-violet-600 border-violet-200"},
};

export function BronTag({bron}) {
  const cfg = BRON_TAG[bron] || BRON_TAG.handmatig;
  return (
    <span className={classNames("rounded border px-1.5 py-0.5 text-xs font-medium", cfg.cls)}>
      {cfg.label}
    </span>
  );
}
