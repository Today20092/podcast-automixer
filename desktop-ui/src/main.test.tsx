// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./main";

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
const api = {
  status: vi.fn(async () => ({
    state: operation,
    ...(kind === "full_render" ? { kind: "full_render" } : {}),
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
  vi.clearAllMocks();
  Object.defineProperty(window, "pywebview", { configurable: true, value: { api } });
  Object.defineProperty(window, "matchMedia", { configurable: true, value: () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }) });
});
afterEach(cleanup);

describe("desktop workflow", () => {
  it("drives recordings through Preview processing and Review with one idle primary action", async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(primaryActions()).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Choose recordings" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Choose Preview Range" })).toBeEnabled());
    expect(primaryActions()).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Choose Preview Range" }));
    expect(primaryActions()).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Create Preview" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Cancel Preview" })).toBeVisible());
    expect(primaryActions()).toHaveLength(0);
    operation = "complete";
    await waitFor(() => expect(screen.getByRole("button", { name: "Render full recordings" })).toBeVisible(), { timeout: 1500 });
    expect(screen.queryByRole("button", { name: "Cancel Preview" })).not.toBeInTheDocument();
    expect(primaryActions()).toHaveLength(1);
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
