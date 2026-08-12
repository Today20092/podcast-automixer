import React from 'react'
import { createRoot } from 'react-dom/client'
import { defineChart, lineY } from '@tanstack/charts'
import { scaleLinear } from '@tanstack/charts/scales/linear'
import { tooltip } from '@tanstack/charts/tooltip'
import { Chart } from '@tanstack/charts/react/tooltip'

interface TrackRow {
  id: string
  name: string
  active: number
  meanGain: number
  calibration: number
  noiseFloor: number
  minimumGain: number
  color: string
}

interface Health {
  single_owner_percent: number
  multiple_owner_percent: number
  unowned_percent: number
  switches_per_minute: number
}

interface TimelineWindow {
  start_seconds: number
  end_seconds: number
  gain_db: readonly number[]
  attenuated_percent: readonly number[]
  overlap_percent: number
  unowned_percent: number
}

interface ShareWindow {
  start_seconds: number
  end_seconds: number
  track_percent: readonly number[]
  overlap_percent: number
  unowned_percent: number
}

interface ReviewMoment {
  kind: 'multiple' | 'unowned'
  start_seconds: number
  end_seconds: number
  duration_seconds: number
  track_indexes: readonly number[]
}

interface TrackSummary {
  exclusive_percent: number
  active_percent: number
  mean_gain_db: number
  maximum_reduction_db: number
}

interface LoudnessMetrics {
  integrated_lufs: number | null
  maximum_momentary_lufs: number | null
  maximum_short_term_lufs: number | null
  loudness_range_lu: number
  maximum_estimated_true_peak_dbtp: number | null
  short_term_timeline: readonly { seconds: number; lufs: number | null }[]
}

interface LoudnessReport {
  standard: string
  stems: readonly LoudnessMetrics[]
  virtual_mono_program: LoudnessMetrics
}

export interface ReportData {
  openingTimeConstantMs: number
  closingTimeConstantMs: number
  attenuationDb: number
  health: Health
  window_seconds: number
  timeline: readonly TimelineWindow[]
  speaker_share: readonly ShareWindow[]
  review_moments: readonly ReviewMoment[]
  track_summary: readonly TrackSummary[]
  tracks: readonly TrackRow[]
  loudness: LoudnessReport | null
}

interface GainPoint {
  id: string
  seconds: number
  gainDb: number
  trackId: string
  trackName: string
  color: string
  window: TimelineWindow
}

function TimeConstantSummary({ report }: { report: ReportData }) {
  const metrics = [
    ['Opening time constant', `${report.openingTimeConstantMs} ms`],
    ['Closing time constant', `${report.closingTimeConstantMs} ms`],
  ]
  return <section className="panel" aria-labelledby="timing-title">
    <div className="section-heading"><div><p className="eyebrow">GAIN TIMING</p><h2 id="timing-title">Envelope response</h2>
      <p>A time constant reaches about 63% of a change; about 95% takes 3× the value and 99% takes 5×.</p></div></div>
    <div className="metrics">{metrics.map(([label, value]) =>
      <article key={label}><span>{label}</span><strong>{value}</strong></article>)}</div>
  </section>
}

declare global {
  interface Window { __PODCAST_REPORT__: ReportData }
}

function formatTime(seconds: number) {
  const rounded = Math.max(0, Math.round(seconds))
  const hours = Math.floor(rounded / 3600)
  const minutes = Math.floor((rounded % 3600) / 60)
  const remainder = rounded % 60
  return hours
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
    : `${minutes}:${String(remainder).padStart(2, '0')}`
}

function loudnessValue(value: number | null, unit: string) {
  return value === null ? 'Silence' : `${value.toFixed(1)} ${unit}`
}

function LoudnessSummary({ report }: { report: ReportData }) {
  if (!report.loudness) return null
  const program = report.loudness.virtual_mono_program
  const metrics = [
    ['Integrated', loudnessValue(program.integrated_lufs, 'LUFS'), 'Gated loudness of the virtual summed program'],
    ['Max momentary', loudnessValue(program.maximum_momentary_lufs, 'LUFS'), 'Loudest 400 ms window'],
    ['Max short-term', loudnessValue(program.maximum_short_term_lufs, 'LUFS'), 'Loudest 3 second window'],
    ['Loudness range', `${program.loudness_range_lu.toFixed(1)} LU`, 'Dynamics after EBU loudness gating'],
    ['Estimated true peak', loudnessValue(program.maximum_estimated_true_peak_dbtp, 'dBTP'), 'Four-times oversampled program peak estimate'],
  ]
  return <section className="panel" aria-labelledby="loudness-title">
    <div className="section-heading"><div><p className="eyebrow">PERCEPTUAL LEVEL</p><h2 id="loudness-title">Program loudness</h2>
      <p>{report.loudness.standard}. The program is the three processed stems summed at unity.</p></div></div>
    <div className="metrics loudness-metrics">{metrics.map(([label, value, help]) =>
      <article key={label}><span>{label}</span><strong>{value}</strong><small>{help}</small></article>)}</div>
  </section>
}

function HealthSummary({ health }: { health: Health }) {
  const metrics = [
    ['Clear ownership', `${health.single_owner_percent.toFixed(1)}%`, 'Exactly one microphone owned the moment'],
    ['Multiple active', `${health.multiple_owner_percent.toFixed(1)}%`, 'Potential overlap or ambiguous ownership'],
    ['Unowned', `${health.unowned_percent.toFixed(1)}%`, 'No microphone passed the ownership decision'],
    ['Switch rate', `${health.switches_per_minute.toFixed(1)}/min`, 'Changes between clear ownership periods'],
  ]
  return (
    <section aria-labelledby="health-title">
      <div className="section-heading"><div><p className="eyebrow">EPISODE SUMMARY</p><h2 id="health-title">Automix health</h2></div></div>
      <div className="metrics">
        {metrics.map(([label, value, help]) => <article key={label}><span>{label}</span><strong>{value}</strong><small>{help}</small></article>)}
      </div>
    </section>
  )
}

function EventLane({
  label,
  className,
  timeline,
  value,
}: {
  label: string
  className: string
  timeline: readonly TimelineWindow[]
  value: (window: TimelineWindow) => number
}) {
  return <div className="lane event-lane"><span className="lane-label">{label}</span>
    <div className="cells">
      {timeline.map((window, index) => <span key={index} className={className} style={{ opacity: value(window) / 100, flexGrow: window.end_seconds - window.start_seconds }} />)}
    </div>
  </div>
}

function ReviewEventStrip({ moments, duration, className }: { moments: readonly ReviewMoment[]; duration: number; className: string }) {
  return <div className={className} aria-label="Review events across the episode">
    {duration > 0 && moments.map((moment) => <span
      key={`${moment.kind}-${moment.start_seconds}`}
      className={moment.kind === 'multiple' ? 'overlap' : 'unowned'}
      style={{ left: `${moment.start_seconds * 100 / duration}%`, width: `${Math.max(moment.duration_seconds * 100 / duration, .4)}%` }}
      title={`${moment.kind === 'multiple' ? 'Overlap' : 'No clear owner'}, ${formatTime(moment.start_seconds)} to ${formatTime(moment.end_seconds)}`}
    />)}
  </div>
}

function AttenuationOverview({ report }: { report: ReportData }) {
  const duration = report.timeline.at(-1)?.end_seconds ?? 0
  return (
    <section className="panel activity-panel" aria-labelledby="attenuation-title">
      <div className="section-heading">
        <div><p className="eyebrow">THE EPISODE AT A GLANCE</p><h2 id="attenuation-title">Automix activity timeline</h2>
          <p>Each column summarizes {report.window_seconds.toLocaleString()} seconds. Stronger color means more attenuation; the final lanes locate overlap, missing ownership, and review events on the same clock.</p></div>
      </div>
      <div className="lanes">
        {report.tracks.map((track, channel) => (
          <div className="lane" key={track.id}>
            <span className="lane-label"><i style={{ background: track.color }} />{track.name}</span>
            <div className="cells">
              {report.timeline.map((window, index) => (
                <span key={index} style={{ background: track.color, opacity: 0.08 + window.attenuated_percent[channel] / 109, flexGrow: window.end_seconds - window.start_seconds }}>
                  <span className="sr-only">{formatTime(window.start_seconds)}: {window.attenuated_percent[channel].toFixed(0)}% attenuated, average {window.gain_db[channel].toFixed(2)} dB</span>
                </span>
              ))}
            </div>
          </div>
        ))}
        <EventLane label="Multiple active" className="overlap" timeline={report.timeline} value={(window) => window.overlap_percent} />
        <EventLane label="Unowned" className="unowned" timeline={report.timeline} value={(window) => window.unowned_percent} />
        <div className="lane event-lane review-lane"><span className="lane-label">Review events</span>
          <ReviewEventStrip moments={report.review_moments} duration={duration} className="event-track" />
        </div>
      </div>
      <div className="time-axis"><span>0:00</span><span>{formatTime(duration / 2)}</span><span>{formatTime(duration)}</span></div>
      <div className="legend"><span><i className="low" />Mostly open</span><span><i className="high" />Mostly attenuated</span><span><i className="overlap" />Overlap</span><span><i className="unowned" />No clear owner</span></div>
    </section>
  )
}

function GainTrackChart({ report, channel, yScale }: { report: ReportData; channel: number; yScale: ReturnType<typeof scaleLinear> }) {
  const [focused, setFocused] = React.useState<GainPoint | null>(null)
  const track = report.tracks[channel]
  const duration = report.timeline.at(-1)?.end_seconds ?? 0
  const points = React.useMemo<readonly GainPoint[]>(() =>
    report.timeline.flatMap((window, index) => {
      const point = {
      id: `${track.id}-${index}`,
      seconds: (window.start_seconds + window.end_seconds) / 2,
      gainDb: window.gain_db[channel],
      trackId: track.id,
      trackName: track.name,
      color: track.color,
      window,
      }
      return [
        ...(index === 0 ? [{ ...point, id: `${point.id}-start`, seconds: 0 }] : []),
        point,
        ...(index === report.timeline.length - 1
          ? [{ ...point, id: `${point.id}-end`, seconds: duration }]
          : []),
      ]
    }), [channel, duration, report, track])
  const xScale = React.useMemo(() => scaleLinear([0, Math.max(duration, 1)], [0, 1]), [duration])
  const definition = React.useMemo(() => defineChart({
    marks: [lineY(points, {
      x: (point) => point.seconds,
      y: (point) => point.gainDb,
      z: (point) => point.trackId,
      key: (point) => point.id,
      stroke: (point) => point.color,
      strokeWidth: 2.25,
      points: false,
    })],
    x: { scale: xScale, nice: false, grid: true, axis: { label: 'Episode time (seconds)' } },
    y: { scale: yScale, nice: false, grid: true, axis: { label: 'Applied gain (dB)' } },
    focus: 'group-x',
    tooltip: {
      ...tooltip,
      items: [
        { id: 'track', label: 'Track', text: (point) => point.datum.trackName },
        { id: 'time', label: 'Window', text: (point) => `${formatTime(point.datum.window.start_seconds)}–${formatTime(point.datum.window.end_seconds)}` },
        { id: 'gain', label: 'Average gain', text: (point) => `${point.datum.gainDb.toFixed(2)} dB` },
      ],
    },
  }), [points, xScale, yScale])

  return (
    <article className="gain-track">
      <div className="gain-track-heading"><strong><i style={{ background: track.color }} />{track.name}</strong>
        <span>Mean {report.track_summary[channel].mean_gain_db.toFixed(2)} dB · Max {report.track_summary[channel].maximum_reduction_db.toFixed(2)} dB</span></div>
      <Chart<GainPoint, number, number>
        definition={definition}
        height={210}
        ariaLabel={`Applied gain in decibels over episode time for ${track.name}`}
        ariaDescription="Zero decibels is unity gain. Lower values indicate stronger attenuation."
        onFocusChange={(point) => setFocused(point?.datum ?? null)}
        renderTooltipBody={({ points: tooltipPoints, defaultBody }) => tooltipPoints.length
          ? <div className="gain-tooltip"><strong>{formatTime(tooltipPoints[0].datum.seconds)}</strong>{defaultBody}</div>
          : null}
      />
      <p className="focus-readout" aria-live="polite">{focused
        ? `${focused.trackName}, ${formatTime(focused.window.start_seconds)}–${formatTime(focused.window.end_seconds)}: ${focused.gainDb.toFixed(2)} dB average gain`
        : 'Hover, tap, or use the keyboard to inspect a point.'}</p>
    </article>
  )
}

function GainTimeline({ report }: { report: ReportData }) {
  const minimumGain = Math.min(0, ...report.timeline.flatMap((window) => window.gain_db))
  const yScale = React.useMemo(() => scaleLinear([Math.floor(minimumGain), 0], [0, 1]), [minimumGain])
  return (
    <section className="panel" aria-labelledby="gain-timeline-title">
      <div className="section-heading"><div><p className="eyebrow">WHAT THE AUTOMIX APPLIED</p><h2 id="gain-timeline-title">Gain reduction by microphone</h2>
        <p>Aligned charts separate the microphones while preserving the same episode clock and decibel scale. Unity gain is 0 dB; lower values mean stronger attenuation.</p></div></div>
      <div className="gain-small-multiples">{report.tracks.map((item, channel) =>
        <GainTrackChart key={item.id} report={report} channel={channel} yScale={yScale} />)}</div>
    </section>
  )
}

function ConversationBalance({ report }: { report: ReportData }) {
  return (
    <section className="panel" aria-labelledby="balance-title">
      <div className="section-heading"><div><p className="eyebrow">WHO CARRIED EACH SECTION?</p><h2 id="balance-title">Conversation balance</h2>
        <p>Color intensity and the printed value show exclusive speaking time. The outlined cell identifies the leading microphone in each section.</p></div></div>
      <div className="balance-table" role="table" aria-label="Conversation balance by episode section">
        <div className="balance-row balance-head" role="row"><span role="columnheader">Section</span>
          {report.tracks.map((track) => <span role="columnheader" key={track.id}><i style={{ background: track.color }} />{track.name}</span>)}
          <span role="columnheader">Overlap</span><span role="columnheader">No owner</span></div>
        {report.speaker_share.map((window, index) => {
          const leadIndex = window.track_percent.reduce(
            (best, value, channel) => value > window.track_percent[best] ? channel : best, 0)
          return <div className="balance-row" role="row" key={index}>
            <strong role="rowheader">{formatTime(window.start_seconds)} to {formatTime(window.end_seconds)}</strong>
            {window.track_percent.map((value, channel) => <span role="cell" key={channel} className={channel === leadIndex ? 'is-lead' : ''}
              style={{ background: `color-mix(in srgb, ${report.tracks[channel].color} ${Math.max(8, value)}%, var(--surface))` }}>{value.toFixed(0)}%</span>)}
            <span role="cell" style={{ background: `color-mix(in srgb, var(--overlap) ${Math.max(8, window.overlap_percent)}%, var(--surface))` }}>{window.overlap_percent.toFixed(0)}%</span>
            <span role="cell" style={{ background: `color-mix(in srgb, var(--unowned) ${Math.max(8, window.unowned_percent)}%, var(--surface))` }}>{window.unowned_percent.toFixed(0)}%</span>
          </div>
        })}
      </div>
    </section>
  )
}

function ReviewMoments({ report }: { report: ReportData }) {
  const moments = report.review_moments
  const duration = report.timeline.at(-1)?.end_seconds ?? 0
  return (
    <section className="panel" aria-labelledby="review-title">
      <div className="section-heading"><div><p className="eyebrow">START REVIEWING HERE</p><h2 id="review-title">Review event timeline</h2>
        <p>The episode strip locates every detected ownership anomaly. The list below ranks the longest events first.</p></div></div>
      <ReviewEventStrip moments={moments} duration={duration} className="review-strip" />
      <div className="review-axis"><span>0:00</span><span>{formatTime(duration / 2)}</span><span>{formatTime(duration)}</span></div>
      {moments.length ? <ol className="moments">{moments.map((moment, index) => (
        <li key={`${moment.kind}-${moment.start_seconds}`}><strong>{formatTime(moment.start_seconds)}–{formatTime(moment.end_seconds)}</strong>
          <span>{moment.kind === 'multiple'
            ? `Potential overlap or ambiguous ownership: ${moment.track_indexes.map((track) => report.tracks[track].name).join(', ')}`
            : 'No microphone passed the ownership decision'}</span><b>{moment.duration_seconds.toFixed(1)}s</b></li>
      ))}</ol> : <p className="empty">No multiple-active or unowned sections were detected.</p>}
    </section>
  )
}

function TrackDetails({ report }: { report: ReportData }) {
  return <section className="track-grid" aria-label="Track details">{report.tracks.map((track, index) => {
    const summary = report.track_summary[index]
    return <article key={track.id}><span><i style={{ background: track.color }} />{track.name}</span><dl>
      <div><dt>Exclusive owner</dt><dd>{summary.exclusive_percent.toFixed(1)}%</dd></div>
      <div><dt>Average gain</dt><dd>{summary.mean_gain_db.toFixed(2)} dB</dd></div>
      <div><dt>Max reduction</dt><dd>{summary.maximum_reduction_db.toFixed(2)} dB</dd></div>
      <div><dt>Noise floor</dt><dd>{track.noiseFloor.toFixed(1)} dB</dd></div>
    </dl></article>
  })}</section>
}

function App() {
  const report = window.__PODCAST_REPORT__
  return <main><header><p className="eyebrow">AUTOMIX ANALYSIS</p><h1>Podcast mix report</h1><p className="subtitle">Clear ownership, attenuation, and moments worth reviewing</p></header>
    <HealthSummary health={report.health} /><ReviewMoments report={report} /><AttenuationOverview report={report} />
    <GainTimeline report={report} /><ConversationBalance report={report} /><LoudnessSummary report={report} />
    <TimeConstantSummary report={report} /><TrackDetails report={report} /></main>
}

const style = document.createElement('style')
style.textContent = `
.loudness-metrics{grid-template-columns:repeat(5,1fr);margin-bottom:0}
:root{color-scheme:light dark;--page:#f4f6fa;--surface:#fff;--ink:#172033;--muted:#657085;--line:#d9e0ea;--border:#d4dce8;--overlap:#f59e0b;--unowned:#94a3b8}
@media(prefers-color-scheme:dark){:root{--page:#0c1119;--surface:#141b27;--ink:#f5f7fb;--muted:#a8b3c5;--line:#293346;--border:#344156;--overlap:#fbbf24;--unowned:#64748b}}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:15px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}main{width:min(1280px,100%);margin:auto;padding:40px 24px 56px}header{margin-bottom:30px}.eyebrow{margin:0 0 6px;color:#6687ff;font-size:.7rem;font-weight:750;letter-spacing:.14em}h1{margin:0;font-size:clamp(2rem,4vw,2.8rem);letter-spacing:-.04em}h2{margin:0;font-size:1.2rem;letter-spacing:-.015em}.subtitle,.section-heading p,.empty{color:var(--muted)}.subtitle{margin:7px 0 0}.section-heading{display:flex;justify-content:space-between;gap:20px;margin-bottom:20px}.section-heading p:not(.eyebrow){max-width:78ch;margin:5px 0 0;font-size:.86rem}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}.metrics article,.panel,.track-grid article{background:var(--surface);border:1px solid var(--border);border-radius:14px}.metrics article{padding:16px;display:flex;flex-direction:column}.metrics span{color:var(--muted);font-size:.77rem}.metrics strong{font-size:1.55rem;margin:4px 0}.metrics small{color:var(--muted);font-size:.72rem}.panel{padding:26px;margin-top:18px}.lanes{display:grid;gap:11px}.lane{display:grid;grid-template-columns:minmax(150px,210px) 1fr;gap:14px;align-items:center}.lane-label{display:flex;align-items:center;gap:7px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.82rem}.lane-label i,.track-grid article>span i{width:9px;height:9px;border-radius:50%;flex:none}.cells{display:grid;height:38px;gap:1px;background:var(--line);overflow:hidden;border-radius:5px}.cells>span{min-width:0}.event-lane .cells{height:12px;background:transparent}.overlap{background:var(--overlap)!important}.unowned{background:var(--unowned)!important}.time-axis{display:flex;justify-content:space-between;margin:8px 0 0 224px;color:var(--muted);font-size:.72rem;font-variant-numeric:tabular-nums}.legend,.flow-key{display:flex;flex-wrap:wrap;gap:14px;color:var(--muted);font-size:.76rem}.legend{margin-top:20px}.legend span,.flow-key span{display:inline-flex;align-items:center;gap:6px}.legend i{width:14px;height:9px;border-radius:2px;background:#6687ff}.legend .low{opacity:.16}.legend .high{opacity:.9}.flow-key{margin:-4px 0 16px}.flow-key i,.share-lead i{width:9px;height:9px;border-radius:50%;flex:none}.share-list{display:grid;gap:0}.share-row{display:grid;grid-template-columns:110px 1fr;gap:12px;align-items:center}.flow-row{grid-template-columns:112px minmax(150px,220px) minmax(280px,1fr) 170px;padding:13px 0;border-top:1px solid var(--line)}.share-row>span{color:var(--muted);font-size:.76rem;font-variant-numeric:tabular-nums}.share-lead{display:flex;align-items:center;gap:8px;min-width:0;font-size:.82rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.share-lead b{margin-left:auto;color:var(--muted);font-size:.75rem;font-weight:650}.share-flags{text-align:right}.stack{height:28px;display:flex;background:var(--line);overflow:hidden;border-radius:5px}.stack i{display:block;min-width:0}.moments{list-style:none;padding:0;margin:0}.moments li{display:grid;grid-template-columns:130px 1fr auto;gap:14px;padding:11px 0;border-top:1px solid var(--line);align-items:center}.moments strong,.moments b{font-variant-numeric:tabular-nums}.moments span{color:var(--muted)}.moments b{font-size:.8rem}.track-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:16px}.track-grid article{padding:16px}.track-grid article>span{display:flex;align-items:center;gap:7px;font-weight:700;overflow-wrap:anywhere}.track-grid dl{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:14px 0 0}.track-grid dl div{min-width:0}.track-grid dt{color:var(--muted);font-size:.72rem}.track-grid dd{margin:2px 0 0;font-weight:650;font-size:.84rem;font-variant-numeric:tabular-nums;white-space:nowrap}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.chart-legend{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 10px;color:var(--muted);font-size:.78rem}.chart-legend span{display:inline-flex;align-items:center;gap:6px}.chart-legend i{width:10px;height:10px;border-radius:50%}.focus-readout{min-height:1.4em;margin:8px 0 0;color:var(--muted);font-size:.78rem;font-variant-numeric:tabular-nums}.gain-tooltip strong{display:block;margin-bottom:4px}
.event-track,.review-strip{position:relative;background:var(--line);overflow:hidden;border-radius:5px}.event-track{height:12px}.event-track span,.review-strip span{position:absolute;top:0;height:100%;min-width:2px}.review-strip{height:32px;margin-top:2px}.review-axis{display:flex;justify-content:space-between;margin-top:7px;color:var(--muted);font-size:.72rem;font-variant-numeric:tabular-nums}
.cells{display:flex}.cells>span{flex-basis:0}
.gain-small-multiples{display:grid;gap:12px}.gain-track{min-width:0;padding:16px 16px 8px;border:1px solid var(--line);border-radius:10px;background:color-mix(in srgb,var(--surface) 92%,var(--page))}.gain-track-heading{display:flex;justify-content:space-between;gap:16px;margin-bottom:4px}.gain-track-heading strong{display:flex;align-items:center;gap:8px;min-width:0;overflow-wrap:anywhere}.gain-track-heading i{width:10px;height:10px;border-radius:50%;flex:none}.gain-track-heading span{color:var(--muted);font-size:.75rem;font-variant-numeric:tabular-nums;text-align:right}
.balance-table{min-width:720px}.balance-row{display:grid;grid-template-columns:minmax(112px,1.25fr) repeat(5,minmax(92px,1fr));gap:6px;align-items:stretch;margin-top:6px}.balance-row>*{display:flex;align-items:center;justify-content:center;min-width:0;min-height:48px;padding:8px;border-radius:6px;font-size:.78rem;font-variant-numeric:tabular-nums}.balance-row>strong{justify-content:flex-start;color:var(--muted);font-weight:600}.balance-head>*{min-height:auto;padding:0 8px 5px;color:var(--muted);font-size:.7rem}.balance-head span{gap:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.balance-head i{width:8px;height:8px;border-radius:50%;flex:none}.balance-row .is-lead{outline:2px solid var(--ink);outline-offset:-2px;font-weight:750}.panel:has(.balance-table){overflow-x:auto}
@media(max-width:900px){.flow-row{grid-template-columns:100px minmax(130px,180px) 1fr}.share-flags{display:none}}
@media(max-width:760px){main{padding:24px 14px 40px}.metrics{grid-template-columns:repeat(2,1fr)}.panel{padding:18px 12px}.lane{grid-template-columns:1fr;gap:5px}.time-axis{margin-left:0}.flow-row{grid-template-columns:1fr 90px}.share-time{grid-column:1}.share-lead{grid-column:2;grid-row:1}.flow-row .stack{grid-column:1/-1}.gain-track{padding:12px 8px 6px}.gain-track-heading{display:grid;gap:3px}.gain-track-heading span{text-align:left}.track-grid{grid-template-columns:1fr}.moments li{grid-template-columns:105px 1fr}.moments b{display:none}}
`
document.head.append(style)
createRoot(document.getElementById('root')!).render(<App />)
