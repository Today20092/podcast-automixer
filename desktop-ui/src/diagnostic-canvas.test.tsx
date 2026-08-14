// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { chooseEnvelopeLevel, DiagnosticCanvas, type DiagnosticTimeline } from "./diagnostic-canvas";

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { constructor(private callback: ResizeObserverCallback) {} observe() { this.callback([], this as unknown as ResizeObserver); } disconnect() {} });
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({ scale:vi.fn(), clearRect:vi.fn(), beginPath:vi.fn(), lineTo:vi.fn(), fill:vi.fn(), fillRect:vi.fn(), stroke:vi.fn() })) as never;
});

describe("diagnostic canvas", () => {
  it("chooses the cached envelope nearest the visible pixel width", () => {
    const levels = [Array(32).fill([0, 1]), Array(128).fill([0, 1]), Array(512).fill([0, 1])];
    expect(chooseEnvelopeLevel(levels, 100)).toHaveLength(128);
  });
  it("renders every Recording Set lane and inspector state", () => {
    const lane = (name: string, color: string) => ({ recording_identity:name, name, color, waveform_levels:[[[0, 1]] as [number, number][]], gain_adjusted_waveform_levels:[[[0, .5]] as [number, number][]], speech_evidence:[true], automix_target:[true], applied_gain_db:[0], evidence_gaps:[] });
    const timeline: DiagnosticTimeline = { duration_seconds:1, frame_ms:100, db_domain:{ minimum:-12, maximum:0 }, lanes:[lane("Mic 1", "#3b82f6"), lane("Mic 2", "#f59e0b")] };
    render(<DiagnosticCanvas timeline={timeline} />);
    expect(screen.getByLabelText("Pinned inspector").textContent).toContain("Mic 1: speech yes, target open, gain 0.0 dB");
    expect(screen.getAllByRole("article")).toHaveLength(2);
  });
});
