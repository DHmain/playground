const integrated = location.pathname.startsWith("/demos/landing/");
const apiBase = integrated ? "/api/tutorial/landing" : "/api";

const $ = (id) => document.getElementById(id),
  canvas = $("scene"),
  ctx = canvas.getContext("2d");
const client = crypto.randomUUID?.() || Math.random().toString(36).slice(2);
const sources = new Map(),
  pending = new Set();
let state = null,
  connected = false;
const buttons = [...document.querySelectorAll("[data-role]")];
const keys = {
  a: "left",
  arrowleft: "left",
  l: "right",
  arrowright: "right",
  u: "up",
  arrowup: "up",
  d: "down",
  arrowdown: "down",
};
async function post(path, data) {
  const r = await fetch(apiBase + path.replace("/api", ""), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!r.ok) throw Error("요청 실패");
}
function allowed(role) {
  return $("role").value === "all" || $("role").value === role;
}
function held(role) {
  return [...sources.values()].includes(role);
}
function sync(role) {
  if (pending.has(role)) return;
  pending.add(role);
  const pressed = held(role);
  post("/api/input", { client, role, pressed })
    .catch(() => {
      connected = false;
    })
    .finally(() => {
      pending.delete(role);
      if (held(role) !== pressed) sync(role);
    });
}
function press(source, role) {
  if (!allowed(role) || sources.has(source)) return;
  sources.set(source, role);
  sync(role);
}
function release(source) {
  const role = sources.get(source);
  sources.delete(source);
  if (role) sync(role);
}
function clear() {
  const roles = new Set(sources.values());
  sources.clear();
  roles.forEach(sync);
}
buttons.forEach((b) => {
  b.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    b.setPointerCapture(e.pointerId);
    press("p" + e.pointerId, b.dataset.role);
  });
  for (const event of ["pointerup", "pointercancel", "lostpointercapture"])
    b.addEventListener(event, (e) => release("p" + e.pointerId));
});
addEventListener("keydown", (e) => {
  if (e.target.matches("select, input") || e.ctrlKey || e.metaKey || e.altKey)
    return;
  const role = keys[e.key.toLowerCase()];
  if (role) {
    e.preventDefault();
    press("k" + e.code, role);
  }
});
addEventListener("keyup", (e) => release("k" + e.code));
addEventListener("blur", clear);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) clear();
});
$("role").addEventListener("change", () => {
  clear();
  buttons.forEach((b) => (b.hidden = !allowed(b.dataset.role)));
});
$("start").addEventListener("click", async () => {
  clear();
  try {
    await post("/api/start", {});
  } catch {
    $("message").textContent = "서버 연결을 확인하세요.";
  }
});
setInterval(() => new Set(sources.values()).forEach(sync), 180);
async function poll() {
  try {
    const r = await fetch(apiBase + "/state");
    if (!r.ok) throw Error();
    state = await r.json();
    connected = true;
    update();
  } catch {
    connected = false;
    $("message").textContent =
      "서버 연결 끊김 · 조작은 0.65초 이내 자동 해제됩니다.";
  }
  setTimeout(poll, 80);
}
function update() {
  const s = state;
  $("fuel").textContent = s.fuel.toFixed(1) + "%";
  $("throttle").textContent = Math.round(s.throttle * 100) + "%";
  $("speed").textContent = Math.max(0, -s.vy).toFixed(1) + " m/s";
  $("wind").textContent =
    (s.wind >= 0 ? "→ " : "← ") + Math.abs(s.wind).toFixed(1);
  $("time").textContent = Math.max(0, 60 - s.elapsed).toFixed(1) + "초";
  $("message").textContent =
    s.status === "ready"
      ? "시작을 누르면 즉시 낙하합니다."
      : s.status === "playing"
        ? s.stable > 0
          ? "접지 확인 중… 출력을 끄고 안정시키세요."
          : "중앙까지 " +
            Math.abs(s.x).toFixed(1) +
            " m · 고도 " +
            s.y.toFixed(1) +
            " m"
        : s.reason + " · " + s.score + "점";
  buttons.forEach((b) =>
    b.classList.toggle("active", s.active.includes(b.dataset.role)),
  );
}
function draw() {
  ctx.clearRect(0, 0, 1000, 550);
  for (let i = 0; i < 65; i++) {
    ctx.fillStyle = i % 3 ? "#71859c" : "#d4edff";
    ctx.fillRect((i * 137) % 1000, (i * 79) % 460, 2, 2);
  }
  ctx.strokeStyle = "#1c344d";
  for (let x = 0; x <= 1000; x += 77) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, 485);
    ctx.stroke();
  }
  ctx.fillStyle = "#243447";
  ctx.fillRect(0, 490, 1000, 60);
  ctx.fillStyle = "#6bdcbd";
  ctx.fillRect(500 - 7.5 * 7.65, 485, 15 * 7.65, 7);
  ctx.fillStyle = "#e9ffce";
  ctx.fillRect(497, 476, 6, 16);
  ctx.font = "16px system-ui";
  ctx.textAlign = "center";
  ctx.fillText("LANDING ZONE · 중앙 100", 500, 525);
  if (state) {
    const s = state,
      x = 500 + s.x * 7.65,
      y = 475 - s.y * 2.9;
    ctx.save();
    ctx.translate(x, y);
    if (s.status === "crashed") {
      ctx.strokeStyle = "#ff937d";
      ctx.beginPath();
      ctx.arc(0, -22, 38, 0, Math.PI * 2);
      ctx.stroke();
    }
    if (s.throttle > 0 && s.fuel > 0 && s.status === "playing") {
      ctx.fillStyle = "#ffbc69";
      ctx.beginPath();
      ctx.moveTo(-10, -4);
      ctx.lineTo(0, 8 + s.throttle * 34);
      ctx.lineTo(10, -4);
      ctx.fill();
    }
    ctx.fillStyle = "#c5d3dc";
    ctx.fillRect(-19, -55, 38, 48);
    ctx.fillStyle = "#92b4c8";
    ctx.fillRect(-23, -56, 46, 7);
    ctx.fillRect(-23, -13, 46, 7);
    ctx.fillStyle = "#233e59";
    ctx.fillRect(-11, -43, 22, 17);
    ctx.strokeStyle = "#d5e9ef";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(-15, -9);
    ctx.lineTo(-27, 0);
    ctx.lineTo(-34, 0);
    ctx.moveTo(15, -9);
    ctx.lineTo(27, 0);
    ctx.lineTo(34, 0);
    ctx.stroke();
    for (const [role, sign] of [
      ["left", 1],
      ["right", -1],
    ]) {
      if (s.active.includes(role) && s.fuel > 0 && s.status === "playing") {
        ctx.fillStyle = "#76d9ff";
        ctx.beginPath();
        ctx.moveTo(sign * 22, -18);
        ctx.lineTo(sign * 48, -12);
        ctx.lineTo(sign * 22, -7);
        ctx.fill();
      }
    }
    ctx.restore();
    ctx.textAlign = "left";
    ctx.fillStyle = "#bed6e7";
    ctx.fillText("고정 자세 / 회전 없음", 20, 28);
    ctx.textAlign = "right";
    ctx.fillText(connected ? "● 연결됨" : "연결 확인 중", 980, 28);
  }
  requestAnimationFrame(draw);
}
poll();
draw();

if (integrated) {
  document.title = "깡통 착륙 · 협동 튜토리얼";
  document.querySelector(".tag").textContent = "COOPERATION TUTORIAL";
  document.querySelector("footer").textContent =
    "협동 튜토리얼 · 본경기 점수에 반영되지 않습니다. 모두 같은 연습 비행을 공유하며 누구나 재시작할 수 있습니다.";
  const back = document.createElement("a");
  back.href = "/";
  back.textContent = "← 본게임으로 돌아가기";
  back.style.color = "#c5f175";
  document.querySelector("header").append(back);
}
