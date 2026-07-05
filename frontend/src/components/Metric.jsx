export function Metric({title, value}) {
  return (
    <div className="rounded-lg border border-line bg-white p-4">
      <div className="mb-2 text-xs font-medium uppercase text-slate-500">{title}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
