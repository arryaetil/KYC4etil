import {X} from "lucide-react";
import {IconButton} from "../IconButton.jsx";
import {buildPdfViewerUrl} from "../../lib/pdfViewerLink.js";

export function BronModal({open, onClose, bronUrl, pagina, citaat, titel}) {
  if (!open) return null;
  const viewerUrl = buildPdfViewerUrl({bronUrl, pagina, citaat});
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex h-full max-h-[90vh] w-full max-w-4xl flex-col rounded-lg border border-line bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div className="font-semibold">{titel || "Bron"}</div>
          <IconButton icon={X} variant="quiet" onClick={onClose}>Sluiten</IconButton>
        </div>
        <iframe title={titel || "Bron"} src={viewerUrl} className="h-full w-full flex-1 rounded-b-lg" />
      </div>
    </div>
  );
}
