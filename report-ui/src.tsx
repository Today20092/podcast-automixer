import React from 'react'
import { createRoot } from 'react-dom/client'

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

interface ReportData {
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
    <div className="cells" style={{ gridTemplateColumns: `repeat(${timeline.length},minmax(1px,1fr))` }}>
      {timeline.map((window, index) => <span key={index} className={className} style={{ opacity: value(window) / 100 }} />)}
    </div>
  </div>
}

function AttenuationOverview({ report }: { report: ReportData }) {
  const duration = report.timeline.at(-1)?.end_seconds ?? 0
  return (
    <section className="panel" aria-labelledby="attenuation-title">
      <div className="section-heading">
        <div><p className="eyebrow">WHO WAS TURNED DOWN?</p><h2 id="attenuation-title">Attenuation overview</h2>
          <p>Each column summarizes {report.window_seconds.toLocaleString()} seconds. Darker color means the microphone spent more of that window attenuated.</p></div>
      </div>
      <div className="lanes">
        {report.tracks.map((track, channel) => (
          <div className="lane" key={track.id}>
            <span className="lane-label"><i style={{ background: track.color }} />{track.name}</span>
            <div className="cells" style={{ gridTemplateColumns: `repeat(${report.timeline.length},minmax(1px,1fr))` }}>
              {report.timeline.map((window, index) => (
                <span key={index} style={{ background: track.color, opacity: 0.08 + window.attenuated_percent[channel] / 109 }}>
                  <span className="sr-only">{formatTime(window.start_seconds)}: {window.attenuated_percent[channel].toFixed(0)}% attenuated, average {window.gain_db[channel].toFixed(2)} dB</span>
                </span>
              ))}
            </div>
          </div>
        ))}
        <EventLane label="Multiple active" className="overlap" timeline={report.timeline} value={(window) => window.overlap_percent} />
        <EventLane label="Unowned" className="unowned" timeline={report.timeline} value={(window) => window.unowned_percent} />
      </div>
      <div className="time-axis"><span>0:00</span><span>{formatTime(duration / 2)}</span><span>{formatTime(duration)}</span></div>
      <div className="legend"><span><i className="low" />Mostly open</span><span><i className="high" />Mostly attenuated</span><span><i className="overlap" />Multiple active</span><span><i className="unowned" />Unowned</span></div>
    </section>
  )
}

function SpeakerShare({ report }: { report: ReportData }) {
  return (
    <section className="panel" aria-labelledby="share-title">
      <div className="section-heading"><div><p className="eyebrow">HOW OWNERSHIP CHANGED</p><h2 id="share-title">Speaker ownership by section</h2>
        <p>Exclusive ownership is separated from multiple-active and unowned time, so every bar totals 100%.</p></div></div>
      <div className="share-list">
        {report.speaker_share.map((window, index) => (
          <div className="share-row" key={index}>
            <span>{formatTime(window.start_seconds)}–{formatTime(window.end_seconds)}</span>
            <div className="stack" aria-label={`Ownership from ${formatTime(window.start_seconds)} to ${formatTime(window.end_seconds)}`}>
              {window.track_percent.map((value, channel) => <i key={channel} style={{ width: `${value}%`, background: report.tracks[channel].color }} title={`${report.tracks[channel].name}: ${value}%`} />)}
              <i className="overlap" style={{ width: `${window.overlap_percent}%` }} title={`Multiple active: ${window.overlap_percent}%`} />
              <i className="unowned" style={{ width: `${window.unowned_percent}%` }} title={`Unowned: ${window.unowned_percent}%`} />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function ReviewMoments({ report }: { report: ReportData }) {
  const moments = report.review_moments
  return (
    <section className="panel" aria-labelledby="review-title">
      <div className="section-heading"><div><p className="eyebrow">START REVIEWING HERE</p><h2 id="review-title">Moments to review</h2>
        <p>The longest ownership anomalies, ranked by duration.</p></div></div>
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
    <HealthSummary health={report.health} /><TimeConstantSummary report={report} /><LoudnessSummary report={report} /><AttenuationOverview report={report} /><SpeakerShare report={report} />
    <ReviewMoments report={report} /><TrackDetails report={report} /></main>
}

const style = document.createElement('style')
style.textContent = `
.loudness-metrics{grid-template-columns:repeat(5,1fr);margin-bottom:0}
:root{color-scheme:light dark;--page:#f4f6fa;--surface:#fff;--ink:#172033;--muted:#657085;--line:#d9e0ea;--border:#d4dce8;--overlap:#f59e0b;--unowned:#94a3b8}
@media(prefers-color-scheme:dark){:root{--page:#0c1119;--surface:#141b27;--ink:#f5f7fb;--muted:#a8b3c5;--line:#293346;--border:#344156;--overlap:#fbbf24;--unowned:#64748b}}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:15px/1.45 Inter,ui-sans-serif,system-ui,sans-serif}main{width:min(1120px,100%);margin:auto;padding:40px 24px 56px}header{margin-bottom:30px}.eyebrow{margin:0 0 6px;color:#6687ff;font-size:.7rem;font-weight:750;letter-spacing:.14em}h1{margin:0;font-size:clamp(2rem,4vw,2.8rem);letter-spacing:-.04em}h2{margin:0;font-size:1.2rem;letter-spacing:-.015em}.subtitle,.section-heading p,.empty{color:var(--muted)}.subtitle{margin:7px 0 0}.section-heading{display:flex;justify-content:space-between;gap:20px;margin-bottom:18px}.section-heading p:not(.eyebrow){margin:5px 0 0;font-size:.86rem}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}.metrics article,.panel,.track-grid article{background:var(--surface);border:1px solid var(--border);border-radius:14px}.metrics article{padding:16px;display:flex;flex-direction:column}.metrics span{color:var(--muted);font-size:.77rem}.metrics strong{font-size:1.55rem;margin:4px 0}.metrics small{color:var(--muted);font-size:.72rem}.panel{padding:22px;margin-top:16px}.lanes{display:grid;gap:9px}.lane{display:grid;grid-template-columns:minmax(120px,190px) 1fr;gap:12px;align-items:center}.lane-label{display:flex;align-items:center;gap:7px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.82rem}.lane-label i,.track-grid article>span i{width:9px;height:9px;border-radius:50%;flex:none}.cells{display:grid;height:30px;gap:1px;background:var(--line);overflow:hidden;border-radius:4px}.cells>span{min-width:0}.event-lane .cells{height:10px;background:transparent}.overlap{background:var(--overlap)!important}.unowned{background:var(--unowned)!important}.time-axis{display:flex;justify-content:space-between;margin:7px 0 0 min(202px,25%);color:var(--muted);font-size:.72rem;font-variant-numeric:tabular-nums}.legend{display:flex;flex-wrap:wrap;gap:14px;margin-top:18px;color:var(--muted);font-size:.76rem}.legend span{display:inline-flex;align-items:center;gap:6px}.legend i{width:14px;height:9px;border-radius:2px;background:#6687ff}.legend .low{opacity:.16}.legend .high{opacity:.9}.share-list{display:grid;gap:10px}.share-row{display:grid;grid-template-columns:110px 1fr;gap:12px;align-items:center}.share-row>span{color:var(--muted);font-size:.76rem;font-variant-numeric:tabular-nums}.stack{height:24px;display:flex;background:var(--line);overflow:hidden;border-radius:4px}.stack i{display:block;min-width:0}.moments{list-style:none;padding:0;margin:0}.moments li{display:grid;grid-template-columns:130px 1fr auto;gap:14px;padding:11px 0;border-top:1px solid var(--line);align-items:center}.moments strong,.moments b{font-variant-numeric:tabular-nums}.moments span{color:var(--muted)}.moments b{font-size:.8rem}.track-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:16px}.track-grid article{padding:16px}.track-grid article>span{display:flex;align-items:center;gap:7px;font-weight:700;overflow-wrap:anywhere}.track-grid dl{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:14px 0 0}.track-grid dl div{min-width:0}.track-grid dt{color:var(--muted);font-size:.72rem}.track-grid dd{margin:2px 0 0;font-weight:650;font-size:.84rem;font-variant-numeric:tabular-nums;white-space:nowrap}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(max-width:760px){main{padding:24px 14px 40px}.metrics{grid-template-columns:repeat(2,1fr)}.panel{padding:18px 12px}.lane{grid-template-columns:1fr;gap:4px}.time-axis{margin-left:0}.share-row{grid-template-columns:84px 1fr}.track-grid{grid-template-columns:1fr}.moments li{grid-template-columns:105px 1fr}.moments b{display:none}}
`
document.head.append(style)
createRoot(document.getElementById('root')!).render(<App />)
