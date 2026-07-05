import {useEffect, useState} from "react";
import {Check, ListChecks} from "lucide-react";
import {classNames} from "../lib/format.js";
import {Shell} from "../components/Shell.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {Alert} from "../components/Alert.jsx";
import {Metric} from "../components/Metric.jsx";

const CHAT_STATUS = {
  created: {label: "Verzonden", cls: "bg-blue-100 text-blue-800"},
  completed: {label: "Ingevuld", cls: "bg-amber-100 text-amber-800"},
  verwerkt: {label: "Doorvoerd", cls: "bg-emerald-100 text-emerald-800"},
};

export function ChatSessiesView({api, user, onLogout, batchId, openBatch}) {
  const [sessies, setSessies] = useState([]);
  const [doorgevoerd, setDoorgevoerd] = useState({});
  const [saving, setSaving] = useState({});
  const [error, setError] = useState("");

  async function load() {
    const data = await api.chatSessies(batchId);
    setSessies(data);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = window.setInterval(() => load().catch(() => {}), 5000);
    return () => window.clearInterval(timer);
  }, [batchId]);

  async function doorvoeren(sessionId) {
    setSaving((prev) => ({...prev, [sessionId]: true}));
    try {
      await api.doorvoerenChat(sessionId);
      setDoorgevoerd((prev) => ({...prev, [sessionId]: true}));
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving((prev) => ({...prev, [sessionId]: false}));
    }
  }

  const totaal = sessies.length;
  const ingevuld = sessies.filter((s) => s.status === "completed").length;
  const verwerkt = sessies.filter((s) => s.verwerkt).length;

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title="Chat-sessies"
      actions={<IconButton icon={ListChecks} onClick={() => openBatch(batchId)}>Batchoverzicht</IconButton>}
    >
      {error ? <Alert message={error} /> : null}
      <div className="mb-4 grid gap-3 md:grid-cols-3">
        <Metric title="Totaal verzonden" value={totaal} />
        <Metric title="Ingevuld" value={ingevuld} />
        <Metric title="Doorvoerd" value={verwerkt} />
      </div>
      {!sessies.length ? (
        <div className="rounded-lg border border-line bg-white p-8 text-center text-slate-500">
          Geen chat-sessies voor deze batch
        </div>
      ) : (
        <div className="space-y-3">
          {sessies.map((s) => {
            const statusKey = s.verwerkt ? "verwerkt" : s.status;
            const cfg = CHAT_STATUS[statusKey] || CHAT_STATUS.created;
            return (
              <div key={s.id} className="rounded-lg border border-line bg-white p-4">
                <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="font-semibold">{s.naam}</div>
                    <div className="text-sm text-slate-500">{s.gemeente}</div>
                    {s.sent_at ? (
                      <div className="mt-1 text-xs text-slate-500">
                        Verzonden {new Date(s.sent_at).toLocaleString("nl-NL", {day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"})}
                      </div>
                    ) : null}
                  </div>
                  <span className={classNames("rounded-md px-2 py-1 text-xs font-semibold", cfg.cls)}>{cfg.label}</span>
                </div>
                <div className="grid gap-4 text-sm md:grid-cols-2">
                  <div>
                    <span className="text-xs font-medium uppercase text-slate-500">Pipeline-schatting</span>
                    <div className="mt-1 text-lg font-semibold">{s.wp_kandidaat ?? "-"} WP</div>
                  </div>
                  {s.status === "completed" || s.verwerkt ? (
                    <div>
                      <span className="text-xs font-medium uppercase text-slate-500">Opgegeven door bedrijf</span>
                      <div className="mt-1 text-lg font-semibold text-etil">{s.wp_opgegeven ?? "-"} WP</div>
                    </div>
                  ) : null}
                </div>
                {s.antwoorden && Object.keys(s.antwoorden).length > 0 && (
                  <div className="mt-3 rounded-md border border-line bg-panel p-3 text-sm">
                    <div className="mb-2 text-xs font-medium uppercase text-slate-500">Antwoorden</div>
                    {Object.entries(s.antwoorden).map(([k, v]) => (
                      <div key={k} className="flex gap-3">
                        <span className="text-slate-500 min-w-24">{k}</span>
                        <span className="font-medium">{String(v || "-")}</span>
                      </div>
                    ))}
                  </div>
                )}
                {s.completed_at ? (
                  <div className="mt-3 flex items-center justify-between border-t border-line pt-3">
                    <span className="text-sm text-slate-500">
                      Ingevuld op {new Date(s.completed_at).toLocaleString("nl-NL", {day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"})}
                    </span>
                    {s.verwerkt || doorgevoerd[s.id] ? (
                      <span className="inline-flex items-center gap-1 text-sm font-medium text-emerald-700">
                        <Check size={15} /> Doorvoerd
                      </span>
                    ) : (
                      <IconButton
                        icon={Check}
                        variant="primary"
                        onClick={() => doorvoeren(s.id)}
                        disabled={saving[s.id]}
                      >
                        {saving[s.id] ? "…" : "Doorvoeren"}
                      </IconButton>
                    )}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </Shell>
  );
}
