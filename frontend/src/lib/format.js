export function pct(value) {
  if (!value) return 0;
  return Math.max(0, Math.min(100, Math.round(value * 100)));
}

export function classNames(...items) {
  return items.filter(Boolean).join(" ");
}
