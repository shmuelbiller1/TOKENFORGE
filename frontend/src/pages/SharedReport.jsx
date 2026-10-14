import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ShieldCheck, ArrowRight, Copy } from "@phosphor-icons/react";
import { toast } from "sonner";
import api from "@/lib/api";
import PublicHeader from "@/components/PublicHeader";
import { KindBadge, RecordText } from "@/components/EngineOptions";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString());

export default function SharedReport() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get(`/share/${token}`).then((r) => setData(r.data)).catch((e) => setError(e.response?.data?.detail || "Report not found"));
  }, [token]);

  const copyLink = async () => {
    await navigator.clipboard.writeText(window.location.href);
    toast.success("Link copied");
  };

  return (
    <div className="min-h-screen bg-white" data-testid="shared-report-page">
      <PublicHeader />
      <main className="max-w-[1100px] mx-auto px-6 py-12 space-y-8">
        {error && (
          <div className="card-brutal p-10 text-center" data-testid="shared-error">
            <h1 className="font-head font-black text-3xl tracking-tight">{error}</h1>
            <Link to="/how-it-works#playground" className="btn-brutal mt-6 inline-flex">Try TokenForge yourself</Link>
          </div>
        )}
        {!data && !error && <div className="text-[#9CA3AF]">Loading…</div>}
        {data && (
          <>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <div className="overline mb-1">Shared token report · {data.filename}{data.file_count > 1 ? ` (${data.file_count} files)` : ""}</div>
                <h1 className="font-head font-black text-4xl sm:text-5xl tracking-tighter" data-testid="shared-headline">
                  {fmt(data.stats.tokens_before)} → <span className="text-[#002FA7]">{fmt(data.stats.tokens_after)}</span> tokens
                </h1>
                <p className="text-sm text-[#4B5563] mt-2">
                  {data.stats.token_reduction_pct}% fewer tokens · {fmt(data.stats.fragments_in)} fragments → {fmt(data.stats.unique_concepts)} records · {data.stats.elapsed_ms} ms
                </p>
              </div>
              <div className="flex gap-3 items-center">
                {data.stats.lossless_verified && (
                  <span className="inline-flex items-center gap-1 border-2 border-[#34C759] text-[#34C759] font-bold uppercase px-2 py-1 text-xs" data-testid="shared-lossless">
                    <ShieldCheck size={14} weight="bold" /> Lossless verified
                  </span>
                )}
                <button onClick={copyLink} className="btn-ghost text-xs" data-testid="shared-copy-link"><Copy size={16} weight="bold" /> Copy link</button>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="shared-stats">
              {[
                ["Tokens saved", fmt(data.stats.tokens_saved)],
                ["Exact duplicates", fmt(data.stats.exact_duplicates)],
                ["Templates", fmt(data.stats.templates)],
                ["Tables folded", fmt(data.stats.tables_folded)],
              ].map(([k, v]) => (
                <div key={k} className="card-brutal p-5">
                  <div className="overline">{k}</div>
                  <div className="font-head font-black text-3xl tracking-tighter mt-1">{v}</div>
                </div>
              ))}
            </div>

            <div className="card-brutal overflow-hidden">
              <div className="bg-[#0A0A0A] text-white px-4 py-2 text-xs uppercase tracking-wider font-bold">Optimized output · preview</div>
              <pre className="p-4 text-xs leading-relaxed whitespace-pre-wrap break-words max-h-[420px] overflow-auto" data-testid="shared-preview">
                {data.preview_text}{data.preview_truncated ? "\n…" : ""}
              </pre>
            </div>

            <div className="card-brutal overflow-hidden">
              <table className="w-full text-sm">
                <tbody>
                  {data.preview_records.map((r) => (
                    <tr key={r.id} className="border-b-2 border-[#0A0A0A] last:border-b-0 align-top">
                      <td className="px-4 py-2 w-14 text-right font-bold text-[#002FA7]">×{r.count}</td>
                      <td className="px-4 py-2 w-28"><KindBadge kind={r.kind} /></td>
                      <td className="px-4 py-2"><RecordText text={r.text} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="bg-[#0A0A0A] text-white p-8 flex flex-wrap items-center justify-between gap-6" data-testid="shared-cta">
              <div>
                <h2 className="font-head font-black text-2xl tracking-tight">Cut your own LLM token bill</h2>
                <p className="text-sm text-[#9CA3AF] mt-1">Free and open source. Deterministic, with no LLM in the loop. Works on PDFs, spreadsheets, logs, code and ZIPs.</p>
              </div>
              <div className="flex gap-3">
                <Link to="/how-it-works#playground" className="btn-ghost bg-white text-[#0A0A0A]" data-testid="shared-try">Try it live</Link>
                <Link to="/register" className="btn-brutal" data-testid="shared-signup">Start free <ArrowRight size={18} weight="bold" /></Link>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
