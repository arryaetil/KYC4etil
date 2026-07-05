export function Progress({value, total}) {
  const width = total ? Math.round((value / total) * 100) : 0;
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-500">
        <span>{value}</span>
        <span>{total}</span>
      </div>
      <div className="h-2 rounded-full bg-slate-200">
        <div className="h-2 rounded-full bg-etil" style={{width: `${Math.max(0, Math.min(100, width))}%`}} />
      </div>
    </div>
  );
}
