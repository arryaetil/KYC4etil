import {useEffect, useRef, useState} from "react";
import {BookOpen, Check, Send} from "lucide-react";
import {classNames} from "../lib/format.js";
import {Shell} from "../components/Shell.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {Alert} from "../components/Alert.jsx";
import {Panel} from "../components/Panel.jsx";

export function JaarverslagChatView({api, user, onLogout, uploadId, openJaarverslagen}) {
  const [detail, setDetail] = useState(null);
  const [vraag, setVraag] = useState("");
  const [wpWaarde, setWpWaarde] = useState("");
  const [wpJaar, setWpJaar] = useState(String(new Date().getFullYear() - 1));
  const [busy, setBusy] = useState(false);
  const [wpBusy, setWpBusy] = useState(false);
  const [wpOpgeslagen, setWpOpgeslagen] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  async function load() {
    const data = await api.jaarverslag(uploadId);
    setDetail(data);
  }

  useEffect(() => { load().catch((e) => setError(e.message)); }, [uploadId]);
  useEffect(() => { bottomRef.current?.scrollIntoView({behavior: "smooth"}); }, [detail?.berichten?.length]);

  async function stuurVraag(e) {
    e.preventDefault();
    if (!vraag.trim() || busy) return;
    setBusy(true);
    setError("");
    const q = vraag;
    setVraag("");
    try {
      await api.chatJaarverslag(uploadId, q);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function opslaanWP() {
    if (!wpWaarde) return;
    setWpBusy(true);
    setError("");
    try {
      await api.opslaanWP(uploadId, Number(wpWaarde), Number(wpJaar));
      setWpOpgeslagen(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setWpBusy(false);
    }
  }

  const u = detail?.upload;
  const berichten = detail?.berichten || [];

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title={u?.bestandsnaam || "Jaarverslag chat"}
      actions={<IconButton icon={BookOpen} onClick={openJaarverslagen}>Jaarverslagen</IconButton>}
    >
      {error ? <Alert message={error} /> : null}
      <div className="grid gap-5 lg:grid-cols-[2fr_1fr]">
        <div className="flex flex-col gap-4">
          <Panel title="Chat met jaarverslag" subtitle={u ? `${u.jaar || "—"} · ${u.bestandsnaam}` : ""}>
            <div className="min-h-64 space-y-3">
              {!berichten.length ? (
                <div className="rounded-md border border-dashed border-line p-6 text-center text-sm text-slate-500">
                  Stel een vraag over dit jaarverslag, bijv. "Hoeveel medewerkers had dit bedrijf in {u?.jaar || "dit jaar"}?"
                </div>
              ) : berichten.map((b, i) => (
                <div key={i} className={classNames("flex flex-col gap-0.5", b.rol === "user" ? "items-end" : "items-start")}>
                  <div className={classNames(
                    "max-w-prose rounded-lg px-4 py-2.5 text-sm",
                    b.rol === "user"
                      ? "bg-etil text-white"
                      : "border border-line bg-panel text-ink",
                  )}>
                    {b.inhoud}
                  </div>
                  {b.created_at && (
                    <span className="text-xs text-slate-500">
                      {new Date(b.created_at).toLocaleTimeString("nl-NL", {hour: "2-digit", minute: "2-digit"})}
                    </span>
                  )}
                </div>
              ))}
              {busy ? (
                <div className="flex justify-start">
                  <div className="rounded-lg border border-line bg-panel px-4 py-2.5 text-sm text-slate-500">Bezig…</div>
                </div>
              ) : null}
              <div ref={bottomRef} />
            </div>
          </Panel>
          <form onSubmit={stuurVraag} className="flex gap-2">
            <input
              className="focus-ring h-11 flex-1 rounded-md border border-line bg-white px-3 text-sm"
              value={vraag}
              onChange={(e) => setVraag(e.target.value)}
              placeholder="Stel een vraag over het jaarverslag…"
              disabled={busy}
            />
            <IconButton icon={Send} variant="primary" type="submit" disabled={busy || !vraag.trim()}>
              {busy ? "…" : "Sturen"}
            </IconButton>
          </form>
        </div>

        <Panel title="WP-waarde opslaan" subtitle="Sla gevonden waarde op in het register">
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-500">WP-waarde</label>
              <input
                className="focus-ring h-10 w-full rounded-md border border-line px-3 text-sm"
                type="number"
                min="0"
                value={wpWaarde}
                onChange={(e) => setWpWaarde(e.target.value)}
                placeholder="Bijv. 138"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-500">Peiljaar</label>
              <input
                className="focus-ring h-10 w-full rounded-md border border-line px-3 text-sm"
                type="number"
                value={wpJaar}
                onChange={(e) => setWpJaar(e.target.value)}
              />
            </div>
            {wpOpgeslagen ? (
              <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-800">
                <Check size={15} /> Opgeslagen in register
              </div>
            ) : (
              <IconButton
                icon={Check}
                variant="primary"
                className="w-full justify-center"
                onClick={opslaanWP}
                disabled={wpBusy || !wpWaarde}
              >
                {wpBusy ? "Opslaan…" : "Opslaan in register"}
              </IconButton>
            )}
            {u?.company_naam ? (
              <div className="mt-3 border-t border-line pt-3 text-xs text-slate-500">
                Bedrijf: <span className="font-medium text-ink">{u.company_naam}</span>
              </div>
            ) : (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                Niet gekoppeld aan een bedrijf — opslaan in register niet mogelijk
              </div>
            )}
          </div>
        </Panel>
      </div>
    </Shell>
  );
}
