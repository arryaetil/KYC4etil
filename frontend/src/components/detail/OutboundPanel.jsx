import {useState} from "react";
import {Mail, Phone, RefreshCw} from "lucide-react";
import {Panel} from "../Panel.jsx";
import {IconButton} from "../IconButton.jsx";

export function OutboundPanel({candidate, api, batchId, companyId, onRefresh}) {
  const [chatBusy, setChatBusy] = useState(false);
  const [chatResult, setChatResult] = useState(null);
  const [belBusy, setBelBusy] = useState(false);
  const [herBusy, setHerBusy] = useState(false);
  const [error, setError] = useState("");

  async function stuurChat() {
    setChatBusy(true); setError("");
    try {
      const res = await api.createChatSession(candidate.id);
      setChatResult({ok: res.email_sent, recipient: res.email_recipient, chatUrl: res.chat_url});
      await onRefresh();
    } catch (err) { setError(err.message); }
    finally { setChatBusy(false); }
  }

  async function opBellijst() {
    setBelBusy(true); setError("");
    try { await api.bellijst(candidate.id, ""); await onRefresh(); }
    catch (err) { setError(err.message); }
    finally { setBelBusy(false); }
  }

  async function herverwerk() {
    setHerBusy(true); setError("");
    try { await api.herverwerk(batchId, companyId); await onRefresh(); }
    catch (err) { setError(err.message); }
    finally { setHerBusy(false); }
  }

  return (
    <Panel title="Outbound" collapsible>
      {error && <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{error}</div>}
      <div className="space-y-3">
        {chatResult ? (
          <div className="space-y-2">
            {chatResult.ok && (
              <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                <strong>Email verstuurd</strong> naar {chatResult.recipient}
              </div>
            )}
            {(() => {
              const token = new URL(chatResult.chatUrl, window.location.origin).searchParams.get("chat") || chatResult.chatUrl;
              const publicUrl = `${window.location.origin}/?chat=${token}`;
              return (
                <div className="rounded-md border border-line bg-panel p-3">
                  <div className="mb-1 text-xs font-medium text-slate-500">Chat-link</div>
                  <p className="mb-2 break-all text-xs text-slate-500">{publicUrl}</p>
                  <div className="flex gap-2">
                    <button className="focus-ring flex-1 rounded-md bg-etil px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90"
                      onClick={() => { window.open(`/?chat=${token}`, '_blank'); }}>
                      Open chat
                    </button>
                    <button className="focus-ring rounded-md border border-line bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-panel"
                      onClick={() => navigator.clipboard.writeText(publicUrl)}>
                      Kopieer link
                    </button>
                  </div>
                </div>
              );
            })()}
          </div>
        ) : (
          <IconButton icon={Mail} className="w-full justify-center" disabled={!candidate || chatBusy} onClick={stuurChat}>
            {chatBusy ? "Bezig…" : "Chat-uitnodiging versturen"}
          </IconButton>
        )}
        <IconButton icon={Phone} className="w-full justify-center" disabled={!candidate || belBusy} onClick={opBellijst}>
          {belBusy ? "Bezig…" : "Op bellijst zetten"}
        </IconButton>
        <div className="border-t border-line pt-3">
          <IconButton icon={RefreshCw} className="w-full justify-center" disabled={herBusy} onClick={herverwerk}>
            {herBusy ? "Bezig…" : "Herverwerk"}
          </IconButton>
        </div>
      </div>
    </Panel>
  );
}
