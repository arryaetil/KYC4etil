import {classNames} from "../../lib/format.js";

export function SomRij({velden, wpTotaal, values, onUpdate, disabled}) {
  const som = velden.reduce((s, v) => s + (Number(values[v.key]) || 0), 0);
  const resterend = wpTotaal - som;
  return (
    <div className="mb-3">
      <div className="mb-1 grid gap-2" style={{gridTemplateColumns: `repeat(${velden.length}, 1fr)`}}>
        {velden.map((v) => (
          <div key={v.key}>
            <label className="mb-1 block text-xs text-slate-600">{v.label}</label>
            <input type="number" min="0" max={wpTotaal}
              className="focus-ring h-9 w-full rounded-md border border-line px-2 text-sm text-center"
              value={values[v.key] ?? ""} onChange={(e) => onUpdate(v.key, e.target.value)} disabled={disabled} />
          </div>
        ))}
      </div>
      <span className={classNames("text-xs font-medium", resterend === 0 ? "text-emerald-600" : resterend < 0 ? "text-red-600" : "text-amber-600")}>
        {resterend === 0 ? "✓ Som klopt" : resterend > 0 ? `Nog ${resterend} te verdelen` : `${Math.abs(resterend)} te veel`}
      </span>
    </div>
  );
}
