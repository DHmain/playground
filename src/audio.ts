let soundOn = false;
let context: AudioContext | undefined;
export function beep() {
  if (!soundOn) return;
  context ??= new AudioContext();
  if (context.state === "suspended") void context.resume();
  const oscillator = context.createOscillator(),
    gain = context.createGain();
  oscillator.connect(gain);
  gain.connect(context.destination);
  gain.gain.value = 0.08;
  oscillator.frequency.value = 700;
  oscillator.start();
  oscillator.stop(context.currentTime + 0.05);
}
const button = document.createElement("button");
button.textContent = "박자 소리 켜기";
button.className = "small";
document.querySelector("header .row")!.prepend(button);
button.onclick = () => {
  soundOn = !soundOn;
  button.textContent = soundOn ? "박자 소리 끄기" : "박자 소리 켜기";
  beep();
};
