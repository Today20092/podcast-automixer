import React, { useEffect, useRef } from "react";

export type DiagnosticTimeline = {
  duration_seconds: number;
  db_domain: { minimum: number; maximum: number };
  waveform_levels: [number, number][][];
  gain_adjusted_waveform_levels: [number, number][][];
  speech_evidence: boolean[];
  automix_target: boolean[];
  applied_gain_db: number[];
  frame_ms: number;
  evidence_gaps: { start_seconds: number; end_seconds: number }[];
};

export function chooseEnvelopeLevel(levels: [number, number][][], pixels: number) {
  return levels.reduce((best, level) =>
    Math.abs(level.length - pixels) < Math.abs(best.length - pixels) ? level : best);
}

export function DiagnosticCanvas({ timeline }: { timeline: DiagnosticTimeline }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ratio = devicePixelRatio || 1, width = canvas.clientWidth, height = 230;
    canvas.width = width * ratio; canvas.height = height * ratio;
    const context = canvas.getContext("2d"); if (!context) return;
    context.scale(ratio, ratio); context.clearRect(0, 0, width, height);
    const drawEnvelope = (level: [number, number][], color: string, scale = 1) => {
      context.fillStyle = color; context.beginPath();
      level.forEach(([minimum], index) => context.lineTo(index / level.length * width, 75 + minimum * 55 * scale));
      [...level].reverse().forEach(([, maximum], index) => context.lineTo((level.length - index) / level.length * width, 75 + maximum * 55 * scale));
      context.fill();
    };
    drawEnvelope(chooseEnvelopeLevel(timeline.waveform_levels, width), "#9ca3af44");
    drawEnvelope(chooseEnvelopeLevel(timeline.gain_adjusted_waveform_levels, width), "#f5b84dcc");
    const binary = (values: boolean[], y: number, color: string) => {
      context.fillStyle = color;
      values.forEach((value, index) => { if (value) context.fillRect(index / values.length * width, y, Math.max(1, width / values.length), 8); });
    };
    binary(timeline.speech_evidence, 136, "#60a5fa"); binary(timeline.automix_target, 150, "#34d399");
    context.strokeStyle = "#f5b84d"; context.beginPath();
    timeline.applied_gain_db.forEach((gain, index) => context.lineTo(index / Math.max(1, timeline.applied_gain_db.length - 1) * width, 168 + Math.min(60, Math.abs(gain) / 60 * 55)));
    context.stroke();
    timeline.evidence_gaps.forEach((gap) => {
      const x = gap.start_seconds / timeline.duration_seconds * width, w = Math.max(1, (gap.end_seconds - gap.start_seconds) / timeline.duration_seconds * width);
      context.save(); context.beginPath(); context.rect(x, 0, w, height); context.clip(); context.strokeStyle = "#ffffff33";
      for (let line = x - height; line < x + w; line += 8) { context.beginPath(); context.moveTo(line, height); context.lineTo(line + height, 0); context.stroke(); }
      context.restore();
      context.fillStyle = "#ddd"; context.fillText("Evidence Gap", x + 3, 14);
    });
  }, [timeline]);
  return <canvas ref={ref} className="diagnostic-canvas" aria-label="Input Waveform, gain-adjusted waveform, Speech Evidence, Automix Target, and Applied Gain" />;
}
