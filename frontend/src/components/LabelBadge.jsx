import {classNames} from "../lib/format.js";
import {LABELS} from "../lib/constants.js";

export function LabelBadge({label}) {
  const cfg = LABELS[label] || LABELS.laag;
  return (
    <span className={classNames("inline-flex items-center gap-2 rounded-md px-2 py-1 text-xs font-semibold", cfg.bg, cfg.textColor)}>
      <span className={classNames("h-2 w-2 rounded-full", cfg.dot)} />
      {cfg.text}
    </span>
  );
}
