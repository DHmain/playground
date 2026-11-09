import type { GameState } from "./types";
let soundOn = false;
let musicOn = false;
let context: AudioContext | undefined;
let cueBuffer: AudioBuffer | undefined;
let loadingCue: Promise<void> | undefined;
const music = new Audio("/audio/happy-adventure.mp3");
music.loop = true;
music.preload = "none";
let musicWanted = false;
let currentState: GameState | null = null;

function unlock() {
  context ??= new AudioContext();
  void context.resume().catch(() => {});
  loadingCue ??= fetch("/audio/beat.wav")
    .then((response) => {
      if (!response.ok) throw new Error("Audio unavailable");
      return response.arrayBuffer();
    })
    .then((data) => context!.decodeAudioData(data))
    .then((buffer) => {
      cueBuffer = buffer;
    })
    .catch(() => {});
}
export function beep() {
  if (!soundOn || !context || context.state !== "running") return;
  const gain = context.createGain();
  gain.connect(context.destination);
  gain.gain.value = 0.2;
  if (cueBuffer) {
    const source = context.createBufferSource();
    source.buffer = cueBuffer;
    source.connect(gain);
    source.onended = () => {
      source.disconnect();
      gain.disconnect();
    };
    source.start();
  } else {
    const oscillator = context.createOscillator();
    oscillator.connect(gain);
    oscillator.frequency.value = 700;
    gain.gain.setValueAtTime(0.08, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.05);
    oscillator.onended = () => {
      oscillator.disconnect();
      gain.disconnect();
    };
    oscillator.start();
    oscillator.stop(context.currentTime + 0.05);
  }
}
export function updateAudio(state: GameState | null) {
  currentState = state;
  // Keep the beat cues prominent during rhythm stages.
  music.volume =
    state?.phase === "playing" && (state.stage === 1 || state.stage === 2)
      ? 0.07
      : 0.18;
  const wanted = musicOn && !document.hidden && !!state && !state.paused;
  if (wanted === musicWanted) return;
  musicWanted = wanted;
  if (wanted)
    void music.play().catch(() => {
      musicWanted = false;
      musicOn = false;
      musicButton.textContent = "BGM 켜기";
      musicButton.setAttribute("aria-pressed", "false");
    });
  else music.pause();
}
const button = document.createElement("button");
button.textContent = "박자 소리 켜기";
button.className = "small";
button.setAttribute("aria-pressed", "false");
const musicButton = document.createElement("button");
musicButton.textContent = "BGM 켜기";
musicButton.className = "small";
musicButton.setAttribute("aria-pressed", "false");
document.querySelector("header .row")!.prepend(button, musicButton);
button.addEventListener("click", () => {
  soundOn = !soundOn;
  if (soundOn) unlock();
  button.textContent = soundOn ? "박자 소리 끄기" : "박자 소리 켜기";
  button.setAttribute("aria-pressed", String(soundOn));
  beep();
});
musicButton.addEventListener("click", () => {
  musicOn = !musicOn;
  musicButton.textContent = musicOn ? "BGM 끄기" : "BGM 켜기";
  musicButton.setAttribute("aria-pressed", String(musicOn));
  updateAudio(currentState);
});
document.addEventListener("visibilitychange", () => updateAudio(currentState));
