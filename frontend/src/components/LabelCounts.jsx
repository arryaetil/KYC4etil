import {classNames} from "../lib/format.js";
import {LABELS} from "../lib/constants.js";

export function LabelCounts({labels = {}}) {
  return (
    <div className="flex flex-wrap gap-2">
      {["hoog", "middel", "laag"].map((label) => (
        <span key={label} className="inline-flex items-center gap-1 rounded-md border border-line bg-white px-2 py-1 text-xs">
          <span className={classNames("h-2 w-2 rounded-full", LABELS[label].dot)} />
          {labels?.[label] || 0}
        </span>
      ))}
    </div>
  );
}
