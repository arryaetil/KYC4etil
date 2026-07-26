import {describe, expect, it, vi} from "vitest";
import {abonneerOpMediaQuery} from "./useBreakpoint.js";

function maakVenster({matches = false, modern = true} = {}) {
  const luisteraars = [];
  const media = modern
    ? {
      matches,
      addEventListener: (_soort, fn) => luisteraars.push(fn),
      removeEventListener: (_soort, fn) => {
        const index = luisteraars.indexOf(fn);
        if (index >= 0) luisteraars.splice(index, 1);
      },
    }
    : {
      matches,
      addListener: (fn) => luisteraars.push(fn),
      removeListener: (fn) => {
        const index = luisteraars.indexOf(fn);
        if (index >= 0) luisteraars.splice(index, 1);
      },
    };
  return {venster: {matchMedia: vi.fn(() => media)}, luisteraars};
}

describe("abonneerOpMediaQuery", () => {
  it("geeft de huidige stand terug", () => {
    const {venster} = maakVenster({matches: true});
    expect(abonneerOpMediaQuery("(min-width: 1280px)", () => {}, venster).matches)
      .toBe(true);
  });

  it("meldt wijzigingen aan de callback", () => {
    const {venster, luisteraars} = maakVenster({matches: false});
    const gezien = [];
    abonneerOpMediaQuery("(min-width: 1280px)", (v) => gezien.push(v), venster);
    luisteraars[0]({matches: true});
    expect(gezien).toEqual([true]);
  });

  it("ruimt de luisteraar op", () => {
    const {venster, luisteraars} = maakVenster();
    const abonnement = abonneerOpMediaQuery("(min-width: 1280px)", () => {}, venster);
    expect(luisteraars).toHaveLength(1);
    abonnement.stop();
    expect(luisteraars).toHaveLength(0);
  });

  it("valt terug op addListener/removeListener", () => {
    const {venster, luisteraars} = maakVenster({modern: false});
    const abonnement = abonneerOpMediaQuery("(min-width: 1280px)", () => {}, venster);
    expect(luisteraars).toHaveLength(1);
    abonnement.stop();
    expect(luisteraars).toHaveLength(0);
  });

  it("blijft stil zonder matchMedia", () => {
    const abonnement = abonneerOpMediaQuery("(min-width: 1280px)", () => {}, {});
    expect(abonnement.matches).toBe(false);
    expect(() => abonnement.stop()).not.toThrow();
  });
});
