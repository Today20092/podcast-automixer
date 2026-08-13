export type ComparisonProgram = "original" | "automixed" | "difference";

export type ComparisonSources = {
  original_paths: string[];
  automixed_paths: string[];
  start_seconds: number;
  duration_seconds: number;
  playback_gain_db: { original: number; automixed: number };
};

type AudioFactory = (path: string) => HTMLAudioElement;
type ContextFactory = () => AudioContext;

const url = (path: string) => `file:///${path.replaceAll("\\", "/")}`;

export class ComparisonAudioController {
  readonly audio: HTMLAudioElement[];
  private readonly offsets: number[];
  private readonly buses: Record<ComparisonProgram, GainNode>;
  private readonly context: AudioContext;
  private readonly monitorGains: GainNode[] = [];
  private selected: ComparisonProgram = "original";
  private looping = false;
  private playing = false;
  private onUpdate: (position: number, playing: boolean) => void = () => {};

  constructor(
    private readonly sources: ComparisonSources,
    makeAudio: AudioFactory = (path) => new Audio(path),
    makeContext: ContextFactory = () => new AudioContext(),
  ) {
    this.context = makeContext();
    const protection = this.context.createDynamicsCompressor();
    protection.connect(this.context.destination);
    this.buses = {
      original: this.context.createGain(),
      automixed: this.context.createGain(),
      difference: this.context.createGain(),
    };
    Object.values(this.buses).forEach((bus) => bus.connect(protection));
    this.buses.original.gain.value = 1;
    this.buses.automixed.gain.value = 0;
    this.buses.difference.gain.value = 0;

    const originalGain = 10 ** (sources.playback_gain_db.original / 20);
    const automixedGain = 10 ** (sources.playback_gain_db.automixed / 20);
    const definitions: [string, number, GainNode, GainNode][] = [
      ...sources.original_paths.map((path) => [path, sources.start_seconds, this.buses.original, this.buses.difference] as [string, number, GainNode, GainNode]),
      ...sources.automixed_paths.map((path) => [path, 0, this.buses.automixed, this.buses.difference] as [string, number, GainNode, GainNode]),
    ];
    this.offsets = definitions.map(([, offset]) => offset);
    this.audio = definitions.map(([path, offset, programBus, differenceBus], index) => {
      const item = makeAudio(url(path));
      item.currentTime = offset;
      const source = this.context.createMediaElementSource(item);
      const monitorGain = this.context.createGain();
      monitorGain.gain.value = 1;
      source.connect(monitorGain);
      this.monitorGains.push(monitorGain);
      const programGain = this.context.createGain();
      const isOriginal = index < sources.original_paths.length;
      programGain.gain.value = isOriginal ? originalGain : automixedGain;
      monitorGain.connect(programGain);
      programGain.connect(programBus);
      const differenceGain = this.context.createGain();
      differenceGain.gain.value = isOriginal ? -originalGain : automixedGain;
      monitorGain.connect(differenceGain);
      differenceGain.connect(differenceBus);
      return item;
    });
    const clock = this.audio[0];
    if (clock) {
      clock.ontimeupdate = () => this.emit();
      clock.onended = () => this.finish();
    }
  }

  subscribe(callback: (position: number, playing: boolean) => void) {
    this.onUpdate = callback;
    this.emit();
  }

  position() { return Math.max(0, (this.audio[0]?.currentTime ?? 0) - (this.offsets[0] ?? 0)); }
  isPlaying() { return this.playing; }
  isLooping() { return this.looping; }
  program() { return this.selected; }

  async toggle() {
    if (this.playing) {
      this.audio.forEach((item) => item.pause());
      this.playing = false;
    } else {
      if (this.position() >= this.sources.duration_seconds) this.seek(0);
      await this.context.resume();
      await Promise.all(this.audio.map((item) => item.play()));
      this.playing = true;
    }
    this.emit();
  }

  select(program: ComparisonProgram) {
    const now = this.context.currentTime;
    this.buses[this.selected].gain.setTargetAtTime(0, now, 0.01 / 3);
    this.buses[program].gain.setTargetAtTime(1, now, 0.01 / 3);
    this.selected = program;
  }

  seek(position: number) {
    const next = Math.max(0, Math.min(position, this.sources.duration_seconds));
    this.audio.forEach((item, index) => { item.currentTime = next + this.offsets[index]; });
    this.emit();
  }

  setLoop(looping: boolean) { this.looping = looping; }

  setSolo(trackIndex: number | null) {
    const microphoneCount = this.sources.original_paths.length;
    const now = this.context.currentTime;
    this.monitorGains.forEach((gain, sourceIndex) => {
      const microphoneIndex = sourceIndex % microphoneCount;
      gain.gain.setTargetAtTime(trackIndex === null || microphoneIndex === trackIndex ? 1 : 0, now, 0.01 / 3);
    });
  }

  stop() {
    this.audio.forEach((item) => item.pause());
    this.playing = false;
    this.emit();
  }

  private finish() {
    if (this.looping) {
      this.seek(0);
      void Promise.all(this.audio.map((item) => item.play()));
    } else {
      this.audio.forEach((item) => item.pause());
      this.playing = false;
      this.seek(this.sources.duration_seconds);
    }
  }

  private emit() { this.onUpdate(this.position(), this.playing); }
}
