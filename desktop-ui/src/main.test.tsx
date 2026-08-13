// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./main";
import { ComparisonAudioController } from "./comparison-audio-controller";

const inputs = ["host.wav", "guest.wav"].map((path) => ({
  path,
  samplerate: 48_000,
  frames: 48_000 * 120,
  channels: 1,
  subtype: "PCM_24",
  format: "WAV",
  problems: [],
}));

let operation: "idle" | "running" | "cancelling" | "complete" = "idle";
let kind: "preview" | "full_render" = "preview";
let selectedDirectory: string | null = null;
let progress: { phase: string; completed: number; total: number } | undefined;
const api = {
  status: vi.fn(async () => ({
    state: operation,
    ...(kind === "full_render" ? { kind: "full_render" } : {}),
    ...(operation === "running" && progress ? { progress } : {}),
    ...(operation === "complete" ? { result: {} } : {}),
  })),
  inspect_recording_set: vi.fn(async () => ({ inputs, problems: [] })),
  choose_recordings: vi.fn(async () => inputs.map(({ path }) => path)),
  start_waveform_overview: vi.fn(async () => undefined),
  waveform_overview_status: vi.fn(async () => ({ state: "complete", result: { points: [[-0.5, 0.5]] } })),
  comparison_playback: vi.fn(async () => ({
    original_paths: ["host.wav"], automixed_paths: ["preview.wav"],
    start_seconds: 0, duration_seconds: 30,
    playback_gain_db: { original: 0, automixed: 0 },
    waveforms: {
      duration_seconds: 30,
      point_limit: 512,
      original: [[-0.8, 0.8], [-0.4, 0.4]],
      automixed: [[-0.5, 0.5], [-0.2, 0.2]],
      difference: [[-0.3, 0.3], [-0.2, 0.2]],
    },
  })),
  start_preview: vi.fn(async () => { operation = "running"; kind = "preview"; }),
  cancel_preview: vi.fn(async () => { operation = "cancelling"; }),
  full_render_destination: vi.fn(async (_paths: string[], directory: string | null) => ({ unique: `${directory || "default"}/Automixed` })),
  choose_full_render_directory: vi.fn(async () => "D:/Podcast"),
  start_full_render: vi.fn(async (_paths: string[], directory: string | null) => { selectedDirectory = directory; operation = "running"; kind = "full_render"; }),
  cancel_full_render: vi.fn(async () => { operation = "cancelling"; }),
  export_preview: vi.fn(async () => undefined),
};

function primaryActions() {
  return document.querySelectorAll('button[data-primary-action]:not([disabled])');
}

beforeEach(() => {
  operation = "idle";
  kind = "preview";
  selectedDirectory = null;
  progress = undefined;
  vi.clearAllMocks();
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1024 });
  Object.defineProperty(window, "pywebview", { configurable: true, value: { api } });
  Object.defineProperty(window, "matchMedia", { configurable: true, value: () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }) });
  const node = () => ({ connect: vi.fn(), gain: { value: 0, setTargetAtTime: vi.fn() } });
  Object.defineProperty(window, "AudioContext", { configurable: true, value: class {
    currentTime = 0; destination = node();
    createDynamicsCompressor = node; createGain = node; createMediaElementSource = node;
    resume = vi.fn(async () => undefined);
  } });
  Object.defineProperty(window, "Audio", { configurable: true, value: class {
    currentTime = 0; ontimeupdate = null; onended = null;
    pause = vi.fn(); play = vi.fn(async () => undefined);
  } });
});
afterEach(cleanup);

describe("desktop workflow", () => {
  it("waits for the desktop bridge before the single initial refresh", async () => {
    Object.defineProperty(window, "pywebview", { configurable: true, value: undefined });

    render(<App />);

    expect(api.status).not.toHaveBeenCalled();
    expect(screen.queryByText(/Desktop bridge is not ready/)).not.toBeInTheDocument();

    Object.defineProperty(window, "pywebview", { configurable: true, value: { api } });
    window.dispatchEvent(new Event("pywebviewready"));

    await waitFor(() => expect(api.status).toHaveBeenCalledTimes(1));
    expect(screen.queryByText(/Desktop bridge is not ready/)).not.toBeInTheDocument();
  });

  it("reports an actionable error when the desktop bridge never becomes ready", async () => {
    vi.useFakeTimers();
    Object.defineProperty(window, "pywebview", { configurable: true, value: undefined });

    try {
      render(<App />);
      await act(() => vi.advanceTimersByTimeAsync(10_000));

      expect(screen.getByText(/desktop bridge did not become ready/i)).toBeVisible();
      expect(screen.getByText(/restart the desktop application/i)).toBeVisible();
    } finally {
      vi.useRealTimers();
    }
  });

  it("reports a genuine bridge rejection after readiness", async () => {
    api.status.mockRejectedValueOnce(new Error("bridge connection failed"));

    render(<App />);

    expect(await screen.findByText(/Unable to refresh the operation: Error: bridge connection failed/)).toBeVisible();
  });

  it("keeps the workspace and keyboard-accessible navigation available at 450 pixels", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 450 });
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: (query: string) => ({
        matches: query === "(max-width: 767px)",
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    });
    const user = userEvent.setup();

    render(<App />);

    expect(screen.getByRole("heading", { name: "Build a synchronized recording set." })).toBeVisible();
    expect(screen.getByRole("button", { name: "Choose recordings" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Choose recordings" }));
    await user.click(await screen.findByRole("button", { name: "Choose Preview Range" }));
    await user.click(screen.getByRole("button", { name: "Create Preview" }));
    operation = "complete";
    await user.click(await screen.findByRole("button", { name: "Render full recordings" }, { timeout: 1500 }));

    const navigation = await screen.findByRole("button", { name: "Toggle Sidebar" });
    navigation.focus();
    await user.keyboard("{Enter}");

    for (const [name, heading] of [
      ["Render", "Confirm the final deliverables."],
      ["Review", "Listen for what the automix changed."],
      ["Preview", "Choose the section worth testing."],
      ["Recordings", "Build a synchronized recording set."],
    ]) {
      const stageButton = screen.getByRole("button", { name });
      expect(stageButton).toBeEnabled();
      stageButton.focus();
      await user.keyboard("{Enter}");
      await user.keyboard("{Escape}");
      expect(screen.getByRole("heading", { name: heading })).toBeVisible();
      expect(primaryActions()).toHaveLength(1);
      navigation.focus();
      await user.keyboard("{Enter}");
    }
    for (const [name, theme] of [
      ["System", "system"],
      ["Light appearance", "light"],
      ["Dark appearance", "dark"],
    ]) {
      const appearance = screen.getByRole("button", { name });
      appearance.focus();
      await user.keyboard("{Enter}");
      expect(document.documentElement.dataset.theme).toBe(theme);
    }
  });

  it("drives recordings through Preview processing and Review with one idle primary action", async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(primaryActions()).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Choose recordings" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Choose Preview Range" })).toBeEnabled());
    expect(primaryActions()).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Choose Preview Range" }));
    expect(primaryActions()).toHaveLength(1);
    const startInput = screen.getByRole("spinbutton", { name: "Start" });
    expect(startInput).toHaveValue(0);
    fireEvent.change(startInput, { target: { value: "12.34" } });
    expect(startInput).toHaveValue(12.3);
    progress = { phase: "analyzing", completed: 25, total: 100 };
    await user.click(screen.getByRole("button", { name: "Create Preview" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Cancel Preview" })).toBeVisible());
    expect(screen.getByText("Analyzing recordings")).toBeVisible();
    expect(screen.getByText(/25% · 25 \/ 100 · Elapsed 0:00\.0/)).toBeVisible();
    expect(api.start_preview).toHaveBeenCalledWith(
      inputs.map(({ path }) => path),
      12.34,
      30,
    );
    expect(primaryActions()).toHaveLength(0);
    operation = "complete";
    await waitFor(() => expect(screen.getByRole("button", { name: "Render full recordings" })).toBeVisible(), { timeout: 1500 });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Preview Run complete. Review opened.",
    );
    expect(screen.queryByRole("button", { name: "Cancel Preview" })).not.toBeInTheDocument();
    expect(primaryActions()).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Try another section" }));
    expect(screen.getByRole("spinbutton", { name: "Start" })).toHaveValue(12.3);
  });

  it("shows and routes comparison shortcuts while ignoring editable controls", async () => {
    const user = userEvent.setup();
    const select = vi.spyOn(ComparisonAudioController.prototype, "select");
    const toggle = vi.spyOn(ComparisonAudioController.prototype, "toggle");
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Choose recordings" }));
    await user.click(await screen.findByRole("button", { name: "Choose Preview Range" }));
    await user.click(screen.getByRole("button", { name: "Create Preview" }));
    operation = "complete";
    await screen.findByText(/O Original · A Automixed · D Difference/);

    await user.keyboard("d ");
    expect(select).toHaveBeenCalledWith("difference");
    expect(toggle).toHaveBeenCalledTimes(1);

    const input = document.createElement("input");
    document.body.append(input);
    input.focus();
    await user.keyboard("a");
    expect(select).toHaveBeenCalledTimes(1);
    input.remove();
  });

  it("shows a shared waveform playhead and supports pointer and keyboard seeking", async () => {
    const user = userEvent.setup();
    const seek = vi.spyOn(ComparisonAudioController.prototype, "seek");
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Choose recordings" }));
    await user.click(await screen.findByRole("button", { name: "Choose Preview Range" }));
    await user.click(screen.getByRole("button", { name: "Create Preview" }));
    operation = "complete";

    const waveform = await screen.findByRole("slider", { name: "Comparison playback position" });
    Object.defineProperty(waveform, "getBoundingClientRect", {
      value: () => ({ left: 0, width: 600, top: 0, right: 600, bottom: 190, height: 190, x: 0, y: 0, toJSON: () => ({}) }),
    });
    fireEvent.pointerDown(waveform, { clientX: 300, pointerId: 1 });
    expect(seek).toHaveBeenCalledWith(15);
    waveform.focus();
    await user.keyboard("{End}");
    expect(seek).toHaveBeenCalledWith(30);
    expect(waveform.querySelectorAll(".original-envelope, .automixed-envelope")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Difference" }));
    expect(waveform.querySelector(".difference-envelope")).toBeInTheDocument();
  });

  it("keeps the chosen render directory across Back and retry, and shows Cancel only while active", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Choose recordings" }));
    await user.click(await screen.findByRole("button", { name: "Choose Preview Range" }));
    await user.click(screen.getByRole("button", { name: "Create Preview" }));
    operation = "complete";
    await user.click(await screen.findByRole("button", { name: "Render full recordings" }, { timeout: 1500 }));
    await user.click(screen.getByRole("button", { name: "Choose folder" }));
    expect(screen.getByDisplayValue("D:/Podcast/Automixed")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Back to Review" }));
    await user.click(screen.getByRole("button", { name: "Try another section" }));
    operation = "idle";
    await user.click(screen.getByRole("button", { name: "Create Preview" }));
    operation = "complete";
    await waitFor(() => expect(screen.getByRole("button", { name: "Render full recordings" })).toBeVisible(), { timeout: 1500 });
    await user.click(screen.getByRole("button", { name: "Render full recordings" }));
    expect(await screen.findByDisplayValue("D:/Podcast/Automixed")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Render full recordings" }));
    expect(selectedDirectory).toBe("D:/Podcast");
    expect(await screen.findByRole("button", { name: "Cancel Full Render" })).toBeVisible();
    operation = "complete";
    await waitFor(() => expect(screen.queryByRole("button", { name: "Cancel Full Render" })).not.toBeInTheDocument(), { timeout: 1500 });
  });

  it("exposes theme names and keyboard waveform range semantics", async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(screen.getByRole("button", { name: "System" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Light appearance" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Dark appearance" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Choose recordings" }));
    await user.click(await screen.findByRole("button", { name: "Choose Preview Range" }));
    const waveform = screen.getByRole("slider", { name: "Preview start position" });
    expect(waveform).toHaveAttribute("aria-valuemax", "90");
    await user.type(waveform, "{End}");
    expect(waveform).toHaveAttribute("aria-valuenow", "90");
  });
});
