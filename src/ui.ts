import morphdom from "morphdom";
import type { Key } from "./types";
export const arrows: Record<string, string> = {
  U: "↑",
  D: "↓",
  L: "←",
  R: "→",
  S: "SPACE",
} satisfies Record<Key, string>;
export function element<T extends HTMLElement = HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (!found) throw new Error(`Missing element: ${id}`);
  return found as T;
}
export const app = element("app");
export const e = (value: unknown) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );
let toastTimer: ReturnType<typeof setTimeout>;
export function toast(message: string) {
  const node = element("toast");
  node.textContent = message;
  node.style.display = "block";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (node.style.display = "none"), 4000);
}
export function mount(html: string) {
  morphdom(app, `<div id="app">${html}</div>`, {
    childrenOnly: true,
    onBeforeElUpdated(from, to) {
      if (from instanceof HTMLInputElement && from === document.activeElement)
        to.setAttribute("value", from.value);
      return !from.isEqualNode(to);
    },
  });
}
