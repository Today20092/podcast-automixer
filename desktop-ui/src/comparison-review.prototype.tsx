// PROTOTYPE — three Comparison Playback layouts, switchable with ?variant=A|B|C.
// Verdict: Variant B, Editorial Timeline. Desktop-only and intentionally widescreen.
// Production direction: TanStack Charts for gain timelines; specialized envelope renderer for waveforms.
import React, { useEffect, useMemo, useState } from "react";
import { Pause, Play, Repeat2 } from "lucide-react";
import "./comparison-review.prototype.css";
import { TanStackGainPrototype } from "./tanstack-gain.prototype";
import { useDiagnosticViewport } from "./diagnostic-viewport";

type Variant = "A" | "B" | "C";
type Program = "original" | "automixed" | "difference";
const duration = 60;
const tracks = [
  { name: "Host", color: "#ffb84d", phase: 0.3 },
  { name: "Guest", color: "#78a8ff", phase: 1.9 },
  { name: "Remote", color: "#b08cff", phase: 3.2 },
];

function samples(count: number, phase: number, reduction = 0) {
  return Array.from({ length: count }, (_, index) => {
    const x = index / (count - 1);
    const envelope = 0.3 + Math.abs(Math.sin(x * 17 + phase)) * 0.42;
    const detail = Math.abs(Math.sin(x * 63 + phase * 2.7)) * 0.22;
    return Math.min(0.94, (envelope + detail) * (1 - reduction * (0.25 + 0.7 * Math.abs(Math.sin(x * 9)))));
  });
}

function area(values: number[], height = 100) {
  const top = values.map((v, i) => `${i ? "L" : "M"}${(i / (values.length - 1)) * 100},${height / 2 - v * height * 0.43}`).join(" ");
  const bottom = [...values].reverse().map((v, i) => `L${((values.length - i - 1) / (values.length - 1)) * 100},${height / 2 + v * height * 0.43}`).join(" ");
  return `${top} ${bottom} Z`;
}

function attenuation(phase: number) {
  return Array.from({ length: 72 }, (_, i) => {
    const x = i / 71;
    const speech = Math.max(0, Math.sin(x * 13 + phase));
    const overlap = Math.max(0, Math.sin(x * 31 + phase * 1.7));
    return -(speech * 14 + overlap * 8);
  });
}

function reductionArea(values: number[]) {
  const line = values.map((v, i) => `${i ? "L" : "M"}${(i / (values.length - 1)) * 100},${Math.abs(v) / 24 * 100}`).join(" ");
  return `M0,0 ${line} L100,0 Z`;
}

function Waveform({ program, position, onSeek, compact = false }: { program: Program; position: number; onSeek: (n: number) => void; compact?: boolean }) {
  const original = useMemo(() => samples(150, 0.6), []);
  const mixed = useMemo(() => samples(150, 0.6, 0.28), []);
  const difference = original.map((v, i) => Math.abs(v - mixed[i]) * 2.5);
  return <div className={`proto-waveform ${compact ? "compact" : ""}`} onPointerDown={(event) => onSeek(event.nativeEvent.offsetX / event.currentTarget.clientWidth * duration)}>
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label={`${program} comparison waveform`}>
      {program === "difference" ? <path className="difference" d={area(difference)} /> : <>
        <path className={`original ${program === "original" ? "active" : ""}`} d={area(original)} />
        <path className={`automixed ${program === "automixed" ? "active" : ""}`} d={area(mixed)} />
      </>}
    </svg>
    <span className="played" style={{ width: `${position / duration * 100}%` }} />
    <i className="proto-playhead" style={{ left: `${position / duration * 100}%` }} />
    <b className="time-readout">{clock(position)} / 1:00</b>
  </div>;
}

function GainLanes({ position, dense = false }: { position: number; dense?: boolean }) {
  return <div className={`gain-lanes ${dense ? "dense" : ""}`}>
    <div className="gain-scale"><span>0</span><span>−12</span><span>−24 dB</span></div>
    {tracks.map((track) => {
      const values = attenuation(track.phase);
      const current = values[Math.min(values.length - 1, Math.floor(position / duration * values.length))];
      return <div className="gain-lane" key={track.name}>
        <header><strong><i style={{ background: track.color }} />{track.name}</strong><span>{current.toFixed(1)} dB</span></header>
        <div className="gain-plot">
          <svg viewBox="0 0 100 100" preserveAspectRatio="none"><path d={reductionArea(values)} style={{ fill: track.color }} /></svg>
          <i className="proto-playhead" style={{ left: `${position / duration * 100}%` }} />
        </div>
      </div>;
    })}
  </div>;
}

function Programs({ value, onChange }: { value: Program; onChange: (p: Program) => void }) {
  return <div className="proto-programs" role="group" aria-label="Comparison program">
    {(["original", "automixed", "difference"] as Program[]).map((item, index) => <button key={item} className={value === item ? "active" : ""} onClick={() => onChange(item)}><kbd>{["O", "A", "D"][index]}</kbd>{item[0].toUpperCase() + item.slice(1)}</button>)}
  </div>;
}

function Transport({ playing, loop, onPlay, onLoop }: { playing: boolean; loop: boolean; onPlay: () => void; onLoop: () => void }) {
  return <div className="proto-transport">
    <button className="play" onClick={onPlay} aria-label={playing ? "Pause" : "Play"}>{playing ? <Pause /> : <Play />}</button>
    <button className={loop ? "active" : ""} onClick={onLoop}><Repeat2 /> Loop <kbd>L</kbd></button>
    <span>Space play/pause · ←/→ seek · O/A/D switch</span>
  </div>;
}

function VariantA(props: SharedProps) {
  return <section className="comparison-prototype variant-a">
    <header className="proto-heading"><div><small>COMPARISON PLAYBACK</small><h2>Hear the change. See where it happened.</h2><p>Original and Automixed stay locked to one protected playback clock.</p></div><span>Preview ready</span></header>
    <Programs value={props.program} onChange={props.setProgram} />
    <Waveform program={props.program} position={props.position} onSeek={props.setPosition} />
    <Transport {...props} />
    <div className="gain-heading"><div><small>WHAT THE AUTOMIX APPLIED</small><h3>Gain reduction by microphone</h3></div><span>Shared playhead · Shared dB scale</span></div>
    <GainLanes position={props.position} />
  </section>;
}

function VariantB(props: SharedProps) {
  const chart = (["A", "B", "C", "D"].includes(new URLSearchParams(location.search).get("chart") || "") ? new URLSearchParams(location.search).get("chart") : "A") as "A" | "B" | "C" | "D";
  const viewport = useDiagnosticViewport(duration, props.position, props.setPosition);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.target as HTMLElement).matches("input, textarea, [contenteditable=true]")) return;
      if (event.key === "0") viewport.fit();
      else if (event.key === "+" || event.key === "=") viewport.zoomAt(1.25);
      else if (event.key === "-") viewport.zoomAt(0.8);
    };
    addEventListener("keydown", key);
    return () => removeEventListener("keydown", key);
  }, [viewport.fit, viewport.zoomAt]);
  return <section className="comparison-prototype variant-b">
    <header className="proto-heading"><div><small>EDITORIAL TIMELINE</small><h2>One clock for listening and diagnosis.</h2></div><Programs value={props.program} onChange={props.setProgram} /></header>
    <div className="timeline-controls">
      <button onClick={viewport.fit}>Fit <kbd>0</kbd></button>
      <button aria-label="Zoom out" onClick={() => viewport.zoomAt(.8)}>−</button>
      <input aria-label="Timeline zoom" type="range" min={viewport.viewportWidth / duration} max={100} step="0.1" value={viewport.pixelsPerSecond} onChange={(event) => viewport.zoomAt(Number(event.currentTarget.value) / viewport.pixelsPerSecond)} />
      <button aria-label="Zoom in" onClick={() => viewport.zoomAt(1.25)}>+</button>
      <span>{viewport.pixelsPerSecond.toFixed(1)} px/s · {viewport.following ? "Following playhead" : "Free scroll"}</span>
    </div>
    <div
      className="timeline-viewport"
      ref={viewport.viewportRef}
      onScroll={viewport.onScroll}
      onWheel={(event) => { if (event.ctrlKey || !event.deltaX) { event.preventDefault(); viewport.zoomAt(event.deltaY < 0 ? 1.1 : .9, event.clientX); } }}
      data-scroll-left={Math.round(viewport.scrollLeft)}
    >
      <div
        className="timeline-content"
        style={{ width: viewport.contentWidth }}
        data-pixels-per-second={viewport.pixelsPerSecond}
        onPointerDown={(event) => { if (!(event.target as HTMLElement).closest("button, input")) viewport.seekAt(event.clientX); }}
      >
        <div className="timeline-ruler" onClick={(event) => viewport.seekAt(event.clientX)}><span>0:00</span><span>0:15</span><span>0:30</span><span>0:45</span><span>1:00</span></div>
        <Waveform program={props.program} position={props.position} onSeek={props.setPosition} compact />
        <TanStackGainPrototype kind={chart} playhead={props.position} onSeek={props.setPosition} />
        <i className="timeline-playhead" style={{ left: viewport.playheadPixel }} data-playhead-pixel={viewport.playheadPixel} />
      </div>
    </div>
    <Transport {...props} />
  </section>;
}

function VariantC(props: SharedProps) {
  return <section className="comparison-prototype variant-c">
    <header className="proto-heading"><div><small>METER BRIDGE</small><h2>Compare the mix at a glance.</h2></div><span className="live-dot">● MONITOR</span></header>
    <div className="bridge-grid"><div className="bridge-main">
      <Programs value={props.program} onChange={props.setProgram} />
      <Waveform program={props.program} position={props.position} onSeek={props.setPosition} />
      <Transport {...props} />
    </div><aside className="meters"><strong>Gain now</strong>{tracks.map((track) => <div key={track.name}><span>{track.name}</span><i><b style={{ height: `${45 + Math.abs(Math.sin(props.position / 7 + track.phase)) * 45}%`, background: track.color }} /></i></div>)}</aside></div>
    <GainLanes position={props.position} dense />
  </section>;
}

type SharedProps = { program: Program; setProgram: (p: Program) => void; position: number; setPosition: (n: number) => void; playing: boolean; loop: boolean; onPlay: () => void; onLoop: () => void };
const names: Record<Variant, string> = { A: "Studio stack", B: "Editorial timeline", C: "Meter bridge" };

export function ComparisonReviewPrototype() {
  const query = new URLSearchParams(location.search);
  const initial = (["A", "B", "C"].includes(query.get("variant") || "") ? query.get("variant") : "B") as Variant;
  const [variant, setVariant] = useState<Variant>(initial), [program, setProgram] = useState<Program>("original"), [position, setPosition] = useState(19), [playing, setPlaying] = useState(false), [loop, setLoop] = useState(false);
  const chooseVariant = (next: Variant) => { const url = new URL(location.href); url.searchParams.set("variant", next); history.replaceState({}, "", url); setVariant(next); };
  const cycle = (amount: number) => { const all: Variant[] = ["A", "B", "C"]; chooseVariant(all[(all.indexOf(variant) + amount + all.length) % all.length]); };
  useEffect(() => { if (!playing) return; const timer = window.setInterval(() => setPosition((old) => old >= duration ? (loop ? 0 : (setPlaying(false), duration)) : old + 0.1), 100); return () => clearInterval(timer); }, [playing, loop]);
  useEffect(() => { const key = (event: KeyboardEvent) => { const target = event.target as HTMLElement; if (target.matches("input, textarea, [contenteditable=true]")) return; if (event.key === " ") { event.preventDefault(); setPlaying((v) => !v); } else if (event.key.toLowerCase() === "o") setProgram("original"); else if (event.key.toLowerCase() === "a") setProgram("automixed"); else if (event.key.toLowerCase() === "d") setProgram("difference"); else if (event.key.toLowerCase() === "l") setLoop((v) => !v); else if (event.key === "ArrowLeft" && event.altKey) cycle(-1); else if (event.key === "ArrowRight" && event.altKey) cycle(1); else if (event.key === "ArrowLeft") setPosition((v) => Math.max(0, v - 1)); else if (event.key === "ArrowRight") setPosition((v) => Math.min(duration, v + 1)); }; addEventListener("keydown", key); return () => removeEventListener("keydown", key); }, [variant]);
  const props = { program, setProgram, position, setPosition, playing, loop, onPlay: () => setPlaying((v) => !v), onLoop: () => setLoop((v) => !v) };
  return <><div className="prototype-notice">PROTOTYPE · generated data</div>{variant === "A" ? <VariantA {...props} /> : variant === "B" ? <VariantB {...props} /> : <VariantC {...props} />}<nav className="prototype-switcher"><button onClick={() => cycle(-1)}>←</button><strong>{variant} — {names[variant]}</strong><button onClick={() => cycle(1)}>→</button></nav></>;
}

function clock(seconds: number) { return `${Math.floor(seconds / 60)}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`; }
