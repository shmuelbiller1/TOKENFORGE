import { useEffect, useRef, useState } from "react";
import { useHotkeys } from "@/lib/hotkeys";
import ShareDialog from "@/components/ShareDialog";
import { useParams, useNavigate } from "react-router-dom";
import api, { API } from "@/lib/api";
import { toast } from "sonner";
import { BarChart, Bar, XAxis, YAxis, Cell, ResponsiveContainer, Tooltip } from "recharts";
import {
  ArrowLeft,
  DownloadSimple,
  MagnifyingGlass,
  CaretLeft,
  CaretRight,
  Copy,
  ShieldCheck,
  ArrowCounterClockwise,
  ShareNetwork,
  Scissors,
} from "@phosphor-icons/react";
import { KindBadge, RecordText, Segmented } from "@/components/EngineOptions";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString());
const PAGE = 25;

const Kpi = ({ label, value, accent, sub, testid }) => (
  <div className="card-brutal p-5" data-testid={testid}>
    <div className="overline">{label}</div>
    <div className={`font-head font-black text-3xl tracking-tighter mt-1 ${accent || ""}`}>{value}</div>
    {sub && <div className="text-xs text-[#9CA3AF] mt-1">{sub}</div>}
  </div>
);

const EXPORTS = [
  ["txt", "Optimized text (.txt)"],
  ["annotated", "Annotated with ×counts (.txt)"],
  ["md", "Markdown report (.md)"],
  ["json", "Records JSON (.json)"],
  ["jsonl", "Records JSONL (.jsonl)"],
  ["csv", "Records CSV (.csv)"],
  ["bundle", "Lossless bundle + map (.json)"],
];

const STAGES = ["tokenize", "exact", "minhash", "lsh", "resolve", "verify"];

function Timings({ t }) {
  if (!t) return null;
  const total = STAGES.reduce((a, k) => a + (t[k] || 0), 0) || 1;
  const colors = ["#0A0A0A", "#4B5563", "#002FA7", "#3B5BDB", "#FF3B30", "#34C759"];
  return (
    <div data-testid="pipeline-timings">
      <div className="flex h-6 border-2 border-[#0A0A0A] overflow-hidden">
        {STAGES.map((k, i) => (
          <div key={k} style={{ width: `${((t[k] || 0) / total) * 100}%`, background: colors[i] }} title={`${k}: ${t[k]} ms`} />
        ))}
      </div>
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 mt-3">
        {STAGES.map((k, i) => (
          <div key={k} className="text-xs">
            <span className="inline-block w-2.5 h-2.5 mr-1.5 border border-[#0A0A0A]" style={{ background: colors[i] }} />
            <span className="uppercase tracking-wider text-[#4B5563]">{k}</span>
            <div className="font-bold tabular-nums">{t[k] ?? 0} ms</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RecordRow({ f, sources }) {
  return (
    <tr className="border-t-2 border-[#0A0A0A] align-top" data-testid={`fragment-row-${f.id}`}>
      <td className="px-4 py-3 text-right font-bold tabular-nums text-[#002FA7]">{f.count}</td>
      <td className="px-4 py-3"><KindBadge kind={f.kind} /></td>
      <td className="px-4 py-3">
        <div className="leading-relaxed"><RecordText text={f.text} /></div>
        {sources.length > 1 && (
          <div className="text-[10px] uppercase tracking-wider text-[#9CA3AF] mt-1">
            in: {f.sources.map((s) => sources[s]?.name).join(" · ")}
          </div>
        )}
        {f.variant_count > 0 && (
          <details className="mt-2">
            <summary className="cursor-pointer text-xs uppercase tracking-wider text-[#9CA3AF] hover:text-[#002FA7]">
              {f.variant_count} preserved original{f.variant_count > 1 ? "s" : ""}
            </summary>
            <ul className="mt-2 space-y-1 border-l-2 border-[#E5E7EB] pl-3">
              {f.variants.map((v, vi) => (
                <li key={vi} className="text-xs text-[#4B5563] whitespace-pre-wrap">{v}</li>
              ))}
              {f.variant_count > f.variants.length && (
                <li className="text-xs text-[#9CA3AF]">+{f.variant_count - f.variants.length} more in the lossless bundle</li>
              )}
            </ul>
          </details>
        )}
      </td>
      <td className="px-4 py-3 text-right tabular-nums">{f.tokens}</td>
    </tr>
  );
}

export default function JobResult() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [frags, setFrags] = useState({ items: [], total: 0 });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [kind, setKind] = useState("");
  const [exportFmt, setExportFmt] = useState("txt");
  const [shareOpen, setShareOpen] = useState(false);
  const searchRef = useRef(null);

  useEffect(() => {
    api.get(`/jobs/${jobId}`).then((r) => setJob(r.data)).catch(() => navigate("/app"));
  }, [jobId, navigate]);

  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(search);
      setPage(1);
    }, 400);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    api
      .get(`/jobs/${jobId}/fragments`, { params: { page, page_size: PAGE, search: debounced, kind } })
      .then((r) => setFrags(r.data))
      .catch(() => {});
  }, [jobId, page, debounced, kind]);

  const download = (path) => window.open(`${API}/jobs/${jobId}/${path}`, "_blank");

  const copyText = async () => {
    try {
      const { data } = await api.get(`/jobs/${jobId}/export`, { params: { format: "txt" }, responseType: "text" });
      await navigator.clipboard.writeText(data || "");
      toast.success("Optimized text copied to clipboard");
    } catch (e) {
      toast.error("Copy failed");
    }
  };

  const totalPages = Math.max(1, Math.ceil(frags.total / PAGE));
  useHotkeys({
    "/": () => searchRef.current?.focus(),
    c: () => copyText(),
    e: () => download(`export?format=${exportFmt}`),
    r: () => download("reconstruct"),
    s: () => setShareOpen(true),
    arrowleft: () => setPage((p) => Math.max(1, p - 1)),
    arrowright: () => setPage((p) => Math.min(totalPages, p + 1)),
    escape: () => searchRef.current?.blur(),
  }, !!job);

  if (!job) return <div className="text-[#9CA3AF]">Loading…</div>;
  const s = job.stats || {};
  const sources = s.sources || [];
  const chartData = [
    { name: "Before", value: s.tokens_before || 0 },
    { name: "After", value: s.tokens_after || 0 },
  ];

  return (
    <div className="space-y-8" data-testid="job-result">
      <ShareDialog open={shareOpen} onOpenChange={setShareOpen} job={job} onChange={(patch) => setJob((j) => ({ ...j, ...patch }))} />
      <button onClick={() => navigate("/app")} className="btn-ghost py-2 px-3 text-xs" data-testid="back-button">
        <ArrowLeft size={16} weight="bold" /> Back
      </button>

      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="overline mb-1">Result · {job.filename}</div>
          <h1 className="font-head font-black text-4xl tracking-tighter">Token report</h1>
          <div className="flex flex-wrap items-center gap-2 mt-3 text-xs">
            {s.lossless_verified && (
              <span className="inline-flex items-center gap-1 border-2 border-[#34C759] text-[#34C759] font-bold uppercase px-2 py-0.5" data-testid="lossless-badge">
                <ShieldCheck size={14} weight="bold" /> Lossless verified
              </span>
            )}
            {["mode", "guard", "order"].map((k) => (
              <span key={k} className="border-2 border-[#0A0A0A] px-2 py-0.5 uppercase font-bold">
                {k}: {s[k]}
              </span>
            ))}
            <span className="border-2 border-[#0A0A0A] px-2 py-0.5 uppercase font-bold">threshold: {s.threshold}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-3 items-center">
          <button onClick={() => setShareOpen(true)} className="btn-ghost" data-testid="share-button" title="Share (S)">
            <ShareNetwork size={18} weight="bold" /> {job.share_enabled ? "Shared" : "Share"}
          </button>
          <button onClick={copyText} className="btn-ghost" data-testid="copy-text-button" title="Copy (C)">
            <Copy size={18} weight="bold" /> Copy text
          </button>
          <button onClick={() => download("reconstruct")} className="btn-ghost" data-testid="reconstruct-button"
            title="Download every original fragment, rebuilt from the reconstruction map">
            <ArrowCounterClockwise size={18} weight="bold" /> Rebuild original
          </button>
          <div className="flex">
            <select
              value={exportFmt}
              onChange={(e) => setExportFmt(e.target.value)}
              className="input-brutal py-2 text-xs border-r-0 rounded-r-none"
              data-testid="export-format-select"
            >
              {EXPORTS.map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
            <button onClick={() => download(`export?format=${exportFmt}`)} className="btn-brutal" data-testid="export-button">
              <DownloadSimple size={18} weight="bold" /> Export
            </button>
          </div>
        </div>
      </div>

      {s.budget_omitted_records > 0 && (
        <div className="border-2 border-[#B45309] text-[#B45309] px-4 py-3 text-sm flex items-center gap-2" data-testid="budget-notice">
          <Scissors size={18} weight="bold" />
          Token budget {fmt(s.budget)}: {fmt(s.budget_omitted_records)} lower-priority records left out of the text output.
          The full lossless output is {fmt(s.tokens_after_full)} tokens ({s.token_reduction_pct_lossless}% smaller), and the bundle and rebuild still contain everything.
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi testid="kpi-tokens-saved" label="Tokens saved" value={fmt(s.tokens_saved)} accent="text-[#002FA7]" sub={`${s.token_reduction_pct}% smaller`} />
        <Kpi testid="kpi-tokens" label="Tokens before → after" value={fmt(s.tokens_before)} sub={`→ ${fmt(s.tokens_after)} after`} />
        <Kpi testid="kpi-records" label="Fragments → records" value={fmt(s.fragments_in)} accent="text-[#FF3B30]" sub={`→ ${fmt(s.unique_concepts)} records (${s.dup_reduction_pct}% fewer)`} />
        <Kpi testid="kpi-templates" label="Templates · tables" value={`${fmt(s.templates)} · ${fmt(s.tables_folded ?? 0)}`} sub={`${fmt(s.values_folded)} lines in slots · ${fmt(s.rows_in_tables ?? 0)} table rows`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="card-brutal p-6 lg:col-span-2 space-y-6">
          <div>
            <div className="overline mb-4">Token volume · before vs after</div>
            <div style={{ width: "100%", height: 200 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <XAxis dataKey="name" tick={{ fontFamily: "IBM Plex Mono", fontSize: 12, fill: "#0A0A0A" }} axisLine={{ stroke: "#0A0A0A" }} />
                  <YAxis tick={{ fontFamily: "IBM Plex Mono", fontSize: 11, fill: "#9CA3AF" }} axisLine={{ stroke: "#0A0A0A" }} width={60} />
                  <Tooltip cursor={{ fill: "#F3F4F6" }} contentStyle={{ border: "2px solid #0A0A0A", borderRadius: 2, fontFamily: "IBM Plex Mono" }} />
                  <Bar dataKey="value" stroke="#0A0A0A" strokeWidth={2} maxBarSize={140} isAnimationActive={false}>
                    <Cell fill="#FF3B30" />
                    <Cell fill="#002FA7" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div>
            <div className="overline mb-3">Pipeline · {s.elapsed_ms} ms total</div>
            <Timings t={s.timings_ms} />
          </div>
        </div>
        <div className="card-brutal p-6">
          <div className="overline mb-4">Breakdown</div>
          <dl className="space-y-3 text-sm" data-testid="breakdown">
            {[
              ["Input fragments", fmt(s.fragments_in)],
              ["Exact duplicates", fmt(s.exact_duplicates)],
              ["After exact dedup", fmt(s.after_exact_dedup)],
              ["Near-dup clusters", fmt(s.near_dup_clusters)],
              ["Templates built", fmt(s.templates)],
              ["Guard splits (kept apart)", fmt(s.guard_splits)],
              ["Cross-file records", fmt(s.cross_source_records)],
              ["Final records", fmt(s.unique_concepts)],
              ["Raw characters", fmt(s.raw_chars)],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-dashed border-[#E5E7EB] pb-2">
                <dt className="text-[#4B5563]">{k}</dt>
                <dd className="font-bold tabular-nums">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {sources.length > 0 && (
        <div className="card-brutal overflow-hidden" data-testid="sources-table">
          <table className="w-full text-sm">
            <thead className="bg-[#0A0A0A] text-white">
              <tr className="text-left uppercase text-xs tracking-wider">
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Detected as</th>
                <th className="px-4 py-3 text-right">Fragments</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((src, i) => (
                <tr key={i} className="border-t-2 border-[#0A0A0A]">
                  <td className="px-4 py-2 font-bold break-all">{src.name}</td>
                  <td className="px-4 py-2 uppercase text-xs tracking-wider">{src.kind}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{fmt(src.fragments)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {s.parse_errors?.length > 0 && (
            <div className="border-t-2 border-[#0A0A0A] px-4 py-2 text-xs text-[#FF3B30]" data-testid="parse-errors">
              Skipped: {s.parse_errors.join(" · ")}
            </div>
          )}
        </div>
      )}

      <div>
        <div className="flex items-end justify-between mb-4 flex-wrap gap-4">
          <div>
            <h2 className="font-head font-bold text-xl tracking-tight mb-3">Optimized dataset</h2>
            <Segmented
              label="Filter"
              value={kind}
              onChange={(v) => { setKind(v); setPage(1); }}
              testid="kind-filter"
              options={[
                { value: "", label: "All" },
                { value: "template", label: "Templates" },
                { value: "near_duplicate", label: "Near-dup" },
                { value: "duplicate", label: "Duplicate" },
                { value: "unique", label: "Unique" },
              ]}
            />
          </div>
          <div className="relative">
            <MagnifyingGlass size={16} weight="bold" className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search records… (/)"
              ref={searchRef} className="input-brutal pl-9 w-72" data-testid="fragment-search" />
          </div>
        </div>

        <div className="card-brutal overflow-x-auto" data-testid="fragments-table">
          <table className="w-full text-sm">
            <thead className="bg-[#0A0A0A] text-white">
              <tr className="text-left uppercase text-xs tracking-wider">
                <th className="px-4 py-3 w-16 text-right">×</th>
                <th className="px-4 py-3 w-28">Type</th>
                <th className="px-4 py-3">Record</th>
                <th className="px-4 py-3 w-20 text-right">Tokens</th>
              </tr>
            </thead>
            <tbody>
              {frags.items.map((f, i) => <RecordRow key={f.id ?? i} f={{ ...f, id: f.id ?? i, sources: f.sources || [] }} sources={sources} />)}
              {frags.items.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-10 text-center text-[#9CA3AF]">No records match.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between mt-4">
          <div className="text-xs text-[#9CA3AF] uppercase tracking-wider" data-testid="records-total">{fmt(frags.total)} records</div>
          <div className="flex items-center gap-3">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="btn-ghost py-1.5 px-2 disabled:opacity-40" data-testid="prev-page">
              <CaretLeft size={16} weight="bold" />
            </button>
            <span className="text-sm font-bold tabular-nums">{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} className="btn-ghost py-1.5 px-2 disabled:opacity-40" data-testid="next-page">
              <CaretRight size={16} weight="bold" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
