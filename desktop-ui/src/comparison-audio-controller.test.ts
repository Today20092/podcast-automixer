import { describe, expect, it, vi } from "vitest";
import { ComparisonAudioController } from "./comparison-audio-controller";

class FakeParam {
  value = 0;
  changes: [number, number, number][] = [];
  setTargetAtTime(value: number, time: number, constant: number) { this.changes.push([value, time, constant]); this.value = value; }
}
class FakeNode {
  gain = new FakeParam();
  connect = vi.fn();
}
class FakeAudio {
  currentTime = 0;
  ontimeupdate: (() => void) | null = null;
  onended: (() => void) | null = null;
  pause = vi.fn();
  play = vi.fn(async () => undefined);
}

function setup() {
  const audio: FakeAudio[] = [];
  const gains: FakeNode[] = [];
  const context = {
    currentTime: 4,
    destination: new FakeNode(),
    createDynamicsCompressor: () => new FakeNode(),
    createGain: () => { const gain = new FakeNode(); gains.push(gain); return gain; },
    createMediaElementSource: () => new FakeNode(),
    resume: vi.fn(async () => undefined),
  };
  const controller = new ComparisonAudioController(
    {
      original_paths: ["original.wav"], automixed_paths: ["automixed.wav"],
      start_seconds: 12, duration_seconds: 30,
      playback_gain_db: { original: -2, automixed: -4 },
    },
    () => { const item = new FakeAudio(); audio.push(item); return item as unknown as HTMLAudioElement; },
    () => context as unknown as AudioContext,
  );
  return { controller, audio, gains };
}

function setupTwoTracks() {
  const audio: FakeAudio[] = [];
  const gains: FakeNode[] = [];
  const context = { currentTime: 4, destination: new FakeNode(), createDynamicsCompressor: () => new FakeNode(), createGain: () => { const gain = new FakeNode(); gains.push(gain); return gain; }, createMediaElementSource: () => new FakeNode(), resume: vi.fn(async () => undefined) };
  const controller = new ComparisonAudioController({ original_paths: ["o1.wav", "o2.wav"], automixed_paths: ["a1.wav", "a2.wav"], start_seconds: 0, duration_seconds: 30, playback_gain_db: { original: 0, automixed: 0 } }, () => { const item = new FakeAudio(); audio.push(item); return item as unknown as HTMLAudioElement; }, () => context as unknown as AudioContext);
  return { controller, gains };
}

describe("ComparisonAudioController", () => {
  it("keeps one synchronized graph playing while programs crossfade", async () => {
    const { controller, audio, gains } = setup();
    controller.seek(7.25);
    await controller.toggle();
    controller.setLoop(true);
    controller.select("difference");

    expect(audio.map((item) => item.currentTime)).toEqual([19.25, 7.25]);
    expect(audio.every((item) => item.play.mock.calls.length === 1)).toBe(true);
    expect(controller.position()).toBe(7.25);
    expect(controller.isPlaying()).toBe(true);
    expect(controller.isLooping()).toBe(true);
    expect(gains.slice(0, 3).flatMap((node) => node.gain.changes).some((change) => change[2] === 0.01 / 3)).toBe(true);
  });

  it("stops at the end, or restarts every source from the shared clock when looping", async () => {
    const first = setup();
    await first.controller.toggle();
    first.audio[0].onended?.();
    expect(first.controller.isPlaying()).toBe(false);
    expect(first.controller.position()).toBe(30);

    const second = setup();
    second.controller.setLoop(true);
    await second.controller.toggle();
    second.audio[0].onended?.();
    expect(second.audio.map((item) => item.currentTime)).toEqual([12, 0]);
    expect(second.audio.every((item) => item.play.mock.calls.length === 2)).toBe(true);
  });

  it("solos the corresponding microphone in every comparison program without changing transport", async () => {
    const { controller, gains } = setupTwoTracks();
    controller.seek(8);
    await controller.toggle();
    controller.select("difference");
    controller.setSolo(1);
    const monitorGains = [gains[3], gains[6], gains[9], gains[12]];
    expect(monitorGains.map((gain) => gain.gain.value)).toEqual([0, 1, 0, 1]);
    expect(controller.position()).toBe(8);
    expect(controller.program()).toBe("difference");
    expect(controller.isPlaying()).toBe(true);
    controller.setSolo(null);
    expect(monitorGains.map((gain) => gain.gain.value)).toEqual([1, 1, 1, 1]);
  });
});
