import React, { useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Slider } from "@/components/ui/slider";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Check,
  ChevronDown,
  FileAudio,
  FolderOpen,
  Moon,
  Pause,
  Play,
  RefreshCw,
  Sun,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import "./index.css";
import { ComparisonReviewPrototype } from "./comparison-review.prototype";
import { DiagnosticCanvas, type DiagnosticTimeline } from "./diagnostic-canvas";

type Stage = "recordings" | "preview" | "review" | "render";
type Theme = "system" | "light" | "dark";
type Program = "original" | "automixed" | "difference";
type InputInfo = {
  path: string;
  samplerate: number;
  frames: number;
  channels: number;
  subtype: string;
  format: string;
  problems: { code: string; message: string }[];
};
type Inspection = {
  inputs: InputInfo[];
  problems: { code: string; message: string }[];
};
type ProgressState = { phase: string; completed: number; total: number };
type Status =
  | { state: "idle" | "cancelled" }
  | { state: "running" | "cancelling"; kind?: "full_render"; progress?: ProgressState }
  | { state: "failed"; kind?: "full_render"; error: string }
  | { state: "complete"; kind?: undefined; result: unknown }
  | {
      state: "complete";
      kind: "full_render";
      full_render_result: { destination: string; outputs: string[] };
    };
type Comparison = {
  original_paths: string[];
  automixed_paths: string[];
  start_seconds: number;
  duration_seconds: number;
  playback_gain_db: { original: number; automixed: number };
  diagnostic_timeline?: DiagnosticTimeline;
};
type WaveformStatus = { state: string; result?: { points?: [number, number][] } };
type Destination = { unique: string };
type DesktopApi = {
  status(): Promise<Status>;
  inspect_recording_set(paths: string[]): Promise<Inspection>;
  choose_recordings(): Promise<string[]>;
  start_waveform_overview(paths: string[]): Promise<void>;
  waveform_overview_status(): Promise<WaveformStatus>;
  comparison_playback(): Promise<Comparison>;
  start_preview(paths: string[], start: number, duration: number): Promise<void>;
  cancel_preview(): Promise<void>;
  full_render_destination(paths: string[], directory: string | null): Promise<Destination>;
  choose_full_render_directory(): Promise<string>;
  start_full_render(paths: string[], directory: string | null, overwrite: boolean): Promise<void>;
  cancel_full_render(): Promise<void>;
  export_preview(): Promise<void>;
};

declare global {
  interface Window {
    pywebview?: { api: DesktopApi };
    receiveDroppedPaths?: (paths: string[]) => void;
  }
}
const api = new Proxy({} as DesktopApi,
  {
    get:
      (_t, name: string) =>
      async (...args: unknown[]) => {
        const method = (window.pywebview?.api as unknown as Record<string, ((...args: unknown[]) => Promise<unknown>) | undefined>)?.[name];
        if (!method) throw new Error("Desktop bridge is not ready");
        return method(...args);
      },
  }) as DesktopApi;
const base = (path: string) =>
  path.replaceAll("\\", "/").split("/").pop() || path;
const clock = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds) % 60).padStart(2, "0")}`;

function Waveform({
  paths,
  start,
  duration,
  total,
  onStart,
  onError,
}: {
  paths: string[];
  start: number;
  duration: number;
  total: number;
  onStart: (value: number) => void;
  onError: (message: string) => void;
}) {
  const [points, setPoints] = useState<[number, number][]>([]);
  useEffect(() => {
    if (!paths.length) return;
    let live = true;
    void (async () => {
      try {
        await api.start_waveform_overview(paths);
        let status;
        do {
          await new Promise((r) => setTimeout(r, 40));
          status = await api.waveform_overview_status();
        } while (live && status.state === "loading");
        if (live && status.result) setPoints(status.result.points || []);
      } catch (e) {
        if (live) onError(`The waveform could not be prepared: ${String(e)}`);
      }
    })();
    return () => {
      live = false;
    };
  }, [paths.join("\n")]);
  const d = points.length
    ? points
        .map(
          (p, i) =>
            `${i ? "L" : "M"}${(i / (points.length - 1 || 1)) * 100},${50 - p[1] * 46}`,
        )
        .join(" ") +
      " " +
      [...points]
        .reverse()
        .map((p, j) => {
          const i = points.length - j - 1;
          return `L${(i / (points.length - 1 || 1)) * 100},${50 - p[0] * 46}`;
        })
        .join(" ") +
      " Z"
    : "";
  return (
    <div
      className="waveform"
      role="slider"
      tabIndex={0}
      aria-label="Preview start position"
      aria-valuemin={0}
      aria-valuemax={Math.max(0, total - duration)}
      aria-valuenow={start}
      aria-valuetext={`Start ${clock(start)}, duration ${clock(duration)}`}
      onClick={(e) =>
        onStart(
          Math.max(
            0,
            Math.min(
              Math.max(0, total - duration),
              (e.nativeEvent.offsetX / e.currentTarget.clientWidth) * total,
            ),
          ),
        )
      }
      onKeyDown={(e) => {
        const limit = Math.max(0, total - duration);
        const next =
          e.key === "Home"
            ? 0
            : e.key === "End"
              ? limit
              : e.key === "ArrowLeft" || e.key === "ArrowDown"
                ? Math.max(0, start - 1)
                : e.key === "ArrowRight" || e.key === "ArrowUp"
                  ? Math.min(limit, start + 1)
                  : null;
        if (next !== null) {
          e.preventDefault();
          onStart(next);
        }
      }}
    >
      {d ? (
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path d={d} />
        </svg>
      ) : (
        <span>Preparing waveform overview</span>
      )}
      <i
        style={{
          left: `${(start / total) * 100}%`,
          width: `${(duration / total) * 100}%`,
        }}
      />
    </div>
  );
}

export function App() {
  const prototypeVariant = import.meta.env.DEV && new URLSearchParams(location.search).has("variant");
  const [stage, setStage] = useState<Stage>(prototypeVariant ? "review" : "recordings"),
    [theme, setTheme] = useState<Theme>("system"),
    [paths, setPaths] = useState<string[]>([]),
    [inspection, setInspection] = useState<Inspection | null>(null),
    [error, setError] = useState(""),
    [status, setStatus] = useState<Status>({ state: "idle" }),
    [start, setStart] = useState(0),
    [duration, setDuration] = useState(30),
    [program, setProgram] = useState<Program>("original"),
    [comparison, setComparison] = useState<Comparison | null>(null),
    [fullDirectory, setFullDirectory] = useState(""),
    [destination, setDestination] = useState(""),
    [overwrite, setOverwrite] = useState(false),
    [playing, setPlaying] = useState(false),
    [playbackPosition, setPlaybackPosition] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null),
    audio = useRef<HTMLAudioElement[]>([]),
    audioOffsets = useRef<number[]>([]);
  const active = status.state === "running" || status.state === "cancelling",
    activeKind = active ? status.kind : undefined,
    previewActive = active && activeKind !== "full_render",
    renderActive = active && activeKind === "full_render",
    progress = "progress" in status ? status.progress : undefined;
  const inputDurations = (inspection?.inputs || []).map((i) => i.frames / i.samplerate);
  const total = inputDurations.length ? Math.min(...inputDurations) : 30;
  const valid =
    paths.length >= 2 &&
    !inspection?.problems.length &&
    inspection?.inputs.every((i) => !i.problems.length);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    const media = matchMedia("(prefers-color-scheme: dark)");
    const apply = () =>
      document.documentElement.classList.toggle(
        "dark",
        theme === "dark" || (theme === "system" && media.matches),
      );
    apply();
    media.addEventListener("change", apply);
    heading.current?.focus();
    return () => media.removeEventListener("change", apply);
  }, [stage, theme]);
  useEffect(() => {
    setDuration((value) => Math.max(5, Math.min(value, total)));
    setStart((value) => Math.max(0, Math.min(value, Math.max(0, total - duration))));
  }, [total]);
  useEffect(() => {
    window.receiveDroppedPaths = (next) => void add(next);
    let initialized = false;
    const timeout = window.setTimeout(() => {
      if (!initialized) {
        setError("Desktop bridge did not become ready. Restart the desktop application and try again.");
      }
    }, 10_000);
    const ready = () => {
      if (initialized || !window.pywebview?.api) return;
      initialized = true;
      window.clearTimeout(timeout);
      void refresh();
    };
    window.addEventListener("pywebviewready", ready);
    ready();
    return () => {
      window.clearTimeout(timeout);
      window.removeEventListener("pywebviewready", ready);
    };
  }, []);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => void refresh(), 350);
    return () => clearInterval(timer);
  }, [active]);
  async function refresh() {
    try {
      const next = (await api.status()) as Status;
      setStatus(next);
      if (next.state === "failed") setError(next.error);
      if (
        next.state === "complete" &&
        next.kind !== "full_render" &&
        next.result
      ) {
        setStage("review");
        await loadComparison();
      }
    } catch (e) {
      setError(`Unable to refresh the operation: ${String(e)}`);
      setStatus({ state: "failed", error: String(e) });
    }
  }
  async function inspectExact(next: string[]) {
    try {
      setError("");
      const result = next.length ? await api.inspect_recording_set(next) : null;
      setPaths(next);
      setInspection(result);
    } catch (e) {
      setError(String(e));
    }
  }
  async function add(next: string[]) {
    await inspectExact([...new Set([...paths, ...next])]);
  }
  async function choose() {
    try {
      await add(await api.choose_recordings());
    } catch (e) {
      setError(`Recordings could not be selected: ${String(e)}`);
    }
  }
  async function cancel(kind: "preview" | "full_render") {
    try {
      setStatus({ state: "cancelling", ...(kind === "full_render" ? { kind } : {}) });
      await (kind === "full_render" ? api.cancel_full_render() : api.cancel_preview());
    } catch (e) {
      setError(`Cancellation failed: ${String(e)}`);
      await refresh();
    }
  }
  async function loadComparison() {
    try {
      const data = await api.comparison_playback();
      setComparison(data);
      setProgram("original");
      setPlaybackPosition(0);
    } catch (e) {
      setError(`Preview completed, but the comparison could not be loaded: ${String(e)}`);
    }
  }
  function changeStage(next: Stage) {
    audio.current.forEach((a) => a.pause());
    setPlaying(false);
    setStage(next);
  }
  async function play() {
    if (!comparison) return;
    if (playing) {
      audio.current.forEach((a) => a.pause());
      setPlaying(false);
      return;
    }
    audio.current.forEach((a) => {
      a.pause();
      a.src = "";
    });
    const context = new AudioContext(),
      protection = context.createDynamicsCompressor();
    protection.connect(context.destination);
    const originalGain = Math.pow(
      10,
      comparison.playback_gain_db.original / 20,
    );
    const automixedGain = Math.pow(
      10,
      comparison.playback_gain_db.automixed / 20,
    );
    const programs: [string[], number, number][] =
      program === "difference"
        ? [
            [
              comparison.original_paths,
              -originalGain,
              comparison.start_seconds,
            ],
            [comparison.automixed_paths, automixedGain, 0],
          ]
        : [
            [
              program === "original"
                ? comparison.original_paths
                : comparison.automixed_paths,
              program === "original" ? originalGain : automixedGain,
              program === "original" ? comparison.start_seconds : 0,
            ],
          ];
    audioOffsets.current = programs.flatMap(([paths, , offset]) => paths.map(() => offset));
    audio.current = programs.flatMap(([paths, gain, offset]) =>
      paths.map((path, index) => {
        const item = new Audio(`file:///${path.replaceAll("\\", "/")}`);
        const relative = playbackPosition;
        item.currentTime = offset + relative;
        if (index === 0) {
          item.ontimeupdate = () => setPlaybackPosition(Math.max(0, item.currentTime - offset));
          item.onended = () => setPlaying(false);
        }
        const source = context.createMediaElementSource(item),
          bus = context.createGain();
        bus.gain.value = gain;
        source.connect(bus);
        bus.connect(protection);
        return item;
      }),
    );
    await context.resume();
    await Promise.all(audio.current.map((a) => a.play()));
    setPlaying(true);
  }
  async function preview() {
    try {
      setError("");
      await api.start_preview(paths, start, duration);
      setStatus({ state: "running" });
      void refresh();
    } catch (e) {
      setError(`Preview could not start: ${String(e)}`);
      setStatus({ state: "failed", error: String(e) });
    }
  }
  async function openRender() {
    try {
      setError("");
      const result = await api.full_render_destination(paths, fullDirectory || null);
      setDestination(result.unique);
      changeStage("render");
    } catch (e) {
      setError(`The render destination could not be prepared: ${String(e)}`);
    }
  }
  async function render() {
    try {
      setError("");
      await api.start_full_render(paths, fullDirectory || null, overwrite);
      setStatus({ state: "running", kind: "full_render" });
      void refresh();
    } catch (e) {
      setError(`Full Render could not start: ${String(e)}`);
      setStatus({ state: "failed", kind: "full_render", error: String(e) });
    }
  }
  const steps: [Stage, string][] = [
    ["recordings", "Recordings"],
    ["preview", "Preview"],
    ["review", "Review"],
    ["render", "Render"],
  ];
  return (
    <TooltipProvider>
      <SidebarProvider>
        <Sidebar collapsible="offcanvas">
          <SidebarHeader>
            <div className="brand">
              <span>PA</span>
              <div>
                <strong>Podcast Automixer</strong>
                <small>Offline audio workspace</small>
              </div>
            </div>
          </SidebarHeader>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupContent>
                <SidebarMenu>
                  {steps.map(([id, label], i) => (
                    <SidebarMenuItem key={id}>
                      <SidebarMenuButton
                        aria-label={label}
                        isActive={stage === id}
                        disabled={steps.findIndex((s) => s[0] === stage) < i}
                        onClick={() => changeStage(id)}
                      >
                        <span className="step">{i + 1}</span>
                        {label}
                        {steps.findIndex((s) => s[0] === stage) > i && (
                          <Check />
                        )}
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
          <SidebarFooter>
            <ToggleGroup
              value={[theme]}
              onValueChange={(v) => v[0] && setTheme(v[0] as Theme)}
              aria-label="Appearance"
            >
              <Tooltip>
                <TooltipTrigger
                  render={
                    <ToggleGroupItem value="system">System</ToggleGroupItem>
                  }
                />
                <TooltipContent>Use system appearance</TooltipContent>
              </Tooltip>
              <ToggleGroupItem value="light" aria-label="Light appearance">
                <Sun />
              </ToggleGroupItem>
              <ToggleGroupItem value="dark" aria-label="Dark appearance">
                <Moon />
              </ToggleGroupItem>
            </ToggleGroup>
          </SidebarFooter>
        </Sidebar>
        <SidebarInset>
          <main className="workspace">
            <div className="mobile-navigation">
              <SidebarTrigger />
              <span>Workflow and appearance</span>
            </div>
            <header>
              <div>
                <p>{steps.find((s) => s[0] === stage)?.[1]}</p>
                <h1 ref={heading} tabIndex={-1}>
                  {stage === "recordings"
                    ? "Build a synchronized recording set."
                    : stage === "preview"
                      ? "Choose the section worth testing."
                      : stage === "review"
                        ? "Listen for what the automix changed."
                        : "Confirm the final deliverables."}
                </h1>
              </div>
              <Badge variant="secondary">Local processing</Badge>
            </header>
            <Separator />
            {error && (
              <Alert variant="destructive">
                <AlertTitle>Could not continue</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            {stage === "recordings" && (
              <section className="surface">
                <div className="drop" onDragOver={(e) => e.preventDefault()}>
                  <FileAudio />
                  <strong>Drop synchronized WAV recordings</strong>
                  <span>
                    Mono WAV, WAVEX, or RF64 with matching technical properties.
                  </span>
                  <Button variant="outline" onClick={choose}>
                    <Upload data-icon="inline-start" />
                    Choose recordings
                  </Button>
                </div>
                {inspection?.inputs.length ? (
                  <div className="recording-list">
                    {inspection.inputs.map((item, index) => (
                      <React.Fragment key={item.path}>
                        <div className="recording-row">
                          <FileAudio />
                          <div className="filename">
                            <strong>{base(item.path)}</strong>
                            <small>{item.path}</small>
                          </div>
                          <Input
                            aria-label={`Microphone name for ${base(item.path)}`}
                            defaultValue={base(item.path).replace(
                              /\.[^.]+$/,
                              "",
                            )}
                          />
                          <span>{clock(item.frames / item.samplerate)}</span>
                          <span>
                            {item.format} {item.subtype}
                          </span>
                          <Badge
                            variant={
                              item.problems.length ? "destructive" : "secondary"
                            }
                          >
                            {item.problems.length ? "Check" : "Ready"}
                          </Badge>
                          <Tooltip>
                            <TooltipTrigger
                              render={
                                <Button
                                  variant="ghost"
                                  size="icon-sm"
                                  aria-label="Replace recording"
                                  onClick={async () => {
                                    const selected =
                                      await api.choose_recordings();
                                    if (selected[0])
                                      await inspectExact(
                                        paths.map((path) =>
                                          path === item.path
                                            ? selected[0]
                                            : path,
                                        ),
                                      );
                                  }}
                                >
                                  <RefreshCw />
                                </Button>
                              }
                            />
                            <TooltipContent>Replace recording</TooltipContent>
                          </Tooltip>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label="Remove recording"
                            onClick={() =>
                              void inspectExact(
                                paths.filter((p) => p !== item.path),
                              )
                            }
                          >
                            <Trash2 />
                          </Button>
                        </div>
                        <Collapsible>
                          <CollapsibleTrigger
                            render={
                              <Button variant="ghost" size="sm">
                                <ChevronDown data-icon="inline-start" />
                                Technical details
                              </Button>
                            }
                          />
                          <CollapsibleContent className="details">
                            {item.samplerate} Hz · {item.channels} channel ·{" "}
                            {item.frames.toLocaleString()} frames
                          </CollapsibleContent>
                        </Collapsible>
                        {index < inspection.inputs.length - 1 && <Separator />}
                      </React.Fragment>
                    ))}
                  </div>
                ) : null}
                <footer>
                  <span>
                    {valid
                      ? "Recording Set is compatible."
                      : "Add at least two compatible recordings."}
                  </span>
                  <Button
                    data-primary-action
                    disabled={!valid}
                    onClick={() => changeStage("preview")}
                  >
                    Choose Preview Range
                  </Button>
                </footer>
              </section>
            )}
            {stage === "preview" && (
              <section className="surface">
                <div className="section-heading">
                  <div>
                    <h2>Create a disposable Preview Run</h2>
                    <p>
                      Preview audio stays in app-owned temporary storage until
                      you export it.
                    </p>
                  </div>
                  <Badge variant="outline">Not a deliverable</Badge>
                </div>
                <Waveform
                  paths={paths}
                  start={start}
                  duration={duration}
                  total={total}
                  onStart={setStart}
                  onError={setError}
                />
                <FieldGroup className="range-fields">
                  <Field>
                    <FieldLabel>Start</FieldLabel>
                    <Input
                      type="number"
                      value={start}
                      onChange={(e) => setStart(Number(e.target.value))}
                    />
                  </Field>
                  <Field>
                    <FieldLabel>Duration</FieldLabel>
                    <Input
                      type="number"
                      min={5}
                      max={Math.min(600, total)}
                      value={duration}
                      onChange={(e) => setDuration(Number(e.target.value))}
                    />
                  </Field>
                </FieldGroup>
                {previewActive && (
                  <div className="operation" role="status">
                    <div>
                      <strong>
                        {progress?.phase?.replaceAll("_", " ") ||
                          "Preparing Preview Run"}
                      </strong>
                      <Button
                        variant="outline"
                        aria-label="Cancel Preview"
                        onClick={() => void cancel("preview")}
                      >
                        <X data-icon="inline-start" />
                        Cancel
                      </Button>
                    </div>
                    <Progress
                      value={
                        progress?.total
                          ? (progress.completed /
                              progress.total) *
                            100
                          : 12
                      }
                    />
                  </div>
                )}
                <footer>
                  <Button
                    variant="ghost"
                    onClick={() => changeStage("recordings")}
                  >
                    Back
                  </Button>
                  <Button data-primary-action disabled={previewActive} onClick={preview}>
                    Create Preview
                  </Button>
                </footer>
              </section>
            )}
            {stage === "review" && (prototypeVariant ? <ComparisonReviewPrototype /> : (
              <section className="surface review">
                <div className="section-heading">
                  <div>
                    <h2>Comparison Playback</h2>
                    <p>
                      All modes share one protected monitor output. Source and
                      Preview files remain unchanged.
                    </p>
                  </div>
                  <Badge variant="secondary">Preview complete</Badge>
                </div>
                <ToggleGroup
                  value={[program]}
                  onValueChange={(v) => {
                    if (!v[0]) return;
                    audio.current.forEach((item) => item.pause());
                    setPlaying(false);
                    setProgram(v[0] as Program);
                  }}
                  aria-label="Comparison program"
                  className="programs"
                >
                  <ToggleGroupItem value="original">Original</ToggleGroupItem>
                  <ToggleGroupItem value="automixed">Automixed</ToggleGroupItem>
                  <ToggleGroupItem value="difference">
                    Difference
                  </ToggleGroupItem>
                </ToggleGroup>
                {program === "difference" && (
                  <Alert>
                    <AlertTitle>Difference = Automixed − Original</AlertTitle>
                    <AlertDescription>
                      It isolates gain movement so you can hear what changed. It
                      is a monitoring view, not a deliverable.
                    </AlertDescription>
                  </Alert>
                )}
                {comparison?.diagnostic_timeline && (
                  <DiagnosticCanvas timeline={comparison.diagnostic_timeline} />
                )}
                <div className="transport">
                  <Button
                    variant="outline"
                    size="icon-lg"
                    aria-label={
                      playing ? "Pause comparison" : "Play comparison"
                    }
                    onClick={play}
                  >
                    {playing ? <Pause /> : <Play />}
                  </Button>
                  <div>
                    <strong>
                      {program[0].toUpperCase() + program.slice(1)} monitor
                    </strong>
                    <span>
                      {comparison
                        ? `${clock(comparison.start_seconds)} – ${clock(comparison.start_seconds + comparison.duration_seconds)}`
                        : "Loading comparison"}
                    </span>
                  </div>
                  <Slider
                    value={[playbackPosition]}
                    max={comparison?.duration_seconds || 30}
                    step={0.1}
                    aria-label="Playback position"
                    onValueChange={(value) => {
                      const next = (Array.isArray(value) ? value[0] : value) || 0;
                      setPlaybackPosition(next);
                      audio.current.forEach((item, index) => {
                        item.currentTime = next + (audioOffsets.current[index] || 0);
                      });
                    }}
                  />
                </div>
                <footer className="review-actions">
                  <Button
                    variant="outline"
                    onClick={() => changeStage("preview")}
                  >
                    Try another section
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={async () => {
                      try {
                        setError("");
                        await api.export_preview();
                      } catch (e) {
                        setError(`Preview export failed: ${String(e)}`);
                      }
                    }}
                  >
                    <FolderOpen data-icon="inline-start" />
                    Export Preview
                  </Button>
                  <Button data-primary-action onClick={openRender}>Render full recordings</Button>
                </footer>
              </section>
            ))}
            {stage === "render" && (
              <section className="surface">
                <div className="section-heading">
                  <div>
                    <h2>Full Render confirmation</h2>
                    <p>
                      Final deliverables are written separately from disposable
                      Preview Runs.
                    </p>
                  </div>
                  <Badge>Final output</Badge>
                </div>
                <FieldGroup>
                  <Field>
                    <FieldLabel>Destination</FieldLabel>
                    <div className="destination">
                      <Input value={destination} readOnly />
                      <Button
                        variant="outline"
                        onClick={async () => {
                          try {
                            setError("");
                            const value = await api.choose_full_render_directory();
                            if (value) {
                              setFullDirectory(value);
                              const result = await api.full_render_destination(paths, value);
                              setDestination(result.unique);
                            }
                          } catch (e) {
                            setError(`The render destination could not be changed: ${String(e)}`);
                          }
                        }}
                      >
                        Choose folder
                      </Button>
                    </div>
                  </Field>
                  <Field orientation="horizontal">
                    <Checkbox
                      checked={overwrite}
                      onCheckedChange={(v) => setOverwrite(Boolean(v))}
                    />
                    <FieldLabel>
                      Replace existing files in the selected folder
                    </FieldLabel>
                  </Field>
                </FieldGroup>
                {renderActive && (
                  <div className="operation" role="status">
                    <div>
                      <strong>
                        {progress?.phase?.replaceAll("_", " ") ||
                          "Preparing Full Render"}
                      </strong>
                      <Button
                        variant="outline"
                        aria-label="Cancel Full Render"
                        onClick={() => void cancel("full_render")}
                      >
                        <X data-icon="inline-start" />
                        Cancel
                      </Button>
                    </div>
                    <Progress
                      value={
                        progress?.total
                          ? (progress.completed /
                              progress.total) *
                            100
                          : 12
                      }
                    />
                  </div>
                )}
                <footer>
                  <Button variant="ghost" onClick={() => changeStage("review")}>
                    Back to Review
                  </Button>
                  <Button data-primary-action disabled={renderActive} onClick={render}>
                    Render full recordings
                  </Button>
                </footer>
              </section>
            )}
          </main>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  );
}
const root = document.getElementById("root");
if (root) ReactDOM.createRoot(root).render(<App />);
