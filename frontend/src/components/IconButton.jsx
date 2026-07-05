import {classNames} from "../lib/format.js";

export function IconButton({children, icon: Icon, variant = "default", ...props}) {
  const styles = {
    default: "border-line bg-white text-ink hover:bg-panel",
    primary: "border-etil bg-etil text-white hover:opacity-90",
    danger: "border-red-600 bg-red-600 text-white hover:bg-red-700",
    quiet: "border-transparent bg-transparent text-slate-600 hover:bg-panel",
    ghost: "border-transparent bg-transparent text-white hover:bg-white/10",
  };
  return (
    <button
      {...props}
      aria-label={props["aria-label"] || (!children ? props.title : undefined)}
      className={classNames(
        "focus-ring inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm font-medium transition",
        styles[variant],
        props.className,
      )}
    >
      {Icon ? <Icon size={17} /> : null}
      {children}
    </button>
  );
}
