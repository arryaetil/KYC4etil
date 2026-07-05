import {X} from "lucide-react";

export function Alert({message}) {
  return (
    <div className="mb-4 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      <X size={17} />
      <span>{message}</span>
    </div>
  );
}
