import { useState } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { Play, Spinner, Copy, ShieldCheck, Warning } from "@phosphor-icons/react";
import { EngineOptions, KindBadge, RecordText, DEFAULT_OPTS } from "@/components/EngineOptions";
import { useHotkeys } from "@/lib/hotkeys";

export const SAMPLES = {
  logs: `2026-06-01 10:00:01 INFO user 17 logged in from 10.0.0.17
2026-06-01 10:00:02 INFO user 18 logged in from 10.0.0.18
2026-06-01 10:00:05 WARN cache miss for key session:17
2026-06-01 10:00:07 INFO user 21 logged in from 10.0.0.21
2026-06-01 10:00:09 ERROR payment gateway timeout after 30s
2026-06-01 10:00:11 ERROR payment gateway timeout after 30s
2026-06-01 10:00:12 WARN cache miss for key session:21
2026-06-01 10:00:15 INFO healthcheck ok
2026-06-01 10:00:20 INFO healthcheck ok`,
  csv: `id,product,city,status
1041,Widget Pro,Berlin,shipped
1042,Widget Pro,Berlin,shipped
1043,Widget Pro,Berlin,shipped
1044,Widget Mini,Paris,pending
1044,Widget Mini,Paris,pending
1045,Widget Mini,Paris,pending`,
  prose: `TokenForge removes duplicate data before it reaches your LLM.
TokenForge removes duplicate data before it reaches your LLM!
TokenForge removes duplicate data before it ever reaches your LLM context window.
The invoice total is 120 USD for the March billing period.
The invoice total is 125 USD for the March billing period.
Our office is open Monday to Friday.
Our office is open Monday to Friday.`,
  json: `[{"sku":"SKU-1","name":"Lamp","price":19.99,"tags":["home","light"]},
 {"sku":"SKU-2","name":"Lamp","price":21.99,"tags":["home","light"]},
 {"sku":"SKU-3","name":"Lamp","price":23.99,"tags":["home","light"]},
 {"sku":"SKU-1","name":"Lamp","price":19.99,"tags":["home","light"]}]`,
};

const fmt = (n) => Number(n ?? 0).toLocaleString();

function Results({ res }) {
  const [annotated, setAnnotated] = useState(false);
  const s = res.stats;
  const text = annotated ? res.annotated_text : res.optimized_text;
  const copy = async () => {
    await navigator.clipboard.writeText(text);
    toast.success("Copied optimized output");
  };
  return (
    <div className="space-y-6" data-testid="playground-results">
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        {[
          ["Detected", res.detected_kind],
          ["Fragments", `${fmt(s.fragments_in)} → ${fmt(s.unique_concepts)}`],
          ["Tokens", `${fmt(s.tokens_before)} → ${fmt(s.tokens_after)}`],
          ["Saved", `${s.token_reduction_pct}%`],
          ["Tables", fmt(s.tables_folded)],
          ["Time", `${s.elapsed_ms} ms`],
        ].map(([k, v]) => (
          <div key={k} className="card-brutal p-4" data-testid={`pg-stat-${k.toLowerCase()}`}>
            <div className="overline">{k}</div>
            <div className="font-head font-black text-xl tracking-tight mt-1 uppercase">{v}</div>
          </div>
        ))}
      </div>
      <div
        className={`flex items-center gap-2 border-2 px-3 py-2 text-sm font-bold ${
          res.reconstructed_matches ? "border-[#34C759] text-[#34C759]" : "border-[#FF3B30] text-[#FF3B30]"
        }`}
        data-testid="pg-lossless"
      >
        {res.reconstructed_matches ? <ShieldCheck size={18} weight="bold" /> : <Warning size={18} weight="bold" />}
        {res.reconstructed_matches
          ? `Round-trip verified: all ${fmt(s.fragments_in)} original fragments rebuilt byte-for-byte from the map.`
          : "Round-trip mismatch"}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card-brutal overflow-hidden">
          <div className="bg-[#0A0A0A] text-white px-4 py-2 text-xs uppercase tracking-wider font-bold">
            Records · what changed
          </div>
          <ul className="divide-y-2 divide-[#0A0A0A] max-h-[460px] overflow-auto" data-testid="pg-records">
            {res.records.map((r) => (
              <li key={r.id} className="px-4 py-3 text-sm flex gap-3 items-start">
                <span className="font-bold tabular-nums text-[#002FA7] w-10 text-right shrink-0">×{r.count}</span>
                <div className="min-w-0">
                  <KindBadge kind={r.kind} />
                  <div className="mt-1 leading-relaxed"><RecordText text={r.text} /></div>
                  {r.originals.length > 1 && (
                    <div className="text-[11px] text-[#9CA3AF] mt-1">
                      folds {r.originals.length} distinct originals
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="card-brutal overflow-hidden flex flex-col">
          <div className="bg-[#0A0A0A] text-white px-4 py-2 text-xs uppercase tracking-wider font-bold flex justify-between items-center">
            <span>LLM-ready output</span>
            <span className="flex gap-3">
              <button onClick={() => setAnnotated((a) => !a)} className="underline" data-testid="pg-toggle-annotated">
                {annotated ? "plain" : "with ×counts"}
              </button>
              <button onClick={copy} className="inline-flex items-center gap-1 underline" data-testid="pg-copy">
                <Copy size={12} weight="bold" /> copy
              </button>
            </span>
          </div>
          <pre className="p-4 text-xs leading-relaxed whitespace-pre-wrap break-words flex-1 max-h-[460px] overflow-auto" data-testid="pg-output">
            {text}
          </pre>
        </div>
      </div>
    </div>
  );
}

export default function Playground() {
  const [text, setText] = useState(SAMPLES.logs);
  const [opts, setOpts] = useState(DEFAULT_OPTS);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);

  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/playground", { text, ...opts, budget: opts.budget || null });
      setRes(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  useHotkeys({ "mod+enter": () => text.trim() && !busy && run() });

  return (
    <div className="space-y-6" data-testid="playground">
      <div className="card-brutal p-6 space-y-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="overline mr-2">Try a sample:</span>
          {Object.keys(SAMPLES).map((k) => (
            <button key={k} onClick={() => { setText(SAMPLES[k]); setRes(null); }}
              className="btn-ghost py-1 px-3 text-xs" data-testid={`pg-sample-${k}`}>
              {k}
            </button>
          ))}
        </div>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={10}
          className="input-brutal w-full font-mono text-xs leading-relaxed"
          placeholder="Paste anything: logs, CSV, JSON, prose, YAML, HTML, code…"
          data-testid="pg-input"
        />
        <EngineOptions opts={opts} setOpts={setOpts} />
        <button onClick={run} disabled={busy || !text.trim()} className="btn-brutal disabled:opacity-50" data-testid="pg-run">
          {busy ? <Spinner size={18} weight="bold" className="animate-spin" /> : <Play size={18} weight="fill" />}
          Optimize <span className="opacity-60 text-[10px] ml-1">⌘/Ctrl+Enter</span>
        </button>
      </div>
      {res && <Results res={res} />}
    </div>
  );
}
