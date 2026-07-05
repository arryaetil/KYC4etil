import {useState} from "react";
import {ChevronDown, ChevronUp, Pencil} from "lucide-react";
import {classNames} from "../lib/format.js";

export function Panel({title, subtitle, children, onEdit, completeness, collapsible = false, defaultOpen}) {
  const [open, setOpen] = useState(defaultOpen !== undefined ? defaultOpen : !collapsible);
  return (
    <section className="rounded-lg border border-line bg-white shadow-sm">
      <div
        className={classNames("flex items-center justify-between px-5 py-3", (!collapsible || open) && "border-b border-line")}
        style={collapsible ? {cursor: "pointer"} : undefined}
        onClick={collapsible ? () => setOpen((o) => !o) : undefined}
      >
        <div>
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          {completeness && (
            <span className="text-xs tabular-nums text-slate-500">{completeness.gevuld}/{completeness.totaal}</span>
          )}
          {onEdit && open && (
            <button
              onClick={onEdit}
              className="focus-ring rounded-md p-1.5 text-slate-500 transition hover:bg-panel hover:text-ink"
              title="Bewerken"
              aria-label="Bewerken"
            >
              <Pencil size={14} />
            </button>
          )}
          {collapsible && (
            <button
              className="focus-ring rounded-md p-1.5 text-slate-500 transition hover:bg-panel hover:text-ink"
              onClick={() => setOpen((o) => !o)}
              aria-label={open ? "Inklappen" : "Uitklappen"}
              aria-expanded={open}
            >
              {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          )}
        </div>
      </div>
      {open && <div className="px-5 py-4">{children}</div>}
    </section>
  );
}
