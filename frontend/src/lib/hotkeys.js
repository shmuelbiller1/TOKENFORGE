import { useEffect, useRef } from "react";

const isTyping = (el) =>
  el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);

const keyName = (e) => {
  const k = e.key.toLowerCase();
  const mod = e.metaKey || e.ctrlKey ? "mod+" : "";
  return mod + (k === " " ? "space" : k);
};

// bindings: { "u": fn, "mod+enter": fn, "g d": fn, "?": fn }. Plain keys are ignored while typing.
export function useHotkeys(bindings, enabled = true) {
  const ref = useRef(bindings);
  ref.current = bindings;
  useEffect(() => {
    if (!enabled) return undefined;
    let prefix = null;
    let timer = null;
    const onKey = (e) => {
      const name = keyName(e);
      const typing = isTyping(e.target);
      if (typing && !name.startsWith("mod+") && name !== "escape") return;
      const map = ref.current;
      const seq = prefix ? `${prefix} ${name}` : null;
      if (seq && map[seq]) {
        e.preventDefault();
        prefix = null;
        map[seq](e);
        return;
      }
      if (!typing && Object.keys(map).some((k) => k.startsWith(`${name} `))) {
        prefix = name;
        clearTimeout(timer);
        timer = setTimeout(() => { prefix = null; }, 900);
        return;
      }
      prefix = null;
      if (map[name]) {
        e.preventDefault();
        map[name](e);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      clearTimeout(timer);
    };
  }, [enabled]);
}

export const SHORTCUTS = [
  ["Anywhere", [["?", "Show this list"], ["g d", "Go to dashboard"], ["g k", "Go to API keys"], ["g h", "Go to How it works"], ["g a", "Go to admin (owner)"]]],
  ["Dashboard", [["u", "Pick files to upload"], ["Enter", "Start the reviewed upload"], ["Esc", "Clear the review list"]]],
  ["Result", [["/", "Search records"], ["c", "Copy optimized text"], ["e", "Export in the selected format"], ["r", "Rebuild the original"], ["s", "Share link"], ["← →", "Previous / next page"]]],
  ["Playground", [["⌘/Ctrl + Enter", "Run the optimizer"]]],
];
