export function StatusPill({status}) {
  const label = {
    pending: "Open",
    approved: "Goedgekeurd",
    corrected: "Gecorrigeerd",
    to_chat: "Chat",
    to_call: "Bellijst",
    running: "Draait",
    review: "Review nodig",
    done: "Klaar",
    error: "Fout",
  }[status] || status || "Onbekend";
  return <span className="rounded-md border border-line bg-white px-2 py-1 text-xs font-medium text-slate-700">{label}</span>;
}
