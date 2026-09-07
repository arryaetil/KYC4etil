import {useEffect, useRef, useState} from "react";
import {MoreHorizontal} from "lucide-react";
import {classNames} from "../lib/format.js";

/**
 * Menuknop voor acties op een kaart.
 *
 * Vervangt het patroon waarbij acties pas bij hover verschijnen. Dat had twee
 * problemen, waarvan het tweede het ergste: op touch bestaat hover niet, en
 * `opacity-0` haalt de klikbaarheid er niet af. De verwijderknop lag daardoor
 * onzichtbaar maar wél actief over de rechterbovenhoek van de tegel, precies
 * waar iemand tikt om de map te openen.
 *
 * Deze knop staat altijd zichtbaar en het doelgebied is ondubbelzinnig.
 * Escape sluit, klikken buiten het menu sluit, en de focus keert terug naar
 * de knop zodat toetsenbordnavigatie niet op <body> achterblijft.
 */
export function ActieMenu({label, items}) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef(null);
  const knopRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

    function onPointerDown(event) {
      if (!wrapperRef.current?.contains(event.target)) setOpen(false);
    }
    function onKeyDown(event) {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      setOpen(false);
      knopRef.current?.focus();
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown, true);
    };
  }, [open]);

  return (
    <div ref={wrapperRef} className="relative">
      <button
        ref={knopRef}
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((vorige) => !vorige)}
        className="focus-ring inline-flex h-8 w-8 items-center justify-center rounded-md border border-transparent text-mist-65 transition hover:border-line hover:bg-panel hover:text-ink"
      >
        <MoreHorizontal size={17} />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 min-w-44 overflow-hidden rounded-md border border-line bg-white py-1 shadow-lg"
        >
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
              className={classNames(
                "focus-ring flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition hover:bg-panel",
                item.destructief ? "text-fout" : "text-ink",
              )}
            >
              {item.icon ? <item.icon size={15} /> : null}
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
