import { Fragment } from "react";

export const Segmented = ({ label, hint, value, options, onChange, testid }) => (
  <div data-testid={testid}>
    <div className="overline mb-2">{label}</div>
    <div className="inline-flex border-2 border-[#0A0A0A] rounded-sm overflow-hidden flex-wrap">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          title={o.title}
          data-testid={`${testid}-${o.value}`}
          className={`px-2.5 py-1.5 text-[11px] font-bold uppercase tracking-wider border-r-2 last:border-r-0 border-[#0A0A0A] transition-colors duration-150 ${
            value === o.value ? "bg-[#0A0A0A] text-white" : "bg-white hover:bg-[#F3F4F6]"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
    {hint && <p className="text-xs text-[#4B5563] mt-2 leading-relaxed">{hint}</p>}
  </div>
);

export const MODE_OPTIONS = [
  { value: "auto", label: "Auto", title: "Detect per file" },
  { value: "prose", label: "Prose" },
  { value: "tabular", label: "Tabular" },
  { value: "log", label: "Logs" },
  { value: "code", label: "Code" },
];
export const GUARD_OPTIONS = [
  { value: "facts", label: "Facts" },
  { value: "strict", label: "Strict" },
  { value: "off", label: "Off" },
];
export const ORDER_OPTIONS = [
  { value: "original", label: "Original" },
  { value: "frequency", label: "Frequency" },
];

const GUARD_HINT = {
  facts: "A near-duplicate only folds if every number, ID and name it holds is already in the kept line.",
  strict: "A near-duplicate only folds if every single word is already in the kept line. Safest.",
  off: "Fold all near-duplicates into the longest line. Maximum compression; variants kept in the map.",
};

export function EngineOptions({ opts, setOpts, compact }) {
  const set = (k) => (v) => setOpts((o) => ({ ...o, [k]: v }));
  return (
    <div className={`grid gap-6 ${compact ? "grid-cols-1 md:grid-cols-2" : "grid-cols-1 md:grid-cols-2 xl:grid-cols-4"}`}>
      <div data-testid="threshold-control">
        <div className="overline mb-2">Near-dup threshold</div>
        <div className="flex items-center gap-3">
          <input
            type="range"
            min={0.5}
            max={1}
            step={0.01}
            value={opts.threshold}
            onChange={(e) => set("threshold")(parseFloat(e.target.value))}
            className="w-40 accent-[#002FA7]"
            data-testid="threshold-slider"
          />
          <span className="font-head font-black text-2xl tabular-nums" data-testid="threshold-value">
            {opts.threshold.toFixed(2)}
          </span>
        </div>
        <p className="text-xs text-[#4B5563] mt-2">1.00 = exact duplicates only. Lower = more aggressive.</p>
      </div>
      <Segmented label="Content mode" value={opts.mode} options={MODE_OPTIONS} onChange={set("mode")} testid="mode-select"
        hint="Auto picks word shingles for prose/tables and character shingles for logs/code." />
      <Segmented label="Fact guard" value={opts.guard} options={GUARD_OPTIONS} onChange={set("guard")} testid="guard-select"
        hint={GUARD_HINT[opts.guard]} />
      <Segmented label="Output order" value={opts.order} options={ORDER_OPTIONS} onChange={set("order")} testid="order-select"
        hint={opts.order === "original" ? "Keeps the reading order of the source." : "Most repeated first."} />
    </div>
  );
}

export function RecordText({ text }) {
  const parts = text.split(/(\{[^{}]*\})/g);
  return (
    <span className="whitespace-pre-wrap break-words">
      {parts.map((p, i) =>
        p.startsWith("{") && p.endsWith("}") ? (
          <span key={i} className="bg-[#002FA7]/10 text-[#002FA7] font-bold px-0.5">{p}</span>
        ) : (
          <Fragment key={i}>{p}</Fragment>
        )
      )}
    </span>
  );
}

const KIND_STYLE = {
  template: "text-[#002FA7] border-[#002FA7]",
  near_duplicate: "text-[#B45309] border-[#B45309]",
  duplicate: "text-[#FF3B30] border-[#FF3B30]",
  unique: "text-[#4B5563] border-[#9CA3AF]",
};

export const KindBadge = ({ kind }) => (
  <span className={`inline-block text-[10px] font-bold uppercase tracking-wider border-2 px-1.5 py-0.5 rounded-sm whitespace-nowrap ${KIND_STYLE[kind] || KIND_STYLE.unique}`}>
    {(kind || "unique").replace("_", "-")}
  </span>
);
