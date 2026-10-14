import { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import api from "@/lib/api";
import { Segmented } from "@/components/EngineOptions";

const fmt = (n) => Number(n ?? 0).toLocaleString();

export function useUsage(path) {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get(path, { params: { days } }).then((r) => setData(r.data)).catch(() => setData(null));
  }, [path, days]);
  return { days, setDays, data };
}

export default function UsageChart({ title, usage, testid }) {
  const { days, setDays, data } = usage;
  const t = data?.totals || {};
  return (
    <div className="card-brutal p-6" data-testid={testid}>
      <div className="flex flex-wrap items-end justify-between gap-4 mb-5">
        <div>
          <div className="overline">{title}</div>
          <div className="flex flex-wrap gap-6 mt-2">
            {[
              ["Tokens saved", t.tokens_saved, "text-[#002FA7]"],
              ["Runs", t.requests, ""],
              ["Cache hits", t.cached_hits, "text-[#34C759]"],
            ].map(([k, v, c]) => (
              <div key={k}>
                <div className={`font-head font-black text-3xl tracking-tighter ${c}`} data-testid={`${testid}-${k.toLowerCase().replace(" ", "-")}`}>{fmt(v)}</div>
                <div className="text-[10px] uppercase tracking-wider text-[#9CA3AF]">{k}</div>
              </div>
            ))}
          </div>
        </div>
        <Segmented label="Range" value={String(days)} onChange={(v) => setDays(Number(v))} testid={`${testid}-range`}
          options={[{ value: "7", label: "7d" }, { value: "30", label: "30d" }, { value: "90", label: "90d" }]} />
      </div>
      <div style={{ width: "100%", height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data?.series || []} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#E5E7EB" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="day" tickFormatter={(d) => d.slice(5)} tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: "#4B5563" }} axisLine={{ stroke: "#0A0A0A" }} minTickGap={18} />
            <YAxis yAxisId="t" tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: "#9CA3AF" }} axisLine={{ stroke: "#0A0A0A" }} width={56} />
            <YAxis yAxisId="r" orientation="right" allowDecimals={false} tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: "#FF3B30" }} axisLine={{ stroke: "#0A0A0A" }} width={32} />
            <Tooltip contentStyle={{ border: "2px solid #0A0A0A", borderRadius: 2, fontFamily: "IBM Plex Mono", fontSize: 12 }} formatter={(v, n) => [fmt(v), n]} />
            <Area yAxisId="t" type="stepAfter" dataKey="tokens_saved" name="tokens saved" stroke="#002FA7" strokeWidth={2} fill="#002FA7" fillOpacity={0.15} isAnimationActive={false} />
            <Area yAxisId="r" type="stepAfter" dataKey="requests" name="runs" stroke="#FF3B30" strokeWidth={2} fill="none" isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
