import type { ActionName, GameState } from "./types";
async function request(
  path: string,
  token: string,
  body?: object,
): Promise<unknown> {
  const response = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: { "Content-Type": "application/json", "X-Player": token },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(4000),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(typeof data.error === "string" ? data.error : "연결 오류");
  return data;
}
export async function fetchState(token: string): Promise<GameState> {
  const state = (await request("/api/state", token)) as GameState;
  if (
    !state ||
    !Array.isArray(state.teams) ||
    !Number.isFinite(state.now) ||
    !["lobby", "tutorial", "playing", "results"].includes(state.phase)
  )
    throw new Error("서버 상태 형식이 잘못되었습니다.");
  return state;
}
export async function postAction(
  token: string,
  action: ActionName,
  data: Record<string, unknown>,
) {
  return (await request("/api/action", token, { action, ...data })) as {
    token?: string;
    ok?: boolean;
  };
}
