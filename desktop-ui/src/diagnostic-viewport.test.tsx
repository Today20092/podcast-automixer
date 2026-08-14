// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useDiagnosticViewport } from "./diagnostic-viewport";

beforeEach(() => {
  Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, value: 600 });
  HTMLElement.prototype.getBoundingClientRect = () => ({ left: 0, width: 600 } as DOMRect);
  HTMLElement.prototype.scrollTo = function (first?: ScrollToOptions | number) {
    this.scrollLeft = typeof first === "number" ? first : Number(first?.left || 0);
  };
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => (callback(0), 1));
  vi.stubGlobal("ResizeObserver", class { constructor(private callback: ResizeObserverCallback) {} observe() { this.callback([], this as unknown as ResizeObserver); } disconnect() {} });
});

describe("Diagnostic Timeline viewport", () => {
  it("fits, zooms around the pointer, scrolls, and seeks through one transform", () => {
    const seek = vi.fn();
    const { result } = renderHook(() => useDiagnosticViewport(60, 15, seek));
    const element = document.createElement("div");
    act(() => { result.current.viewportRef.current = element; result.current.fit(); });
    expect(result.current.pixelsPerSecond).toBe(10);
    expect(result.current.timeToPixel(15)).toBe(150);

    act(() => result.current.zoomAt(2, 300));
    expect(result.current.pixelsPerSecond).toBe(20);
    expect(element.scrollLeft).toBe(300);
    expect(result.current.timeToPixel(15)).toBe(300);

    act(() => result.current.seekAt(100));
    expect(seek).toHaveBeenLastCalledWith(20);
    act(() => result.current.onScroll());
    expect(result.current.scrollLeft).toBe(300);

    act(() => result.current.fit());
    expect(result.current.pixelsPerSecond).toBe(10);
    expect(element.scrollLeft).toBe(0);
  });

  it("caps zoom at approximately 100 pixels per second", () => {
    const { result } = renderHook(() => useDiagnosticViewport(60, 0, vi.fn()));
    const element = document.createElement("div");
    act(() => { result.current.viewportRef.current = element; result.current.fit(); });
    act(() => result.current.zoomAt(100));
    expect(result.current.pixelsPerSecond).toBe(100);
  });
});
