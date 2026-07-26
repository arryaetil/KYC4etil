import {useState} from "react";
import {BatchesView} from "./BatchesView.jsx";

export function OnderzoekView({api}) {
  const [batchId, setBatchId] = useState(null);

  if (!batchId) return <BatchesView api={api} onOpenBatch={setBatchId} />;

  return (
    <div className="px-6 py-8 text-sm text-slate-500">
      Werkbank voor batch {batchId} wordt opgebouwd.
      <button
        type="button"
        className="focus-ring ml-2 rounded underline"
        onClick={() => setBatchId(null)}
      >
        Terug
      </button>
    </div>
  );
}
