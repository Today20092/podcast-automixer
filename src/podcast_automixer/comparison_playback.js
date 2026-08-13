(() => {
  const preview = document.querySelector('#preview');
  const style = document.createElement('style');
  style.textContent = `.waveform::before{display:none}.waveform{background:var(--canvas)}.waveform svg{position:absolute;inset:0;width:100%;height:100%;color:var(--accent)}.waveform-path{fill:color-mix(in srgb,currentColor 42%,transparent);stroke:currentColor;stroke-width:.5}.waveform-state{position:absolute;inset:0;display:grid;place-items:center;margin:0;color:var(--muted);pointer-events:none}.playhead{position:absolute;top:0;bottom:0;width:2px;background:var(--ink);transition:left .08s linear}@media(prefers-reduced-motion:reduce){.playhead{transition:none}}`;
  document.head.append(style);
  preview.insertAdjacentHTML('afterend', `<section id="comparison" class="preview" hidden aria-labelledby="comparison-title"><div class="eyebrow">Comparison Playback</div><h2 id="comparison-title">Judge the processing, not the volume.</h2><p id="comparison-metrics" class="hint">Preparing loudness-matched playback…</p><div role="group" aria-label="Comparison Playback program"><button id="play-pause" type="button" disabled>Play</button><button data-program="original" type="button" disabled>Original</button><button data-program="automixed" type="button" disabled>Automixed</button><button data-program="difference" type="button" disabled aria-describedby="difference-help">Difference</button><label> Volume <input id="output-volume" type="range" min="0" max="1" value="1" step="0.01" aria-label="Comparison Playback volume"></label><span id="playback-time" class="hint">0:00 / 0:00</span></div><p id="difference-help" class="hint"><strong>Difference = Automixed − Original.</strong> It reveals content changed or removed by processing and is for monitoring only, not a deliverable.</p><div id="comparison-waveform" class="waveform" role="slider" tabindex="0" aria-label="Comparison Playback position"><span id="comparison-selection" class="range"></span><span id="comparison-playhead" class="playhead"></span></div><p class="hint">Space: play or pause · Left/Right: seek 1 second · O/A/D: switch program</p></section>`);

  const $ = selector => document.querySelector(selector);
  const clock = seconds => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds) % 60).padStart(2, '0')}`;
  const waveform = $('#waveform');
  let overview = null;
  let overviewPromise = null;

  const state = (target, message) => {
    target.querySelector('svg')?.remove();
    let output = target.querySelector('.waveform-state');
    if (!output) {
      output = document.createElement('p');
      output.className = 'waveform-state';
      output.setAttribute('role', 'status');
      target.prepend(output);
    }
    output.textContent = message;
  };
  const draw = target => {
    if (!overview?.points?.length) return state(target, 'Waveform unavailable');
    target.querySelector('.waveform-state')?.remove();
    target.querySelector('svg')?.remove();
    const count = overview.points.length;
    const upper = overview.points.map((point, index) => `${index ? 'L' : 'M'}${index / (count - 1 || 1) * 100},${50 - point[1] * 48}`).join(' ');
    const lower = [...overview.points].reverse().map((point, reverseIndex) => { const index = count - reverseIndex - 1; return `L${index / (count - 1 || 1) * 100},${50 - point[0] * 48}`; }).join(' ');
    target.insertAdjacentHTML('afterbegin', `<svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><path class="waveform-path" d="${upper} ${lower} Z"></path></svg>`);
  };
  const loadOverview = async () => {
    const paths = [...document.querySelectorAll('[data-remove]')].map(button => button.dataset.remove);
    if (!paths.length) return null;
    const key = paths.join('\n');
    if (overviewPromise?.key === key) return overviewPromise;
    overview = null;
    state(waveform, 'Loading Original Monitoring Mix waveform…');
    overviewPromise = window.pywebview.api.start_waveform_overview(paths)
      .then(async () => { let status; do { await new Promise(resolve => setTimeout(resolve, 25)); status = await window.pywebview.api.waveform_overview_status(); } while (status.state === 'loading'); if (status.state !== 'complete') throw new Error('Waveform unavailable'); return status.result; })
      .then(result => { if (overviewPromise.key === key) { overview = result; draw(waveform); } return result; })
      .catch(() => { if (overviewPromise.key === key) { overview = null; state(waveform, 'Waveform unavailable for this Recording Set'); } return null; });
    overviewPromise.key = key;
    return overviewPromise;
  };
  new MutationObserver(() => { if (!preview.hidden) loadOverview(); }).observe(preview, {attributes: true, attributeFilter: ['hidden']});
  state(waveform, 'Waveform loads after the Recording Set is validated');

  let audio = [], program = 'original', duration = 0, startSeconds = 0, context, master, protection, buses = {};
  const play = $('#play-pause'), time = $('#playback-time'), head = $('#comparison-playhead');
  const position = () => Math.max(0, (audio[0]?.currentTime || 0) - Number(audio[0]?.dataset.offset || 0));
  const seek = at => audio.forEach(item => { item.currentTime = Number(item.dataset.offset) + Math.max(0, Math.min(duration, at)); });
  const sync = () => {
    const current = position(), fullDuration = overview?.duration_seconds || duration;
    head.style.left = `${(startSeconds + current) / fullDuration * 100}%`;
    time.textContent = `${clock(startSeconds + current)} / ${clock(fullDuration)}`;
    $('#comparison-waveform').setAttribute('aria-valuetext', `Playhead ${clock(startSeconds + current)} of ${clock(fullDuration)}`);
    if (!audio[0]?.paused) requestAnimationFrame(sync);
  };
  const select = next => { program = next; Object.entries(buses).forEach(([name, bus]) => bus.gain.setValueAtTime(name === next || name.startsWith(`${next}:`) ? Number(bus.datasetGain) : 0, context.currentTime)); document.querySelectorAll('[data-program]').forEach(button => { const selected = button.dataset.program === next; button.classList.toggle('primary', selected); button.setAttribute('aria-pressed', selected); }); };
  const load = async () => {
    const [comparison] = await Promise.all([window.pywebview.api.comparison_playback(), loadOverview()]);
    audio.forEach(item => { item.pause(); item.src = ''; });
    duration = comparison.duration_seconds;
    startSeconds = comparison.start_seconds;
    const gain = comparison.playback_gain_db;
    if (!context) { context = new AudioContext(); protection = context.createDynamicsCompressor(); protection.threshold.value = -1; protection.knee.value = 0; protection.ratio.value = 20; protection.attack.value = 0.003; protection.release.value = 0.1; master = context.createGain(); protection.connect(master); master.connect(context.destination); }
    const bus = (name, busGain) => { const node = context.createGain(); node.datasetGain = busGain; node.gain.value = 0; node.connect(protection); return [name, node]; };
    const originalGain = Math.pow(10, gain.original / 20), automixedGain = Math.pow(10, gain.automixed / 20);
    buses = Object.fromEntries([bus('original', originalGain), bus('automixed', automixedGain), bus('difference:original', -originalGain), bus('difference:automixed', automixedGain)]);
    const make = (paths, name, offset) => paths.map(path => { const item = new Audio(`file:///${path.replaceAll('\\', '/')}`); item.dataset.program = name; item.dataset.offset = offset; item.currentTime = offset; const source = context.createMediaElementSource(item); source.connect(buses[name]); source.connect(buses[`difference:${name}`]); item.addEventListener('ended', () => play.textContent = 'Play'); return item; });
    audio = [...make(comparison.original_paths, 'original', startSeconds), ...make(comparison.automixed_paths, 'automixed', 0)];
    const show = value => value == null ? 'unavailable' : `${value.toFixed(1)} LUFS`, trim = value => `${value >= 0 ? '+' : ''}${value.toFixed(1)} dB`;
    $('#comparison').hidden = false;
    $('#comparison-metrics').textContent = `Original ${show(comparison.monitoring_mix.integrated_lufs)}, trim ${trim(gain.original)}; Automixed ${show(comparison.automixed_virtual_program.integrated_lufs)}, trim ${trim(gain.automixed)}. ${comparison.standard}; source and Preview Run files remain unchanged.`;
    const target = $('#comparison-waveform');
    draw(target);
    const fullDuration = overview?.duration_seconds || duration;
    const selection = $('#comparison-selection');
    selection.style.left = `${startSeconds / fullDuration * 100}%`;
    selection.style.width = `${duration / fullDuration * 100}%`;
    [play, ...document.querySelectorAll('[data-program]')].forEach(button => button.disabled = false);
    select('original'); sync();
  };
  play.onclick = async () => { if (audio[0].paused) { await context.resume(); await Promise.all(audio.map(item => item.play())); play.textContent = 'Pause'; sync(); } else { audio.forEach(item => item.pause()); play.textContent = 'Play'; } };
  document.querySelectorAll('[data-program]').forEach(button => button.onclick = () => select(button.dataset.program));
  $('#output-volume').oninput = event => { master.gain.setValueAtTime(Number(event.target.value), context.currentTime); };
  $('#comparison-waveform').onclick = event => { const fullDuration = overview?.duration_seconds || duration; seek((event.offsetX / event.currentTarget.clientWidth) * fullDuration - startSeconds); sync(); };
  document.addEventListener('keydown', event => { if (!audio.length || event.target.matches('input, textarea, select, [contenteditable]')) return; if (event.code === 'Space') { event.preventDefault(); play.click(); } if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') seek(position() + (event.key === 'ArrowLeft' ? -1 : 1)); if (event.key.toLowerCase() === 'o') select('original'); if (event.key.toLowerCase() === 'a') select('automixed'); if (event.key.toLowerCase() === 'd') select('difference'); sync(); });
  window.addEventListener('preview-complete', load);
})();
