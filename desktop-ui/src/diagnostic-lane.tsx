import React from "react";
import { areaY, defineChart, lineY } from "@tanstack/charts";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { Chart } from "@tanstack/charts/react/tooltip";

export type DiagnosticFrame = {
  seconds: number;
  speech: boolean;
  target_open: boolean;
  gain_db: number;
  response: "open" | "closing" | "attenuated" | "opening";
};
export type DiagnosticTrack = { name: string; frames: DiagnosticFrame[] };

const responseText = {
  open: "At open target",
  closing: "Closing toward attenuation",
  attenuated: "At attenuation target",
  opening: "Opening toward 0 dB",
};

export function DiagnosticLane({ track, playhead }: { track: DiagnosticTrack; playhead: number }) {
  const current = track.frames.reduce(
    (best, frame) => Math.abs(frame.seconds - playhead) < Math.abs(best.seconds - playhead) ? frame : best,
    track.frames[0],
  );
  const minimum = Math.min(-1, ...track.frames.map((frame) => frame.gain_db));
  const definition = React.useMemo(() => defineChart({
    marks: [
      areaY(track.frames, { x: "seconds", y1: "gain_db", y2: () => 0, fill: "#60a5fa", fillOpacity: 0.38 }),
      lineY(track.frames, { x: "seconds", y: "gain_db", stroke: "#60a5fa", strokeWidth: 1.5 }),
    ],
    x: { scale: scaleLinear([0, track.frames.at(-1)?.seconds || 1], [0, 1]), axis: false },
    y: { scale: scaleLinear([minimum, 0], [0, 1]), axis: false },
    clip: true,
  }), [minimum, track]);
  if (!current) return null;
  return <section className={`diagnostic-lane ${current.target_open ? "is-open" : ""}`} aria-label={`${track.name} automix explanation`}>
    <header><strong>{track.name}</strong><span className={current.target_open ? "open-state" : ""}>{current.target_open ? "OPEN" : "ATTENUATE"}</span><b>{current.gain_db.toFixed(1)} dB</b></header>
    <div className="diagnostic-content">
      <div className="diagnostic-strips">
        <span>SPEECH</span><div>{track.frames.map((frame, index) => <i key={`s-${index}`} className={frame.speech ? "speech-on" : ""} />)}</div>
        <span>TARGET</span><div>{track.frames.map((frame, index) => <i key={`t-${index}`} className={frame.target_open ? "target-open" : ""} />)}</div>
      </div>
      <div className="diagnostic-chart"><Chart definition={definition} height={120} ariaLabel={`${track.name} applied gain in decibels`} /><i className="diagnostic-playhead" style={{ left: `${(playhead / (track.frames.at(-1)?.seconds || 1)) * 100}%` }} /></div>
    </div>
    <p className="diagnostic-summary" aria-live="polite">{current.speech ? "Speaking" : "Silent"} · {current.target_open ? "Open target" : "Attenuate target"} · {current.gain_db.toFixed(1)} dB · {responseText[current.response]}</p>
  </section>;
}
