import {X} from "lucide-react";

export function Alert({message}) {
  return (
    <div className="mb-4 flex items-start gap-2 rounded-md border border-spectrum-red/35 bg-spectrum-red/10 p-3 text-sm text-fout">
      <X size={17} />
      <span>{message}</span>
    </div>
  );
}
