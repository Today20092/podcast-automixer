// PROTOTYPE — TanStack Charts attenuation encodings, selected with ?chart=A|B|C.
import React from "react";
import { areaY, defineChart, lineY, rect, ruleY } from "@tanstack/charts";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { tooltip } from "@tanstack/charts/tooltip";
import { Chart } from "@tanstack/charts/react/tooltip";

interface GainDatum { id: string; track: string; seconds: number; gain: number; zero: number; color: string }
interface HeatDatum { id: string; track: string; start: number; end: number; top: number; bottom: number; gain: number; color: string }
const trackInfo = [{ name: "Host", color: "#ffb84d", phase: .3 }, { name: "Guest", color: "#78a8ff", phase: 1.9 }, { name: "Remote", color: "#b08cff", phase: 3.2 }];
const diagnosticTracks = [...trackInfo, { name: "Producer", color: "#5fd6a8", phase: 4.4 }, { name: "Panelist", color: "#ff7c91", phase: 5.7 }, { name: "Room", color: "#63d0e8", phase: 6.8 }];
const gainAt = (seconds: number, phase: number) => -(Math.max(0, Math.sin(seconds / 4.7 + phase)) * 14 + Math.max(0, Math.sin(seconds / 2.05 + phase * 1.7)) * 8);
const rows: GainDatum[] = trackInfo.flatMap(track => Array.from({ length: 61 }, (_, seconds) => ({ id: `${track.name}-${seconds}`, track: track.name, seconds, gain: gainAt(seconds, track.phase), zero: 0, color: track.color })));
const heatRows: HeatDatum[] = trackInfo.flatMap((track, trackIndex) => Array.from({ length: 30 }, (_, index) => { const gain = gainAt(index * 2 + 1, track.phase); return { id: `${track.name}-${index}`, track: track.name, start: index * 2, end: index * 2 + 2, top: trackIndex + .1, bottom: trackIndex + .9, gain, color: gain > -4 ? "#252832" : gain > -10 ? track.color + "66" : gain > -17 ? track.color + "aa" : track.color }; }));
const xScale = scaleLinear([0, 60], [0, 1]);
const yScale = scaleLinear([-24, 0], [0, 1]);
const commonTooltip = { ...tooltip, items: [{ id: "track", label: "Microphone", text: (p: { datum: GainDatum | HeatDatum }) => p.datum.track }, { id: "time", label: "Time", text: (p: { datum: GainDatum | HeatDatum }) => `${"seconds" in p.datum ? p.datum.seconds : p.datum.start}s` }, { id: "gain", label: "Attenuation", text: (p: { datum: GainDatum | HeatDatum }) => `${p.datum.gain.toFixed(1)} dB` }] };

function AreaLane({ track, playhead }: { track: typeof trackInfo[number]; playhead: number }) {
  const data = React.useMemo(() => rows.filter(row => row.track === track.name), [track.name]);
  const definition = React.useMemo(() => defineChart({ marks: [areaY(data, { id: `${track.name}-area`, x: "seconds", y1: "gain", y2: "zero", fill: track.color, fillOpacity: .62 }), lineY(data, { id: `${track.name}-edge`, x: "seconds", y: "gain", stroke: track.color, strokeWidth: 1.5 }), ruleY([0], { stroke: "#ffffff33" })], x: { scale: xScale, nice: false, grid: true, axis: { label: "Preview time (seconds)" } }, y: { scale: yScale, nice: false, grid: true, axis: { label: "Applied gain (dB)" } }, focus: "group-x", tooltip: commonTooltip, clip: true }), [data, track]);
  return <article className="ts-lane"><header><strong><i style={{ background: track.color }} />{track.name}</strong><span>0 to −24 dB</span></header><div className="ts-chart-wrap"><Chart<GainDatum, number, number> definition={definition} height={155} ariaLabel={`${track.name} gain reduction over preview time`} /><i className="chart-playhead" style={{ left: `${playhead / 60 * 100}%` }} /></div></article>;
}
function SmallMultiples({ playhead }: { playhead: number }) { return <div className="ts-small-multiples">{trackInfo.map(track => <AreaLane key={track.name} track={track} playhead={playhead} />)}</div>; }
function Overlay({ playhead }: { playhead: number }) {
  const definition = React.useMemo(() => defineChart({ marks: [ruleY([0], { stroke: "#ffffff44" }), lineY(rows, { id: "gain-overlay", x: "seconds", y: "gain", z: "track", key: "id", stroke: row => row.color, strokeWidth: 2.4 })], x: { scale: xScale, nice: false, grid: true, axis: { label: "Preview time (seconds)" } }, y: { scale: yScale, nice: false, grid: true, axis: { label: "Applied gain (dB)" } }, focus: "group-x", tooltip: commonTooltip, clip: true }), []);
  return <div className="ts-overlay"><div className="ts-legend">{trackInfo.map(track => <span key={track.name}><i style={{ background: track.color }} />{track.name}</span>)}</div><div className="ts-chart-wrap"><Chart<GainDatum, number, number> definition={definition} height={420} ariaLabel="Overlaid gain reduction for all microphones" /><i className="chart-playhead" style={{ left: `${playhead / 60 * 100}%` }} /></div></div>;
}
function Heatmap({ playhead }: { playhead: number }) {
  const definition = React.useMemo(() => {
    const colors = [...new Set(heatRows.map(row => row.color))];
    return defineChart({ marks: colors.map((color, index) => rect(heatRows.filter(row => row.color === color), { id: `attenuation-heatmap-${index}`, x1: row => row.start, x2: row => row.end, y1: row => row.top, y2: row => row.bottom, fill: color, inset: .8 })), x: { scale: xScale, nice: false, grid: false, axis: { label: "Preview time (seconds)" } }, y: { scale: scaleLinear([0, 3], [0, 1]), nice: false, axis: false }, focus: "group-x", tooltip: commonTooltip, clip: true });
  }, []);
  return <div className="ts-heatmap"><div className="heat-labels">{trackInfo.map(track => <strong key={track.name}>{track.name}</strong>)}</div><div className="ts-chart-wrap"><Chart<HeatDatum, number, number> definition={definition} height={280} ariaLabel="Attenuation intensity heatmap by microphone and time" /><i className="chart-playhead" style={{ left: `${playhead / 60 * 100}%` }} /></div><div className="heat-key"><span>Little reduction</span><i /><i /><i /><span>Heavy reduction</span></div></div>;
}

const isActive = (seconds: number, phase: number) => Math.sin(seconds / 5.2 + phase) > .25 || Math.sin(seconds / 2.7 + phase * 1.3) > .78;
function diagnosticSignal(track: typeof diagnosticTracks[number]) {
  let gain = -18;
  return Array.from({ length: 61 }, (_, seconds) => {
    const speech = isActive(seconds, track.phase);
    const targetOpen = speech || (seconds > 0 && isActive(seconds - 1, track.phase));
    const target = targetOpen ? 0 : -18;
    gain += (target - gain) * (targetOpen ? .62 : .28);
    return { id: `${track.name}-${seconds}`, track: track.name, seconds, gain, zero: 0, color: track.color, speech, targetOpen, target };
  });
}
function responseLabel(point: ReturnType<typeof diagnosticSignal>[number]) {
  if (Math.abs(point.gain - point.target) < .8) return point.targetOpen ? "At open target" : "At attenuation target";
  return point.targetOpen ? "Opening toward 0 dB" : "Closing toward −18 dB";
}
function DiagnosticLane({ track, playhead, solo, onSolo }: { track: typeof diagnosticTracks[number]; playhead: number; solo: string; onSolo: (name: string) => void }) {
  const signal = React.useMemo(() => diagnosticSignal(track), [track]);
  const data: GainDatum[] = signal;
  const definition = React.useMemo(() => defineChart({ marks: [areaY(data, { x: "seconds", y1: "gain", y2: "zero", fill: track.color, fillOpacity: .42 }), lineY(data, { x: "seconds", y: "gain", stroke: track.color, strokeWidth: 1.4 })], x: { scale: xScale, axis: false }, y: { scale: yScale, axis: false }, focus: "group-x", tooltip: commonTooltip, clip: true }), [data, track]);
  const windows = Array.from({ length: 30 }, (_, index) => signal[Math.min(60, index * 2 + 1)]);
  const now = signal[Math.min(60, Math.max(0, Math.round(playhead)))];
  return <article className={`diagnostic-lane ${now.targetOpen ? "is-active" : "is-attenuated"}`}>
    <header><i style={{ background: track.color }} /><strong>{track.name}</strong><button className={solo === track.name ? "active" : ""} onClick={() => onSolo(solo === track.name ? "" : track.name)}>S</button><span className={`state ${now.targetOpen ? "open" : "closed"}`}>{now.targetOpen ? "OPEN" : "ATTENUATE"}</span><b>{now.gain.toFixed(1)} dB</b></header>
    <div className="diagnostic-plot">
      <span className="strip-label speech-label">SPEECH</span><div className="speech-evidence" aria-label={`${track.name} detected speech activity`}>{windows.map((point, index) => <i key={index} className={point.speech ? "speaking" : "silent"} style={{ background: point.speech ? track.color : undefined }} />)}</div>
      <span className="strip-label target-label">TARGET</span><div className="target-strip">{windows.map((point, index) => <i key={index} className={point.targetOpen ? "open" : "attenuate"} title={point.targetOpen ? "Target: open" : "Target: attenuate"} />)}</div>
      <Chart<GainDatum, number, number> definition={definition} height={84} ariaLabel={`${track.name}: detected activity, target state, and applied gain`} />
      <i className="chart-playhead" style={{ left: `${playhead / 60 * 100}%` }} />
    </div>
  </article>;
}
function DiagnosticTimeline({ playhead, onSeek }: { playhead: number; onSeek: (seconds: number) => void }) {
  const [solo, setSolo] = React.useState("");
  const alerts = [{ time: 17, label: "Guest speaking while closing" }, { time: 33, label: "Multiple microphones open" }, { time: 47, label: "No clear owner" }];
  return <div className="diagnostic-timeline">
    <div className="diagnostic-key"><span><i className="speech" />Detected speech</span><span><i className="open" />Target open</span><span><i className="closed" />Target attenuate</span><span><i className="curve" />Actual gain</span></div>
    <div className="diagnostic-layout"><div className="diagnostic-tracks">{diagnosticTracks.map(track => <DiagnosticLane key={track.name} track={track} playhead={playhead} solo={solo} onSolo={setSolo} />)}</div>
      <aside className="playhead-inspector"><small>AT {Math.floor(playhead / 60)}:{Math.floor(playhead % 60).toString().padStart(2, "0")}</small><h4>Playhead inspector</h4>{diagnosticTracks.map(track => { const point = diagnosticSignal(track)[Math.min(60, Math.max(0, Math.round(playhead)))]; return <div key={track.name}><i style={{ background: track.color }} /><strong>{track.name}</strong><span>{point.speech ? "Speaking" : "Silent"} · {point.targetOpen ? "Open target" : "Attenuate target"}</span><b>{point.gain.toFixed(1)} dB</b><em>{responseLabel(point)}</em></div>; })}<p>{solo ? `Solo monitoring: ${solo}` : "Combined monitor output"}</p></aside></div>
    <div className="review-flags"><strong>Review moments</strong>{alerts.map(alert => <button key={alert.time} onClick={() => onSeek(alert.time)}><span>{alert.time}s</span>{alert.label}</button>)}</div>
  </div>;
}
export function TanStackGainPrototype({ kind, playhead, onSeek }: { kind: "A" | "B" | "C" | "D"; playhead: number; onSeek: (seconds: number) => void }) { const title = { A: "Filled small multiples", B: "Overlaid gain traces", C: "Attenuation heatmap", D: "Decision + response timeline" }[kind]; return <section className="tanstack-prototype"><header><div><small>TANSTACK CHARTS PROTOTYPE</small><h3>{title}</h3></div><p>{kind === "A" ? "Best per-track precision" : kind === "B" ? "Best direct comparison" : kind === "C" ? "Best whole-session scan" : "Verify the right mic at the right time"}</p></header>{kind === "A" ? <SmallMultiples playhead={playhead} /> : kind === "B" ? <Overlay playhead={playhead} /> : kind === "C" ? <Heatmap playhead={playhead} /> : <DiagnosticTimeline playhead={playhead} onSeek={onSeek} />}</section>; }
