import { Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import PublicHeader from "@/components/PublicHeader";
import {
  ArrowRight,
  Flask,
  Terminal,
  Files,
  Stack,
  Cpu,
  ShieldCheck,
  FileText,
  ChartBar,
  Key,
} from "@phosphor-icons/react";

const Stat = ({ value, label, accent }) => (
  <div className="card-brutal p-6">
    <div className={`font-head font-black text-4xl tracking-tighter ${accent || "text-[#0A0A0A]"}`}>
      {value}
    </div>
    <div className="overline mt-2">{label}</div>
  </div>
);

const Feature = ({ icon: Icon, title, body }) => (
  <div className="card-brutal p-6 hover:-translate-y-1 transition-transform duration-200">
    <div className="w-11 h-11 flex items-center justify-center bg-[#002FA7] border-2 border-[#0A0A0A] mb-4">
      <Icon size={22} weight="bold" className="text-white" />
    </div>
    <h3 className="font-head font-bold text-lg tracking-tight mb-2">{title}</h3>
    <p className="text-sm text-[#4B5563] leading-relaxed">{body}</p>
  </div>
);

export default function Landing() {
  const { user } = useAuth();
  const dest = user ? "/app" : "/register";

  return (
    <div className="min-h-screen bg-white">
      <PublicHeader />

      {/* Hero */}
      <section className="max-w-[1300px] mx-auto px-6 pt-16 pb-12 grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
        <div className="md:col-span-7">
          <div className="overline mb-4">LLM Token Ingestion Optimizer</div>
          <h1 className="font-head font-black text-5xl sm:text-6xl tracking-tighter leading-[0.95]">
            Each piece of data,
            <br />
            kept <span className="text-[#002FA7]">exactly once.</span>
          </h1>
          <p className="mt-6 text-base text-[#4B5563] leading-relaxed max-w-xl">
            TokenForge reads documents, spreadsheets, logs, code and archives, collapses every exact and
            near-duplicate fragment with MinHash + LSH, folds repeating patterns into lossless templates,
            and gives you a token-minimized dataset for your LLM. No LLM in the loop. Every original can be
            rebuilt byte-for-byte, and each job checks that it can.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Link to={dest} className="btn-brutal" data-testid="hero-cta">
              Optimize your data <ArrowRight size={18} weight="bold" />
            </Link>
            <Link to="/how-it-works#playground" className="btn-ghost" data-testid="hero-try-live">
              <Flask size={18} weight="bold" /> Try it live, no signup
            </Link>
          </div>
        </div>

        <div className="md:col-span-5 grid grid-cols-2 gap-4">
          <Stat value="↓ 90%" label="Tokens on repetitive data" accent="text-[#002FA7]" />
          <Stat value="O(n)" label="MinHash · LSH" />
          <Stat value="30+" label="Formats + auto-detect" />
          <Stat value="0" label="Fragments lost (verified)" accent="text-[#FF3B30]" />
        </div>
      </section>

      {/* Pipeline strip */}
      <section className="border-y-2 border-[#0A0A0A] bg-[#0A0A0A] text-white">
        <div className="max-w-[1300px] mx-auto px-6 py-5 flex flex-wrap items-center gap-x-6 gap-y-2 font-mono text-sm">
          <span className="text-[#9CA3AF]">PIPELINE //</span>
          {["PARSE", "TOKENIZE", "EXACT DEDUP", "MINHASH·LSH", "TEMPLATE", "FACT GUARD", "VERIFY"].map(
            (s, i) => (
              <span key={s} className="flex items-center gap-2">
                <span className={i === 3 ? "text-[#002FA7]" : "text-white"}>{s}</span>
                {i < 6 && <span className="text-[#9CA3AF]">→</span>}
              </span>
            )
          )}
        </div>
      </section>

      {/* Features */}
      <section className="max-w-[1300px] mx-auto px-6 py-16">
        <h2 className="font-head font-black text-3xl sm:text-4xl tracking-tight mb-10">
          The smart way to cut LLM token cost.
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          <Feature icon={Stack} title="Each fragment, once"
            body="Lines, rows and records are normalized (full Unicode, numbers intact) and hashed in a single pass. Exact duplicates collapse into one record with a count." />
          <Feature icon={Cpu} title="MinHash + LSH near-dup"
            body="Vectorized 128-value signatures and banded LSH find similar fragments in linear time. Every candidate pair is verified before merging." />
          <Feature icon={ChartBar} title="Lossless templates"
            body="“Order 1041/1042/1043 shipped” becomes “Order {1041|1042|1043} shipped”. All values stay in the text the LLM reads, with fewer tokens." />
          <Feature icon={ShieldCheck} title="Fact Guard + verified round-trip"
            body="A line holding a number, ID or name the kept line lacks is never folded away. Each job rebuilds its input from the map and checks the match." />
          <Feature icon={Files} title="Every format, many files"
            body="PDF, DOCX, XLSX, PPTX, CSV, JSON(L), YAML, XML, HTML, Markdown, RTF, email, logs, 40+ code types, ZIP. Files in one upload are deduplicated against each other." />
          <Feature icon={FileText} title="Exports for any pipeline"
            body="Plain or ×count-annotated text, Markdown, JSON, JSONL, CSV, or a lossless bundle you can rebuild offline with the CLI." />
          <Feature icon={Key} title="API keys"
            body="Per-user keys for /v1/optimize (text) and /v1/optimize/file (multipart). Account login for people, keys for machines." />
          <Feature icon={Terminal} title="Open-source CLI"
            body="python cli.py optimize data.zip -f annotated runs the same engine locally, with no server and no database." />
          <Feature icon={Flask} title="Deterministic, no LLM"
            body="Pure algorithms: the same input always gives the same output, nothing is sent to a third party, and every result can be audited."
          />
        </div>
      </section>

      {/* CTA */}
      <section className="border-t-2 border-[#0A0A0A]">
        <div className="max-w-[1300px] mx-auto px-6 py-16 text-center">
          <h2 className="font-head font-black text-4xl sm:text-5xl tracking-tighter">
            Stop paying for duplicate tokens.
          </h2>
          <Link to={dest} className="btn-brutal mt-8 text-base px-8 py-3 inline-flex" data-testid="footer-cta">
            Get started — it&apos;s free <ArrowRight size={20} weight="bold" />
          </Link>
        </div>
      </section>

      <footer className="border-t-2 border-[#0A0A0A] py-6">
        <div className="max-w-[1300px] mx-auto px-6 text-xs text-[#9CA3AF] uppercase tracking-widest">
          TokenForge · Open-source (MIT) pure-algorithm token ingestion optimizer
        </div>
      </footer>
    </div>
  );
}
