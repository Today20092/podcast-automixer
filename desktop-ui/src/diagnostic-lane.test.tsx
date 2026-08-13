// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { diagnosticDomains, RecordingSetDiagnostics, reviewMoments, type DiagnosticTrack } from "./diagnostic-lane";

afterEach(cleanup);

function tracks(count: number, prefix = "Mic"): DiagnosticTrack[] {
  return Array.from({ length: count }, (_, index) => ({
    id: `track-${index + 1}`,
    name: `${prefix} ${index + 1}`,
    color: ["#3b82f6", "#f59e0b", "#10b981", "#ef4444"][index % 4],
    frames: [
      { seconds: 0, speech: index === 0, target_open: index === 0, gain_db: index === 0 ? 0 : -6, response: index === 0 ? "open" : "attenuated" },
      { seconds: 30, speech: false, target_open: false, gain_db: -6, response: "attenuated" },
    ],
  }));
}

describe("Recording Set diagnostics", () => {
  it("renders an explicit empty state for missing diagnostics", () => {
    render(<RecordingSetDiagnostics tracks={[]} playhead={0} />);
    expect(screen.getByRole("status")).toHaveTextContent("No microphone diagnostics");
  });

  it.each([1, 6, 8])("renders %i synchronized microphone lanes and every inspector row", (count) => {
    render(<RecordingSetDiagnostics tracks={tracks(count)} playhead={0} />);
    expect(screen.getAllByRole("region", { name: /automix explanation/ })).toHaveLength(count);
    expect(screen.getByLabelText("Playhead Inspector").querySelectorAll("p")).toHaveLength(count);
    expect(screen.getAllByLabelText(/applied gain in decibels/)).toHaveLength(count);
  });

  it("preserves replacement data and Recording Set order without stale lanes", () => {
    const { rerender } = render(<RecordingSetDiagnostics tracks={tracks(2, "Old")} playhead={0} />);
    rerender(<RecordingSetDiagnostics tracks={tracks(2, "New").reverse()} playhead={0} />);
    const lanes = screen.getAllByRole("region", { name: /automix explanation/ });
    expect(lanes.map((lane) => lane.getAttribute("aria-label"))).toEqual(["New 2 automix explanation", "New 1 automix explanation"]);
    expect(screen.queryByText("Old 1")).not.toBeInTheDocument();
  });

  it("uses fixed shared domains for constant gain and uneven intervals", () => {
    const scene = tracks(2);
    scene[0].frames = [{ seconds: 0, speech: true, target_open: true, gain_db: 0, response: "open" }];
    scene[1].frames = [{ seconds: 8, speech: false, target_open: false, gain_db: -12, response: "attenuated" }];
    expect(diagnosticDomains(scene)).toEqual({ duration: 8, minimumDb: -12 });
    render(<RecordingSetDiagnostics tracks={scene} playhead={4} />);
    expect(screen.getByText(/Speaking · Open target · 0.0 dB/)).toBeVisible();
    expect(screen.getByText(/Silent · Attenuate target · -12.0 dB/)).toBeVisible();
  });

  it("distinguishes flagged decision mismatches from contextual ownership moments", () => {
    const scene: DiagnosticTrack[] = [
      { id: "host", name: "Host", frames: [{ seconds: 0, speech: true, target_open: false, gain_db: -6, response: "closing" }, { seconds: .5, speech: false, target_open: true, gain_db: -3, response: "opening" }] },
      { id: "guest", name: "Guest", frames: [{ seconds: 0, speech: false, target_open: false, gain_db: -6, response: "attenuated" }, { seconds: .5, speech: true, target_open: true, gain_db: 0, response: "open" }] },
    ];
    const moments = reviewMoments(scene);
    expect(moments).toEqual(expect.arrayContaining([
      expect.objectContaining({ kind: "speaking-attenuated", flagged: true }),
      expect.objectContaining({ kind: "silent-open", flagged: true }),
      expect.objectContaining({ kind: "rapid-switch", flagged: true }),
      expect.objectContaining({ kind: "multiple-active", flagged: false }),
      expect.objectContaining({ kind: "no-clear-owner", flagged: false }),
    ]));
  });

  it("seeks before review moments and supports solo, filters, and lane collapse by keyboard-equivalent buttons", async () => {
    const user = userEvent.setup();
    const seek = vi.fn();
    const solo = vi.fn();
    const scene = tracks(2);
    scene[0].frames = [{ seconds: 5, speech: true, target_open: false, gain_db: -6, response: "closing" }];
    scene[1].frames = [{ seconds: 5, speech: false, target_open: true, gain_db: 0, response: "open" }];
    render(<RecordingSetDiagnostics tracks={scene} playhead={5} onSeek={seek} onSolo={solo} />);

    await user.click(screen.getByRole("button", { name: /Speaking while attenuated at 5.0 seconds, flagged/ }));
    expect(seek).toHaveBeenCalledWith(4);
    await user.click(screen.getByRole("button", { name: "Solo Mic 1" }));
    expect(solo).toHaveBeenLastCalledWith(0);
    await user.click(screen.getByRole("button", { name: "Stop soloing Mic 1" }));
    expect(solo).toHaveBeenLastCalledWith(null);
    await user.click(screen.getByRole("button", { name: "Collapse Mic 1 lane" }));
    expect(screen.getByRole("button", { name: "Expand Mic 1 lane" })).toHaveAttribute("aria-expanded", "false");
    await user.click(screen.getByRole("button", { name: "Active now" }));
    expect(screen.queryByRole("region", { name: "Mic 1 automix explanation" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Mic 2 automix explanation" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Flagged" }));
    expect(screen.getAllByRole("region", { name: /automix explanation/ })).toHaveLength(2);
  });
});
