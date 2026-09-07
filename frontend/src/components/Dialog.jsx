import {useEffect, useRef} from "react";

/**
 * Kleine modale dialoog voor beslissingen die een keuze vragen.
 *
 * `window.confirm` kan maar één ding vragen: doorgaan of niet. Voor het
 * verwijderen van een gevulde map is dat te weinig — daar moet de reviewer
 * kunnen lezen wat er met de lijsten gebeurt voordat hij beslist. Vandaar een
 * eigen dialoog met ruimte voor uitleg en meer dan één uitgang.
 *
 * Toetsenbord en schermlezer: Escape sluit, de focus springt bij openen naar
 * de dialoog zelf en keert bij sluiten terug naar het element dat hem opende,
 * en Tab blijft binnen de dialoog.
 */
export function Dialog({open, titel, beschrijving, onClose, children}) {
  const paneelRef = useRef(null);
  const herstelFocusRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    herstelFocusRef.current = document.activeElement;
    paneelRef.current?.focus();

    function onKeyDown(event) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusbaar = paneelRef.current?.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusbaar?.length) return;
      const eerste = focusbaar[0];
      const laatste = focusbaar[focusbaar.length - 1];
      if (event.shiftKey && document.activeElement === eerste) {
        event.preventDefault();
        laatste.focus();
      } else if (!event.shiftKey && document.activeElement === laatste) {
        event.preventDefault();
        eerste.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      // Terug naar de knop die de dialoog opende: zonder dit staat de focus
      // na sluiten op <body> en is toetsenbordnavigatie het spoor bijster.
      if (herstelFocusRef.current instanceof HTMLElement) {
        herstelFocusRef.current.focus();
      }
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-night/50 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={paneelRef}
        role="dialog"
        aria-modal="true"
        aria-label={titel}
        tabIndex={-1}
        className="focus-ring w-full max-w-md rounded-lg border border-line bg-white p-5 shadow-lg"
      >
        <h2 className="text-base font-semibold text-ink">{titel}</h2>
        {beschrijving ? (
          <p className="mt-2 text-sm leading-relaxed text-mist-85">{beschrijving}</p>
        ) : null}
        <div className="mt-4">{children}</div>
      </div>
    </div>
  );
}
