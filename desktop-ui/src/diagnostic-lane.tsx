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
export type ReviewKind = "speaking-attenuated" | "silent-open" | "rapid-switch" | "multiple-active" | "no-clear-owner";
export type ReviewMoment = { seconds: number; kind: ReviewKind; label: string; trackIds: string[]; flagged: boolean };

const fallbackColors = ["#ffb84d", "#6fa5ff", "#a981ff", "#5dd8aa", "#ff718b", "#58cee5", "#ec4899", "#84cc16"];
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

const reviewLabels: Record<ReviewKind, string> = {
  "speaking-attenuated": "Speaking while attenuated",
  "silent-open": "Silent while open",
  "rapid-switch": "Rapid switching",
  "multiple-active": "Multiple active",
  "no-clear-owner": "No clear owner",
};

export function reviewMoments(tracks: DiagnosticTrack[]): ReviewMoment[] {
  const moments: ReviewMoment[] = [];
  const seen = new Set<string>();
  const add = (seconds: number, kind: ReviewKind, trackIds: string[], flagged: boolean) => {
    const key = `${kind}-${seconds.toFixed(3)}-${trackIds.join("|")}`;
    if (!seen.has(key)) { seen.add(key); moments.push({ seconds, kind, label: reviewLabels[kind], trackIds, flagged }); }
  };
  tracks.forEach((track, trackIndex) => track.frames.forEach((frame, frameIndex) => {
    const id = track.id || track.name;
    if (frame.speech && !frame.target_open) add(frame.seconds, "speaking-attenuated", [id], true);
    if (!frame.speech && frame.target_open) add(frame.seconds, "silent-open", [id], true);
    const previous = track.frames[frameIndex - 1];
    if (previous && previous.target_open !== frame.target_open && frame.seconds - previous.seconds <= 1) add(frame.seconds, "rapid-switch", [id], true);
    if (trackIndex === 0) {
      const current = tracks.map((candidate) => ({ id: candidate.id || candidate.name, frame: frameAt(candidate, frame.seconds) })).filter((item) => item.frame);
      const active = current.filter((item) => item.frame?.target_open).map((item) => item.id);
      if (active.length > 1) add(frame.seconds, "multiple-active", active, false);
      if (active.length === 0) add(frame.seconds, "no-clear-owner", [], false);
    }
  }));
  return moments.sort((a, b) => a.seconds - b.seconds || a.label.localeCompare(b.label));
}

export function DiagnosticLane({ track, playhead, domains, index = 0, collapsed, soloed, onCollapse, onSolo }: { track: DiagnosticTrack; playhead: number; domains: DiagnosticDomains; index?: number; collapsed?: boolean; soloed?: boolean; onCollapse?: () => void; onSolo?: () => void }) {
  const current = frameAt(track, playhead);
  const color = track.color || fallbackColors[index % fallbackColors.length];
  const definition = React.useMemo(() => defineChart({
    marks: [
      areaY(track.frames, { x: "seconds", y1: "gain_db", y2: () => 0, fill: color, fillOpacity: 0.48 }),
      lineY(track.frames, { x: "seconds", y: "gain_db", stroke: color, strokeWidth: 1.5 }),
    ],
    x: { scale: scaleLinear([0, domains.duration], [0, 1]), axis: false },
    y: { scale: scaleLinear([domains.minimumDb, 0], [0, 1]), axis: false },
    clip: true,
  }), [color, domains, track.frames]);
  if (!current) return null;
  const facts = `${current.speech ? "Speaking" : "Silent"} · ${current.target_open ? "Open target" : "Attenuate target"} · ${current.gain_db.toFixed(1)} dB · ${responseText[current.response]}`;
  return <section className={`diagnostic-lane ${current.target_open ? "is-open" : ""} ${collapsed ? "is-collapsed" : ""}`} style={{ "--track-color": color } as React.CSSProperties} aria-label={`${track.name} automix explanation`}>
    <header>
      <strong><i className="track-swatch" />{track.name}</strong>
      <button className="lane-solo" type="button" aria-pressed={soloed} aria-label={`${soloed ? "Stop soloing" : "Solo"} ${track.name}`} onClick={onSolo}>S</button>
      <span className={current.target_open ? "open-state" : ""}>{current.target_open ? "OPEN" : "ATTENUATE"}</span>
      <b>{current.gain_db.toFixed(1)} dB</b>
      <button className="lane-collapse" type="button" aria-expanded={!collapsed} aria-label={`${collapsed ? "Expand" : "Collapse"} ${track.name} lane`} onClick={onCollapse}>{collapsed ? "+" : "−"}</button>
    </header>
    {!collapsed && <div className="diagnostic-content">
      <div className="diagnostic-strips">
        <span>SPEECH</span><div aria-label={`${track.name} detected speech timeline`}>{track.frames.map((frame, frameIndex) => <i key={`s-${frameIndex}`} className={frame.speech ? "speech-on" : ""} title={frame.speech ? "Speech detected" : "No speech"} />)}</div>
        <span>TARGET</span><div aria-label={`${track.name} Automix target timeline`}>{track.frames.map((frame, frameIndex) => <i key={`t-${frameIndex}`} className={frame.target_open ? "target-open" : ""} title={frame.target_open ? "Open target" : "Attenuate target"} />)}</div>
      </div>
      <div className="diagnostic-chart" data-domain={`${domains.minimumDb.toFixed(0)} to 0 dB; 0 to ${domains.duration}s`}><Chart definition={definition} height={84} ariaLabel={`${track.name} applied gain in decibels`} /><i className="diagnostic-playhead" style={{ left: `${Math.min(100, Math.max(0, playhead / domains.duration * 100))}%` }} /></div>
    </div>}
    {!collapsed && <p className="diagnostic-summary sr-only" aria-live="polite">{facts}</p>}
  </section>;
}

export function RecordingSetDiagnostics({ tracks, playhead, onSeek: _onSeek, onSolo }: { tracks: DiagnosticTrack[]; playhead: number; onSeek?: (seconds: number) => void; onSolo?: (trackIndex: number | null) => void }) {
  const [filter, setFilter] = React.useState<"all" | "active" | "flagged">("all");
  const [collapsed, setCollapsed] = React.useState<Set<string>>(new Set());
  const [solo, setSolo] = React.useState<string | null>(null);
  if (!tracks.length) return <div className="diagnostics-empty" role="status">No microphone diagnostics are available for this Preview Run.</div>;
  const domains = diagnosticDomains(tracks);
  const moments = reviewMoments(tracks);
  const flaggedIds = new Set(moments.filter((moment) => moment.flagged).flatMap((moment) => moment.trackIds));
  const visible = tracks.filter((track) => filter === "all" || (filter === "active" ? frameAt(track, playhead)?.target_open : flaggedIds.has(track.id || track.name)));
  return <div className="diagnostics-scroll" tabIndex={0} aria-label="Recording Set diagnostic timeline; scroll horizontally at constrained widths">
    <div className="diagnostics-timeline">
      <header className="diagnostic-heading">
        <div><small>AUTOMIX DECISIONS</small><h2>Decision + response timeline</h2></div>
        <div className="diagnostic-filters" role="group" aria-label="Microphone lane filter">{(["all", "active", "flagged"] as const).map((value) => <button type="button" key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>{value === "all" ? "All" : value === "active" ? "Active now" : "Flagged"}</button>)}</div>
      </header>
      <div className="diagnostic-key" aria-label="Timeline legend"><span><i className="speech-key" />Detected speech</span><span><i className="open-key" />Target open</span><span><i className="attenuate-key" />Target attenuate</span><span><i className="gain-key" />Actual gain</span></div>
      <div className="diagnostic-layout">
        <div className="diagnostic-tracks">{visible.length ? visible.map((track) => { const id = track.id || track.name; return <DiagnosticLane key={id} track={track} playhead={playhead} domains={domains} index={tracks.indexOf(track)} collapsed={collapsed.has(id)} soloed={solo === id} onCollapse={() => setCollapsed((current) => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next; })} onSolo={() => { const next = solo === id ? null : id; setSolo(next); onSolo?.(next === null ? null : tracks.indexOf(track)); }} />; }) : <p role="status">No microphones match this filter.</p>}</div>
        <section className="playhead-inspector" aria-label="Playhead Inspector">
          <small>AT {playhead.toFixed(1)}s</small><h3>Playhead inspector</h3>
          <div>{tracks.map((track, index) => { const frame = frameAt(track, playhead); if (!frame) return null; return <p style={{ "--track-color": track.color || fallbackColors[index % fallbackColors.length] } as React.CSSProperties} key={track.id || `${track.name}-${index}`}><strong><i />{track.name}</strong><b>{frame.gain_db.toFixed(1)} dB</b><span>{frame.speech ? "Speaking" : "Silent"} · {frame.target_open ? "Open target" : "Attenuate target"}</span><em>{responseText[frame.response]}</em></p>; })}</div>
        </section>
      </div>
    </div>
  </div>;
}
