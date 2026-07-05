import {Panel} from "../Panel.jsx";
import {StatusPill} from "../StatusPill.jsx";

export function WpHistorie({wp_historie}) {
  return (
    <Panel title="WP-historie" collapsible>
      {!wp_historie?.length ? (
        <p className="text-sm text-slate-500">Nog geen goedgekeurde records.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-line text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="pb-2 pr-5">Jaar</th>
                <th className="pb-2 pr-5">WP</th>
                <th className="pb-2 pr-5">Bron</th>
                <th className="pb-2 pr-5">Status</th>
                <th className="pb-2">Goedgekeurd</th>
              </tr>
            </thead>
            <tbody>
              {wp_historie.map((r, i) => (
                <tr key={i} className="border-b border-line last:border-0">
                  <td className="py-2.5 pr-5 font-semibold">{r.wp_jaar}</td>
                  <td className="py-2.5 pr-5 font-bold text-etil">{r.wp_waarde}</td>
                  <td className="py-2.5 pr-5 text-slate-500">{r.bron_type || "—"}</td>
                  <td className="py-2.5 pr-5"><StatusPill status={r.status} /></td>
                  <td className="py-2.5 text-xs text-slate-500">
                    {r.goedgekeurd_op ? new Date(r.goedgekeurd_op).toLocaleDateString("nl-NL") : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
