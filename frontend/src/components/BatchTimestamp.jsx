export function BatchTimestamp({created_at, completed_at}) {
  function fmt(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    return d.toLocaleString("nl-NL", {day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"});
  }
  return (
    <div>
      <div>{fmt(created_at) || "-"}</div>
      {completed_at ? <div className="text-xs text-slate-500">klaar {fmt(completed_at)}</div> : null}
    </div>
  );
}
