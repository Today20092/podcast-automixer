(() => {
  const preview = document.querySelector('#preview');
  preview.insertAdjacentHTML('afterend', `<section id="comparison" class="preview" hidden aria-labelledby="comparison-title"><div class="eyebrow">Comparison Playback</div><h2 id="comparison-title">Judge the processing, not the volume.</h2><p id="comparison-metrics" class="hint">Preparing loudness-matched playback…</p><div><button id="play-pause" type="button" disabled>Play</button><button data-program="original" type="button" disabled>Original</button><button data-program="automixed" type="button" disabled>Automixed</button><label> Volume <input id="output-volume" type="range" min="0" max="1" value="1" step="0.01"></label><span id="playback-time" class="hint">0:00 / 0:00</span></div><div id="comparison-waveform" class="waveform" role="slider" tabindex="0" aria-label="Comparison Playback position"><span id="comparison-playhead" class="range"></span></div><p class="hint">Space: play or pause · Left/Right: seek 1 second · O/A: switch program</p></section>`);
  const $ = selector => document.querySelector(selector), clock = seconds => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds) % 60).padStart(2, '0')}`;
  let audio = [], program = 'original', duration = 0, masterVolume = 1;
  const play = $('#play-pause'), time = $('#playback-time'), head = $('#comparison-playhead');
  const sync = () => { const current = audio[0]?.currentTime || 0; head.style.left = `${current / duration * 100}%`; head.style.width = '2px'; time.textContent = `${clock(current)} / ${clock(duration)}`; if (!audio[0]?.paused) requestAnimationFrame(sync); };
  const select = next => { program = next; audio.forEach(item => item.muted = item.dataset.program !== next); document.querySelectorAll('[data-program]').forEach(button => button.classList.toggle('primary', button.dataset.program === next)); };
  const load = async () => {
    const comparison = await window.pywebview.api.comparison_playback();
    duration = comparison.duration_seconds;
    const gain = comparison.playback_gain_db;
    const make = (paths, name, offset) => paths.map(path => { const item = new Audio(`file:///${path.replaceAll('\\', '/')}`); item.dataset.program = name; item.dataset.gain = Math.pow(10, gain[name] / 20) / paths.length; item.volume = item.dataset.gain; item.currentTime = offset; item.addEventListener('ended', () => play.textContent = 'Play'); return item; });
    audio = [...make(comparison.original_paths, 'original', comparison.start_seconds), ...make(comparison.automixed_paths, 'automixed', 0)];
    $('#comparison').hidden = false; $('#comparison-metrics').textContent = `Loudness matched using ${comparison.standard}; source and Preview Run files remain unchanged.`;
    [play, ...document.querySelectorAll('[data-program]')].forEach(button => button.disabled = false); select('original'); sync();
  };
  play.onclick = async () => { if (audio[0].paused) { await Promise.all(audio.map(item => item.play())); play.textContent = 'Pause'; sync(); } else { audio.forEach(item => item.pause()); play.textContent = 'Play'; } };
  document.querySelectorAll('[data-program]').forEach(button => button.onclick = () => select(button.dataset.program));
  $('#output-volume').oninput = event => { masterVolume = Number(event.target.value); audio.forEach(item => item.volume = Number(item.dataset.gain) * masterVolume); };
  $('#comparison-waveform').onclick = event => { const at = (event.offsetX / event.currentTarget.clientWidth) * duration; audio.forEach(item => item.currentTime = at); sync(); };
  document.addEventListener('keydown', event => { if (!audio.length || event.target.matches('input')) return; if (event.code === 'Space') { event.preventDefault(); play.click(); } if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') audio.forEach(item => item.currentTime = Math.max(0, item.currentTime + (event.key === 'ArrowLeft' ? -1 : 1))); if (event.key.toLowerCase() === 'o') select('original'); if (event.key.toLowerCase() === 'a') select('automixed'); });
  window.addEventListener('preview-complete', load);
})();
