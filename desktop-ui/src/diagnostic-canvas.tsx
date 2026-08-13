import React, { useEffect, useRef, useState } from "react";

type Lane = {
  recording_identity: string; name: string; color: string;
  waveform_levels: [number, number][][]; gain_adjusted_waveform_levels: [number, number][][];
  speech_evidence: boolean[]; automix_target: boolean[]; applied_gain_db: number[];
  evidence_gaps: { start_seconds: number; end_seconds: number }[];
};
export type DiagnosticTimeline = {
  duration_seconds: number; db_domain: { minimum: number; maximum: number };
  lanes: Lane[]; frame_ms: number;
};

export function chooseEnvelopeLevel(levels: [number, number][][], pixels: number) {
  return levels.reduce((best, level) => Math.abs(level.length - pixels) < Math.abs(best.length - pixels) ? level : best);
}

function LaneCanvas({ lane, timeline, width, start, end, revision }: { lane: Lane; timeline: DiagnosticTimeline; width: number; start: number; end: number; revision: string }) {
  const ref = useRef<HTMLCanvasElement>(null), signature = useRef("");
  useEffect(() => {
    const canvas = ref.current, ratio = devicePixelRatio || 1, height = 230;
    const next = `${start}:${end}:${width}:${revision}:${ratio}:${document.documentElement.className}`;
    if (!canvas || signature.current === next) return;
    signature.current = next; canvas.width = width * ratio; canvas.height = height * ratio;
    const context = canvas.getContext("2d"); if (!context) return;
    context.scale(ratio, ratio); context.clearRect(0, 0, width, height);
    const overscan = (end - start) * .1, from = Math.max(0, start - overscan), to = Math.min(1, end + overscan);
    const drawEnvelope = (levels: [number, number][][], color: string) => {
      const level = chooseEnvelopeLevel(levels, width * (to - from));
      const first = Math.floor(from * level.length), last = Math.min(level.length, Math.ceil(to * level.length));
      context.fillStyle = color; context.beginPath();
      for (let index = first; index < last; index++) context.lineTo((index / level.length - start) / (end - start) * width, 58 + level[index][0] * 42);
      for (let index = last - 1; index >= first; index--) context.lineTo((index / level.length - start) / (end - start) * width, 58 + level[index][1] * 42);
      context.fill();
    };
    drawEnvelope(lane.waveform_levels, `${lane.color}55`); drawEnvelope(lane.gain_adjusted_waveform_levels, `${lane.color}bb`);
    const binary = (values: boolean[], y: number, color: string) => {
      context.fillStyle = color; const first = Math.floor(from * values.length), last = Math.ceil(to * values.length);
      for (let index = first; index < last; index++) if (values[index]) context.fillRect((index / values.length - start) / (end - start) * width, y, Math.max(1, width / values.length / (end - start)), 10);
    };
    binary(lane.speech_evidence, 120, "#60a5fa"); binary(lane.automix_target, 143, "#34d399");
    context.strokeStyle = lane.color; context.beginPath();
    const gains = lane.applied_gain_db, first = Math.floor(from * gains.length), last = Math.ceil(to * gains.length);
    for (let index = first; index < last; index++) {
      const x = (index / Math.max(1, gains.length - 1) - start) / (end - start) * width;
      const y = 170 + (timeline.db_domain.maximum - gains[index]) / (timeline.db_domain.maximum - timeline.db_domain.minimum) * 50;
      context.lineTo(x, y);
    }
    context.stroke();
  }, [lane, timeline, width, start, end, revision]);
  return <canvas ref={ref} aria-label={`${lane.name}: Input Waveform, Gain-Adjusted Waveform, Speech Evidence, Automix Target, and Applied Gain`} />;
}

export function DiagnosticCanvas({ timeline, playheadSeconds = 0, onSeek }: { timeline: DiagnosticTimeline; playheadSeconds?: number; onSeek?: (seconds: number) => void }) {
  const viewport = useRef<HTMLDivElement>(null), [width, setWidth] = useState(800), [zoom, setZoom] = useState(1), [scroll, setScroll] = useState(0);
  const playhead = useRef<HTMLDivElement>(null), drag = useRef(false), wasPlaying = useRef(false);
  useEffect(() => {
    const element = playhead.current;
    if (!element) return;
    const percent = timeline.duration_seconds ? playheadSeconds / timeline.duration_seconds * 100 : 0;
    requestAnimationFrame(() => { element.style.transform = `translateX(${percent}%)`; });
  }, [playheadSeconds, timeline.duration_seconds]);
  useEffect(() => { const element = viewport.current; if (!element) return; const resize = () => setWidth(element.clientWidth || 1); resize(); const observer = new ResizeObserver(resize); observer.observe(element); return () => observer.disconnect(); }, []);
  const contentWidth = width * zoom, start = scroll / contentWidth, end = Math.min(1, (scroll + width) / contentWidth);
  const frame = Math.min(Math.max(0, Math.floor(playheadSeconds * 1000 / timeline.frame_ms)), Math.max(0, (timeline.lanes[0]?.applied_gain_db.length || 1) - 1));
  return <section className="diagnostic-timeline" aria-label="Diagnostic Timeline">
    <header><strong>Recording Set diagnosis</strong><span>Shared Applied Gain {timeline.db_domain.maximum} to {timeline.db_domain.minimum} dB</span></header>
    <div className="diagnostic-controls"><button onClick={() => { setZoom(1); viewport.current?.scrollTo({ left: 0 }); }}>Fit</button><button aria-label="Zoom out" onClick={() => setZoom(value => Math.max(1, value / 1.5))}>−</button><button aria-label="Zoom in" onClick={() => setZoom(value => Math.min(100, value * 1.5))}>+</button></div>
    <aside className="diagnostic-inspector" aria-label="Pinned inspector"><b>{playheadSeconds.toFixed(1)}s</b>{timeline.lanes.map(lane => <span key={lane.recording_identity}><i style={{ background: lane.color }} />{lane.name}: speech {lane.speech_evidence[frame] ? "yes" : "no"}, target {lane.automix_target[frame] ? "open" : "attenuated"}, gain {lane.applied_gain_db[frame]?.toFixed(1)} dB, {lane.applied_gain_db[frame] > timeline.db_domain.minimum + .5 ? "responding" : "settled"}</span>)}</aside>
    <div className="diagnostic-viewport" ref={viewport} onScroll={event => setScroll(event.currentTarget.scrollLeft)} onPointerDown={event => { drag.current = true; wasPlaying.current = false; (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId); onSeek?.(Math.max(0, Math.min(timeline.duration_seconds, (event.clientX - event.currentTarget.getBoundingClientRect().left + scroll) / contentWidth * timeline.duration_seconds))); }} onPointerMove={event => { if (!drag.current) return; onSeek?.(Math.max(0, Math.min(timeline.duration_seconds, (event.clientX - event.currentTarget.getBoundingClientRect().left + scroll) / contentWidth * timeline.duration_seconds))); }} onPointerUp={event => { drag.current = false; (event.currentTarget as HTMLElement).releasePointerCapture(event.pointerId); }} onKeyDown={event => { if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); onSeek?.(Math.max(0, Math.min(timeline.duration_seconds, playheadSeconds + (event.key === "ArrowRight" ? 1 : -1)))); } }} tabIndex={0}>
      <div style={{ width: contentWidth, position: "relative" }}>
        <div ref={playhead} className="diagnostic-playhead" aria-label="Shared playhead" />
        {timeline.lanes.map(lane => <article className={`diagnostic-lane ${lane.automix_target[frame] ? "is-open" : ""}`} key={lane.recording_identity}><header><strong><i style={{ background: lane.color }} />{lane.name}</strong></header><div className="diagnostic-sticky" style={{ width }}><LaneCanvas lane={lane} timeline={timeline} width={width} start={start} end={end} revision={`${lane.applied_gain_db.length}:${zoom}`} /></div></article>)}
      </div>
    </div>
  </section>;
}
