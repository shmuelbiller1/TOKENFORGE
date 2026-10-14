import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { ArrowRight } from "@phosphor-icons/react";
import PublicHeader from "@/components/PublicHeader";
import Playground from "@/components/Playground";

const STEPS = [
  ["01", "Parse", "Each file is turned into atomic fragments: lines & sentences for prose, one row per record for CSV/XLSX/JSON/YAML/XML, one line per log entry, blank-line blocks for code. Unknown files are sniffed by their bytes; ZIPs are expanded.",
    "customers.csv  →  \"id: 1041 | city: Berlin | status: shipped\""],
  ["02", "Tokenize", "Every fragment is counted once with the cl100k_base tokenizer (GPT-4 family), so savings are real LLM tokens, not characters.",
    "\"Order 1041 shipped\"  →  4 tokens"],
  ["03", "Exact dedup", "A normalized key (case, punctuation and spacing folded; numbers kept intact; full Unicode) is hashed in a single O(n) pass. Identical keys collapse; every distinct spelling is kept as an original.",
    "\"Hello, world!\" + \"hello world\"  →  1 record ×2"],
  ["04", "MinHash", "Each unique fragment becomes a 128-value MinHash signature over kind-aware shingles: word 1-2-grams for prose & tables, character 5-grams for logs & code. Standalone numbers are masked so lines that differ only by values look alike.",
    "\"user 17 logged in\" ≈ \"user 18 logged in\""],
  ["05", "LSH + verify", "Signatures are banded into locality-sensitive buckets (bands × rows tuned to your threshold), so only likely matches are compared — linear time, no O(n²). Every candidate pair is verified against signature similarity before union-find merges it.",
    "400k fragments → candidate pairs in seconds"],
  ["06", "Resolve", "Same-shape clusters become templates with slots, which keeps every value in the text the LLM sees. Other near-duplicates fold into the longest line only if the Fact Guard allows it, otherwise they stay as separate records.",
    "\"Order {1041|1042|1043} shipped to Berlin\""],
  ["07", "Verify", "A reconstruction map (record, original) is recorded for every input fragment. The engine rebuilds the full input stream from it and checks it is byte-identical before it marks the job lossless.",
    "lossless_verified: true"],
  ["08", "Fold & render", "Rows that share the same columns become one table: column names are written once and columns that never change move into the header. An optional token budget keeps the most repeated records and says what it left out.",
    "[table id|plan; every row: city=Berlin]\n1041|pro\n1042|free"],
];

const GUARANTEES = [
  ["Nothing is dropped", "Every input fragment maps to exactly one record and one stored original. Export the lossless bundle or click “Rebuild original” to get it all back."],
  ["Values stay visible", "Templates write every distinct value into the optimized text. Multi-slot templates keep the values of each row together: 10:{1} user {2} :: 01|5; 02|6."],
  ["Fact Guard", "In the default facts mode, a line holding a number, ID or name the kept line lacks is never hidden. Strict mode applies this to every word. Off folds into the longest line."],
  ["Deterministic", "No LLM, no randomness at runtime. The same input and settings always give the same output, so you can audit and diff results."],
];

const FORMATS = [
  ["Documents", "TXT · MD · RST · RTF · PDF · DOCX · PPTX · HTML · EML"],
  ["Data", "CSV · TSV · XLSX · JSON · JSONL/NDJSON · YAML · XML"],
  ["Logs", ".log, plus any text where most lines start with a timestamp or level"],
  ["Code", "py js ts go rs java c/c++ cs rb php swift kt sql sh … plus .ipynb notebooks"],
  ["Archives", "ZIP: every member is parsed and deduplicated against the others"],
  ["Unknown", "Detected from content: PDF/Office signatures, JSON, JSONL, HTML/XML, email, CSV, logs, code, markdown"],
];

export default function HowItWorks() {
  const { hash } = useLocation();
  useEffect(() => {
    if (hash) document.querySelector(hash)?.scrollIntoView({ behavior: "smooth" });
  }, [hash]);
  return (
    <div className="min-h-screen bg-white" data-testid="how-it-works-page">
      <PublicHeader />

      <section className="max-w-[1300px] mx-auto px-6 pt-14 pb-10">
        <div className="overline mb-3">How it works</div>
        <h1 className="font-head font-black text-4xl sm:text-5xl lg:text-6xl tracking-tighter leading-[0.95] max-w-4xl">
          Fewer tokens. <span className="text-[#002FA7]">Same information.</span> Provably.
        </h1>
        <p className="mt-6 text-base text-[#4B5563] leading-relaxed max-w-2xl">
          TokenForge runs only deterministic algorithms (hashing, MinHash, LSH, union-find, templating), no LLM.
          Paste something below to see each record, the LLM-ready output, and the round-trip check.
        </p>
      </section>

      <section className="max-w-[1300px] mx-auto px-6 pb-16" id="playground">
        <Playground />
      </section>

      <section className="border-y-2 border-[#0A0A0A] bg-[#F9FAFB]">
        <div className="max-w-[1300px] mx-auto px-6 py-16">
          <h2 className="font-head font-black text-3xl tracking-tight mb-10">The pipeline, step by step</h2>
          <ol className="space-y-4" data-testid="pipeline-steps">
            {STEPS.map(([n, title, body, ex]) => (
              <li key={n} className="card-brutal p-6 grid grid-cols-1 md:grid-cols-12 gap-4 items-start">
                <div className="md:col-span-1 font-head font-black text-3xl text-[#002FA7]">{n}</div>
                <div className="md:col-span-6">
                  <h3 className="font-head font-bold text-lg tracking-tight mb-1">{title}</h3>
                  <p className="text-sm text-[#4B5563] leading-relaxed">{body}</p>
                </div>
                <code className="md:col-span-5 block bg-[#0A0A0A] text-white text-xs p-3 leading-relaxed break-words">{ex}</code>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="max-w-[1300px] mx-auto px-6 py-16 grid grid-cols-1 lg:grid-cols-2 gap-12">
        <div>
          <h2 className="font-head font-black text-3xl tracking-tight mb-6">Guarantees</h2>
          <div className="space-y-4">
            {GUARANTEES.map(([t, b]) => (
              <div key={t} className="border-l-4 border-[#002FA7] pl-4">
                <div className="font-head font-bold">{t}</div>
                <p className="text-sm text-[#4B5563] leading-relaxed">{b}</p>
              </div>
            ))}
          </div>
          <p className="text-xs text-[#9CA3AF] mt-6 leading-relaxed">
            Precisely: lossless applies to the fragment stream after parsing. Parsing trims whitespace,
            list bullets and markup, keeps the text of PDFs and Office files (not images or styling), and
            skips fragments shorter than min_length (default 3 characters).
          </p>
        </div>
        <div>
          <h2 className="font-head font-black text-3xl tracking-tight mb-6">Formats</h2>
          <div className="card-brutal overflow-hidden" data-testid="formats-table">
            <table className="w-full text-sm">
              <tbody>
                {FORMATS.map(([k, v]) => (
                  <tr key={k} className="border-b-2 border-[#0A0A0A] last:border-b-0 align-top">
                    <td className="px-4 py-3 font-bold uppercase text-xs tracking-wider w-28">{k}</td>
                    <td className="px-4 py-3 text-[#4B5563]">{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="border-t-2 border-[#0A0A0A] bg-[#0A0A0A] text-white">
        <div className="max-w-[1300px] mx-auto px-6 py-14 flex flex-wrap items-center justify-between gap-6">
          <div>
            <h2 className="font-head font-black text-3xl tracking-tight">Ready for 50 MB files and the API?</h2>
            <p className="text-sm text-[#9CA3AF] mt-2">Create a free account to get multi-file jobs, exports, API keys and the CLI workflow.</p>
          </div>
          <Link to="/register" className="btn-brutal" data-testid="hiw-cta">
            Start free <ArrowRight size={18} weight="bold" />
          </Link>
        </div>
      </section>
    </div>
  );
}
