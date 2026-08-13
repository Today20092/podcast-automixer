import React from "react";
import { areaY, defineChart, lineY } from "@tanstack/charts";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { Chart } from "@tanstack/charts/react/tooltip";

export type DiagnosticFrame = {
  seconds: number; speech: boolean; target_open: boolean; gain_db: number;
  response: "open" | "closing" | "attenuated" | "opening";
};
export type DiagnosticTrack = { id?: string; name: string; color?: string; frames: DiagnosticFrame[] };
export type DiagnosticDomains = { duration: number; minimumDb: number };

const fallbackColors = ["#3b82f6", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"];
export const responseText = { open: "At open target", closing: "Closing", attenuated: "At attenuation target", opening: "Opening" };

export function frameAt(track: DiagnosticTrack, playhead: number) {
  return track.frames.reduce<DiagnosticFrame | undefined>((best, frame) =>
    !best || Math.abs(frame.seconds - playhead) < Math.abs(best.seconds - playhead) ? frame : best, undefined);
}

export function diagnosticDomains(tracks: DiagnosticTrack[]): DiagnosticDomains {
  const frames = tracks.flatMap((track) => track.frames);
  return {
    duration: Math.max(1, ...frames.map((frame) => frame.seconds)),
    minimumDb: Math.min(-1, ...frames.map((frame) => frame.gain_db)),
  };
}

export function DiagnosticLane({ track, playhead, domains, index = 0 }: { track: DiagnosticTrack; playhead: number; domains: DiagnosticDomains; index?: number }) {
  const current = frameAt(track, playhead);
  const color = track.color || fallbackColors[index % fallbackColors.length];
  const definition = React.useMemo(() => defineChart({
    marks: [
      areaY(track.frames, { x: "seconds", y1: "gain_db", y2: () => 0, fill: color, fillOpacity: 0.38 }),
      lineY(track.frames, { x: "seconds", y: "gain_db", stroke: color, strokeWidth: 1.5 }),
    ],
    x: { scale: scaleLinear([0, domains.duration], [0, 1]), axis: false },
    y: { scale: scaleLinear([domains.minimumDb, 0], [0, 1]), axis: false },
    clip: true,
  }), [color, domains, track.frames]);
  if (!current) return null;
  const facts = `${current.speech ? "Speaking" : "Silent"} · ${current.target_open ? "Open target" : "Attenuate target"} · ${current.gain_db.toFixed(1)} dB · ${responseText[current.response]}`;
  return <section className={`diagnostic-lane ${current.target_open ? "is-open" : ""}`} style={{ "--track-color": color } as React.CSSProperties} aria-label={`${track.name} automix explanation`}>
    <header><strong><i className="track-swatch" />{track.name}</strong><span className={current.target_open ? "open-state" : ""}>{current.target_open ? "OPEN" : "ATTENUATE"}</span><b>{current.gain_db.toFixed(1)} dB</b></header>
    <div className="diagnostic-content">
      <div className="diagnostic-strips">
        <span>SPEECH</span><div aria-label={`${track.name} detected speech timeline`}>{track.frames.map((frame, frameIndex) => <i key={`s-${frameIndex}`} className={frame.speech ? "speech-on" : ""} title={frame.speech ? "Speech detected" : "No speech"} />)}</div>
        <span>TARGET</span><div aria-label={`${track.name} Automix target timeline`}>{track.frames.map((frame, frameIndex) => <i key={`t-${frameIndex}`} className={frame.target_open ? "target-open" : ""} title={frame.target_open ? "Open target" : "Attenuate target"} />)}</div>
      </div>
      <div className="diagnostic-chart" data-domain={`${domains.minimumDb.toFixed(0)} to 0 dB; 0 to ${domains.duration}s`}><Chart definition={definition} height={120} ariaLabel={`${track.name} applied gain in decibels`} /><i className="diagnostic-playhead" style={{ left: `${Math.min(100, Math.max(0, playhead / domains.duration * 100))}%` }} /></div>
    </div>
    <p className="diagnostic-summary" aria-live="polite">{facts}</p>
  </section>;
}

export function RecordingSetDiagnostics({ tracks, playhead }: { tracks: DiagnosticTrack[]; playhead: number }) {
  if (!tracks.length) return <div className="diagnostics-empty" role="status">No microphone diagnostics are available for this Preview Run.</div>;
  const domains = diagnosticDomains(tracks);
  return <div className="diagnostics-scroll" tabIndex={0} aria-label="Recording Set diagnostic timeline; scroll horizontally at constrained widths">
    <div className="diagnostics-timeline">
      {tracks.map((track, index) => <DiagnosticLane key={track.id || `${track.name}-${index}`} track={track} playhead={playhead} domains={domains} index={index} />)}
      <section className="playhead-inspector" aria-label="Playhead Inspector">
        <h3>Playhead Inspector <span>{playhead.toFixed(1)}s</span></h3>
        <div>{tracks.map((track, index) => { const frame = frameAt(track, playhead); if (!frame) return null; return <p key={track.id || `${track.name}-${index}`}><strong>{track.name}</strong><span>{frame.speech ? "Speaking" : "Silent"}</span><span>{frame.target_open ? "Open" : "Attenuate"}</span><span>{frame.gain_db.toFixed(1)} dB</span><span>{responseText[frame.response]}</span></p>; })}</div>
      </section>
    </div>
  </div>;
}
