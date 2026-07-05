import {useEffect, useMemo, useRef, useState} from "react";
import {FileUp, ListChecks, MessageSquare, Search, Trash2, X} from "lucide-react";
import {Shell} from "../components/Shell.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {Alert} from "../components/Alert.jsx";

export function JaarverslagenView({api, user, onLogout, openDashboard, openChat}) {
  const fileRef = useRef(null);
  const [uploads, setUploads] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [companyZoek, setCompanyZoek] = useState("");
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [error, setError] = useState("");
  const [zoek, setZoek] = useState("");
  const [jaar, setJaar] = useState(String(new Date().getFullYear()));
  const [uploadInfo, setUploadInfo] = useState(null);

  async function load() {
    const data = await api.jaarverslagen();
    setUploads(data);
  }

  useEffect(() => { load().catch((e) => setError(e.message)); }, []);

  useEffect(() => {
    const timer = setTimeout(async () => {
      try {
        const data = await api.zoekCompanies(companyZoek);
        setCompanies(data);
      } catch {}
    }, 300);
    return () => clearTimeout(timer);
  }, [companyZoek]);

  async function upload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    setUploadInfo(null);
    try {
      const result = await api.uploadJaarverslag(file, jaar || null, selectedCompany?.id || null);
      setUploadInfo({paginas: result.paginas, naam: result.bestandsnaam});
      await load();
      openChat(result.upload_id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  async function verwijder(e, uploadId, naam) {
    e.stopPropagation();
    if (!window.confirm(`"${naam}" en alle chatberichten definitief verwijderen?`)) return;
    setDeleting(uploadId);
    try {
      await api.verwijderJaarverslag(uploadId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleting(null);
    }
  }

  const gefilterd = useMemo(() =>
    uploads.filter((u) => {
      if (!zoek) return true;
      return (u.bestandsnaam + (u.company_naam || "")).toLowerCase().includes(zoek.toLowerCase());
    }), [uploads, zoek]);

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title="Jaarverslagen"
      actions={
        <>
          <IconButton icon={ListChecks} onClick={openDashboard}>Dashboard</IconButton>
          <input ref={fileRef} type="file" accept="application/pdf,.pdf" className="hidden" onChange={upload} />
          <IconButton icon={FileUp} variant="primary" onClick={() => fileRef.current?.click()} disabled={busy}>
            {busy ? "Uploaden…" : "PDF uploaden"}
          </IconButton>
        </>
      }
    >
      {error ? <Alert message={error} /> : null}

      {/* Upload-opties */}
      <div className="mb-4 flex flex-wrap gap-3 rounded-lg border border-line bg-white p-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">Peiljaar</label>
          <input
            className="focus-ring h-10 w-24 rounded-md border border-line bg-white px-3 text-sm"
            value={jaar}
            onChange={(e) => setJaar(e.target.value)}
            placeholder="Jaar"
            inputMode="numeric"
          />
        </div>
        <div className="flex-1 min-w-48">
          <label htmlFor="koppel-bedrijf" className="mb-1 block text-xs font-medium text-slate-500">Koppel aan bedrijf (optioneel)</label>
          <div className="relative">
            <input
              id="koppel-bedrijf"
              className="focus-ring h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
              value={selectedCompany ? selectedCompany.naam : companyZoek}
              onChange={(e) => { setCompanyZoek(e.target.value); setSelectedCompany(null); }}
              placeholder="Zoek op bedrijfsnaam…"
            />
            {!selectedCompany && companies.length > 0 && companyZoek && (
              <div className="absolute z-10 mt-1 w-full rounded-md border border-line bg-white shadow-lg">
                {companies.map((c) => (
                  <button
                    key={c.id}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-panel"
                    onClick={() => { setSelectedCompany(c); setCompanyZoek(""); setCompanies([]); }}
                  >
                    <span className="font-medium">{c.naam}</span>
                    <span className="text-xs text-slate-500">{c.gemeente} · {c.batch_naam}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {selectedCompany && (
            <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
              <span className="font-medium text-etil">{selectedCompany.naam}</span>
              <button className="focus-ring text-slate-500 hover:text-red-500" onClick={() => setSelectedCompany(null)} aria-label="Koppeling met bedrijf ongedaan maken">
                <X size={12} />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Zoekbalk */}
      <div className="mb-4 relative">
        <Search className="pointer-events-none absolute left-3 top-3 text-slate-500" size={17} />
        <input
          className="focus-ring h-11 w-full rounded-md border border-line bg-white pl-9 pr-3"
          value={zoek}
          onChange={(e) => setZoek(e.target.value)}
          placeholder="Zoek op bestandsnaam of bedrijf…"
          aria-label="Zoek op bestandsnaam of bedrijf"
        />
      </div>

      <div className="overflow-hidden rounded-lg border border-line bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-panel text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Bestand</th>
              <th className="px-4 py-3">Bedrijf</th>
              <th className="px-4 py-3">Jaar</th>
              <th className="px-4 py-3">Berichten</th>
              <th className="px-4 py-3">Geüpload</th>
              <th className="w-12 px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {gefilterd.map((u) => (
              <tr key={u.upload_id} className="cursor-pointer border-t border-line hover:bg-panel" onClick={() => openChat(u.upload_id)}>
                <td className="px-4 py-3 font-semibold text-etil">{u.bestandsnaam}</td>
                <td className="px-4 py-3 text-slate-500">{u.company_naam || "—"}</td>
                <td className="px-4 py-3">{u.jaar || "—"}</td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center gap-1 rounded-md border border-line bg-white px-2 py-1 text-xs">
                    <MessageSquare size={11} />{u.aantal_berichten}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-500">{new Date(u.uploaded_at).toLocaleDateString("nl-NL")}</td>
                <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                  <button
                    className="focus-ring rounded-md p-1.5 text-slate-500 transition hover:bg-red-50 hover:text-red-600"
                    onClick={(e) => verwijder(e, u.upload_id, u.bestandsnaam)}
                    disabled={deleting === u.upload_id}
                    title="Verwijderen"
                    aria-label="Jaarverslag verwijderen"
                  >
                    <Trash2 size={15} />
                  </button>
                </td>
              </tr>
            ))}
            {!gefilterd.length ? (
              <tr><td className="px-4 py-8 text-center text-slate-500" colSpan="6">
                {uploads.length ? "Geen resultaten voor deze zoekopdracht" : "Geen jaarverslagen geüpload — kies een peiljaar en klik PDF uploaden"}
              </td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
