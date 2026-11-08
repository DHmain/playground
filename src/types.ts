export type Key = "U" | "D" | "L" | "R" | "S";
export type ActionName =
  | "join"
  | "host"
  | "team"
  | "spectate"
  | "shuffle"
  | "count"
  | "start"
  | "start_play"
  | "take_ai"
  | "pause"
  | "reset"
  | "add_ai"
  | "remove_ai"
  | "clear_ai"
  | "input"
  | "test_stage";
export interface Person {
  name: string;
  online: boolean;
  ai: boolean;
  me: boolean;
}
// Stage fields are supplied by the API for their corresponding stage only.
// Renderers are selected by GameState.stage before accessing them.
export interface Team {
  id: number;
  members: Person[];
  score: number;
  pos: number[];
  progress: number;
  finish: number | null;
  feedback: string;
  health: number;
  relay_done: number;
  maze_lap: number;
  maze_start: number[];
  maze_done: number;
  relay_misses: number;
  race_duration: number;
  jump_count: number;
  rope_progress: number;
  completed: boolean;
  jumps: number[];
  started: number;
  status: "waiting" | "active" | "done";
  history: unknown[];
  maze: number[][];
  goal: number[];
  path_length: number;
  runner: string;
  mine: boolean;
  turn_start: number;
  pattern: Key[];
  note_times: number[];
  attempt: number;
  hits: number[];
  bad: boolean;
  rope_pattern: number[];
  beat_index: number;
  successes: number[];
  bpm: number;
  next_bpm: number;
  change_in: number;
  rank: number;
  points: number;
}
export interface GameState {
  game_test: boolean;
  now: number;
  phase: "lobby" | "playing" | "results";
  stage: number;
  start: number;
  limit: number;
  round: number;
  paused: boolean;
  team_count: number;
  teams: Team[];
  active_team: number | null;
  host: boolean;
  host_name: string | null;
  known: boolean;
  my_team: number | null;
  my_slot: number | null;
  lobby: Person[][];
  waiting: Person[];
  rules: {
    relay_notes: number;
    relay_step: number;
    relay_window: number;
    rope_target: number;
    rope_window: number;
    gourd_period: number;
    gourd_hp: number;
  };
}
