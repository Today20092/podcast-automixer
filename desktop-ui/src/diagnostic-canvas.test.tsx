import { describe, expect, it } from "vitest";
import { chooseEnvelopeLevel } from "./diagnostic-canvas";

describe("diagnostic canvas", () => {
  it("chooses the cached envelope nearest the visible pixel width", () => {
    const levels = [Array(32).fill([0, 1]), Array(128).fill([0, 1]), Array(512).fill([0, 1])];
    expect(chooseEnvelopeLevel(levels, 100)).toHaveLength(128);
  });
});
