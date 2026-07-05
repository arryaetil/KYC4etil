import {useEffect, useRef, useState} from "react";
import {Check, X} from "lucide-react";
import {classNames} from "../lib/format.js";
import {OverzichtPanel} from "../components/chat-widget/OverzichtPanel.jsx";
import {WpBevestigingBlok} from "../components/chat-widget/WpBevestigingBlok.jsx";
import {WpDetailsFormulier} from "../components/chat-widget/WpDetailsFormulier.jsx";
import {CorrespondentieadresFormulier} from "../components/chat-widget/CorrespondentieadresFormulier.jsx";
import {OppervlakteFormulier} from "../components/chat-widget/OppervlakteFormulier.jsx";

export function ChatForm({token}) {
  const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [gegevens, setGegevens] = useState({});
  const [widgetDone, setWidgetDone] = useState({wpBevestiging: false, wpDetails: false, correspondentie: false, oppervlakte: false});
  const [wpBevestigd, setWpBevestigd] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({behavior: "smooth"}); }, [messages, busy]);

  async function callMessage(msgs) {
    setBusy(true);
    try {
      const r = await fetch(`${API_URL}/chat/${token}/message`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({messages: msgs}),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Fout bij versturen");
      const updated = [...msgs, {role: "assistant", content: data.reply}];
      setMessages(updated);
      if (data.gegevens) setGegevens((prev) => ({...prev, ...data.gegevens}));
      if (data.done) setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    fetch(`${API_URL}/chat/${token}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.status === "completed") { setDone(true); return; }
        setSession(data);
        const initMsgs = data.messages || [];
        setMessages(initMsgs);
        if (initMsgs.length === 0) callMessage([]);
      })
      .catch(() => setError("Chat-sessie niet gevonden of verlopen."));
  }, [token]);

  async function sendText(text) {
    if (!text.trim() || busy) return;
    const newMsgs = [...messages, {role: "user", content: text.trim()}];
    setMessages(newMsgs);
    setInput("");
    await callMessage(newMsgs);
  }

  async function sendWidget(text, widgetKey) {
    setWidgetDone((prev) => ({...prev, [widgetKey]: true}));
    const newMsgs = [...messages, {role: "user", content: text}];
    setMessages(newMsgs);
    await callMessage(newMsgs);
  }

  // Widgets: primair op gegevens-voortgang, keyword als fallback
  // Nooit tonen voordat de gebruiker iets heeft getypt (userMsgCount >= 1)
  function currentWidget() {
    if (!session || done || busy) return null;
    const userMsgCount = messages.filter((m) => m.role === "user").length;
    if (userMsgCount < 1) return null;
    const lastAI = [...messages].reverse().find((m) => m.role === "assistant")?.content?.toLowerCase() || "";
    const aiMentions = (kws) => kws.some((k) => lastAI.includes(k));

    // Stap 1: WP bevestigen of invoeren (eigen standalone blok)
    if (!widgetDone.wpBevestiging && wpBevestigd == null && gegevens.wp_totaal == null && gegevens.eigen_personeel == null) {
      if (session?.pre_fill_wp != null || aiMentions(["uitsplitsing", "dienstverband", "invulformulier", "werkzame personen"]))
        return "wpBevestiging";
    }
    // Stap 2: Dienstverband + geslacht/arbeidsduur gecombineerd (2 stappen)
    if (!widgetDone.wpDetails && gegevens.man == null) {
      if (wpBevestigd != null || gegevens.wp_totaal != null || widgetDone.wpBevestiging)
        return "wpDetails";
    }
    // Correspondentie: AI vraagt ernaar
    if (!widgetDone.correspondentie && gegevens.correspondentieadres == null
        && aiMentions(["correspondentieadres", "hetzelfde als het vestigingsadres"]))
      return "correspondentie";
    // Oppervlakte: AI vraagt ernaar
    if (!widgetDone.oppervlakte && gegevens.perceeloppervlakte == null
        && aiMentions(["oppervlakte", "perceeloppervlakte", "m²", "vloeroppervlakte"]))
      return "oppervlakte";
    return null;
  }

  if (error && !session) return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5] px-4">
      <div className="w-full max-w-md rounded-lg border border-red-200 bg-white p-8 text-center shadow-sm">
        <X className="mx-auto mb-3 text-red-500" size={32} />
        <p className="font-medium text-red-800">{error}</p>
      </div>
    </main>
  );

  if (done) return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5] px-4">
      <div className="w-full max-w-md rounded-lg border border-line bg-white p-8 text-center shadow-sm">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100">
          <Check className="text-emerald-600" size={28} />
        </div>
        <h2 className="mb-2 text-xl font-semibold">Bedankt!</h2>
        <p className="text-slate-600">Uw gegevens zijn ontvangen. U kunt dit venster sluiten.</p>
      </div>
    </main>
  );

  if (!session && !error) return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5]">
      <div className="text-slate-500">Laden…</div>
    </main>
  );

  const widget = currentWidget();

  return (
    <main className="flex h-screen flex-col overflow-hidden bg-[#eef2f5]">
      {/* Header */}
      <div className="bg-white border-b border-line px-4 py-3 shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center gap-4">
          <img src="/logo-limburg.png" alt="Provincie Limburg" className="h-10 w-auto" />
          <div>
            <div className="text-sm font-semibold text-ink">Vestigingsregister — {session?.bedrijfsnaam || ""}</div>
            <div className="text-xs text-slate-500">Provincie Limburg · Etil Research Group</div>
          </div>
        </div>
      </div>

      {/* Body: chat + overview panel */}
      <div className="mx-auto flex w-full max-w-5xl flex-1 gap-4 overflow-hidden p-4">
        {/* Chat column */}
        <div className="flex min-h-0 flex-1 flex-col gap-3">
          {/* Messages — scrollt intern */}
          <div className="flex flex-1 flex-col gap-3 overflow-y-auto">
            {messages.map((msg, i) => (
              <div key={i} className={classNames("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
                <div className={classNames(
                  "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap",
                  msg.role === "user"
                    ? "rounded-br-sm bg-etil text-white"
                    : "rounded-bl-sm border border-line bg-white text-slate-800 shadow-sm"
                )}>
                  {msg.content}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-sm border border-line bg-white px-4 py-2.5 shadow-sm">
                  <span className="flex gap-1">
                    <span className="animate-bounce text-slate-400" style={{animationDelay: "0ms"}}>●</span>
                    <span className="animate-bounce text-slate-400" style={{animationDelay: "150ms"}}>●</span>
                    <span className="animate-bounce text-slate-400" style={{animationDelay: "300ms"}}>●</span>
                  </span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Contextual form widget */}
          {!busy && widget === "wpBevestiging" && (
            <WpBevestigingBlok
              preFillWp={session?.pre_fill_wp || 0}
              onSubmit={(wpTotal, tekst) => {
                setWpBevestigd(wpTotal);
                sendWidget(tekst, "wpBevestiging");
              }}
              disabled={busy}
            />
          )}
          {!busy && widget === "wpDetails" && (
            <WpDetailsFormulier
              wpTotaal={wpBevestigd || gegevens.wp_totaal || 0}
              onSubmit={(txt) => sendWidget(txt, "wpDetails")}
              disabled={busy}
            />
          )}
          {!busy && widget === "correspondentie" && (
            <CorrespondentieadresFormulier
              vestigingsadres={session?.adres || ""}
              onSubmit={(txt) => sendWidget(txt, "correspondentie")}
              disabled={busy}
            />
          )}
          {!busy && widget === "oppervlakte" && (
            <OppervlakteFormulier
              onSubmit={(txt) => sendWidget(txt, "oppervlakte")}
              disabled={busy}
            />
          )}

          {/* Text input — verborgen als een widget actief is */}
          {error && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</div>}
          {!widget && (
            <div className="flex gap-2">
              <input
                className="focus-ring flex-1 rounded-xl border border-line bg-white px-4 py-2.5 text-sm shadow-sm"
                placeholder={busy ? "Bezig…" : "Typ uw antwoord…"}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendText(input); }}}
                disabled={busy || done}
              />
              <button
                onClick={() => sendText(input)}
                disabled={!input.trim() || busy || done}
                className="focus-ring rounded-xl bg-etil px-4 py-2.5 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-40"
              >
                Stuur
              </button>
            </div>
          )}
          <p className="text-center text-xs text-slate-500">
            Uw gegevens worden uitsluitend gebruikt voor het Vestigingsregister van Provincie Limburg.
          </p>
        </div>

        {/* Overview panel (desktop only) — plakt aan de rechterkant */}
        <div className="hidden w-64 overflow-y-auto lg:block">
          <OverzichtPanel gegevens={gegevens} />
        </div>
      </div>
    </main>
  );
}
