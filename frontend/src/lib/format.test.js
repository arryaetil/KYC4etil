import {describe, expect, it} from "vitest";
import {formatMoment} from "./format.js";

describe("formatMoment", () => {
  it("geeft een streepje zonder waarde", () => {
    expect(formatMoment(null)).toBe("—");
    expect(formatMoment("")).toBe("—");
  });

  it("geeft een streepje bij een onleesbare datum in plaats van Invalid Date", () => {
    expect(formatMoment("geen-datum")).toBe("—");
  });

  it("schrijft een ISO-moment in het Nederlands uit", () => {
    const tekst = formatMoment("2026-03-04T09:30:00Z");
    expect(tekst).toContain("maart");
    expect(tekst).toContain("2026");
    expect(tekst).toContain("4");
  });
});
