import { FileText, X, Play, Spinner, Lightning } from "@phosphor-icons/react";

const MB = 1024 * 1024;
const LIMIT = 50 * MB;

const FAMILY = {
  Document: ["txt", "md", "markdown", "rst", "rtf", "pdf", "docx", "pptx", "html", "htm", "xhtml", "eml"],
  Data: ["csv", "tsv", "xlsx", "xlsm", "json", "jsonl", "ndjson", "yaml", "yml", "xml", "svg"],
  Log: ["log"],
  Archive: ["zip"],
  Notebook: ["ipynb"],
};

export function familyOf(name) {
  const ext = name.toLowerCase().split(".").pop();
  if (!name.includes(".")) return "Auto-detect";
  for (const [fam, exts] of Object.entries(FAMILY)) if (exts.includes(ext)) return fam;
  return ["py", "js", "jsx", "ts", "tsx", "go", "rs", "java", "c", "cpp", "cs", "rb", "php", "sql", "sh", "kt", "swift"].includes(ext)
    ? "Code"
    : "Auto-detect";
}

const size = (b) => (b >= MB ? `${(b / MB).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

export default function UploadReview({ files, opts, onRemove, onClear, onStart, busy }) {
  const total = files.reduce((a, f) => a + f.size, 0);
  const over = total > LIMIT;
  return (
    <div className="card-brutal" data-testid="upload-review">
      <div className="flex items-center justify-between px-5 py-3 border-b-2 border-[#0A0A0A] bg-[#0A0A0A] text-white">
        <span className="text-xs font-bold uppercase tracking-wider">
          Review · {files.length} file{files.length > 1 ? "s" : ""} · {size(total)}
        </span>
        <button onClick={onClear} className="text-xs uppercase underline" data-testid="review-clear">Clear (Esc)</button>
      </div>
      <ul className="divide-y-2 divide-[#E5E7EB] max-h-64 overflow-auto">
        {files.map((f, i) => (
          <li key={`${f.name}-${f.size}`} className="flex items-center gap-3 px-5 py-2 text-sm" data-testid={`review-file-${i}`}>
            <FileText size={18} weight="bold" className="text-[#002FA7] shrink-0" />
            <span className="font-bold truncate flex-1">{f.name}</span>
            <span className="text-[10px] uppercase tracking-wider border-2 border-[#0A0A0A] px-1.5">{familyOf(f.name)}</span>
            <span className="tabular-nums text-[#4B5563] w-20 text-right">{size(f.size)}</span>
            <button onClick={() => onRemove(i)} className="p-1 hover:text-[#FF3B30]" data-testid={`review-remove-${i}`} title="Remove">
              <X size={16} weight="bold" />
            </button>
          </li>
        ))}
      </ul>
      <div className="px-5 py-4 border-t-2 border-[#0A0A0A] space-y-3">
        <div className="h-2 border-2 border-[#0A0A0A] overflow-hidden" title="Share of the 50 MB limit">
          <div className={over ? "h-full bg-[#FF3B30]" : "h-full bg-[#002FA7]"} style={{ width: `${Math.min(100, (total / LIMIT) * 100)}%` }} />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs text-[#4B5563]" data-testid="review-settings">
            threshold {opts.threshold.toFixed(2)} · mode {opts.mode} · guard {opts.guard} · order {opts.order} · tables {opts.fold_tables ? "folded" : "as rows"}
            {opts.budget ? ` · budget ${Number(opts.budget).toLocaleString()} tokens` : ""}
            {files.length > 1 && (
              <span className="ml-2 inline-flex items-center gap-1 text-[#002FA7] font-bold">
                <Lightning size={12} weight="fill" /> cross-file dedup on
              </span>
            )}
          </div>
          <button onClick={onStart} disabled={busy || over} className="btn-brutal disabled:opacity-50" data-testid="review-start">
            {busy ? <Spinner size={18} weight="bold" className="animate-spin" /> : <Play size={18} weight="fill" />}
            {over ? "Over 50 MB" : "Start optimization (Enter)"}
          </button>
        </div>
      </div>
    </div>
  );
}
