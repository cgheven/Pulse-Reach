"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiGet } from "@/lib/api";
import { Skeleton } from "@/components/EmptyState";

type Dashboard = {
  kpis: Record<string, number>;
  charts: {
    by_city: { name: string; value: number }[];
    by_property_type: { name: string; value: number }[];
    by_score: { name: string; value: number }[];
    by_scale: { name: string; value: number }[];
    funnel: { name: string; value: number }[];
    campaign_quality: { name: string; quality_score: number; a_plus: number; a: number; b: number; c: number; hot?: number; contactable?: number; multi_property?: number; aa_plus_rate?: number }[];
    query_performance?: { query: string; total: number; a_plus: number; a: number; b: number; c: number; aa_plus_rate: number }[];
  };
};

const PRIMARY = [
  ["hot_prospects", "Hot", "/leads?sales_priority=Hot", "Best sales-ready opportunities"],
  ["a_plus_leads", "A+", "/leads?priority=A%2B", "Highest-fit operators"],
  ["a_leads", "A prospects", "/leads?priority=A", "Strong PulseHub fit"],
  ["contactable_leads", "Contactable", "/leads?view=contactable", "Phone or email ready"],
  ["multi_property", "Multi-property", "/leads?view=multi_property", "One operator, several sites"],
  ["sales_ready", "Sales-ready", "/leads?view=sales_ready", "Researched and contactable"],
];

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);

  useEffect(() => {
    const load = () => apiGet<Dashboard>("/dashboard").then(setData).catch(() => undefined);
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, []);

  if (!data) {
    return <div className="grid gap-3 md:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>;
  }

  const k = data.kpis;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-mist">Spend time on Hot and A+ first. Click a number to open that list.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {PRIMARY.map(([key, label, href, hint]) => (
          <Link key={key} href={href} className="card p-5 transition hover:border-white/20">
            <div className="text-xs text-mist">{label}</div>
            <div className="mt-2 text-3xl font-semibold">{k[key] ?? 0}</div>
            <div className="mt-2 text-xs text-mist">{hint}</div>
          </Link>
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Total prospects" value={k.total_leads} />
        <Stat label="Decision makers" value={k.decision_makers} />
        <Stat label="Follow-ups today" value={k.today_followups} />
        <Stat label="Overdue follow-ups" value={k.overdue_followups} />
      </div>
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {["new", "contacted", "replied", "trials", "customers", "lost"].map((key) => (
          <Stat key={key} label={key === "trials" ? "Trial" : key} value={k[key]} />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Leads by City" data={data.charts.by_city} />
        <ChartCard title="Leads by Property Type" data={data.charts.by_property_type} />
        <ChartCard title="Lead Score Distribution" data={data.charts.by_score} />
        <ChartCard title="Property Scale" data={data.charts.by_scale} />
        <ChartCard title="Sales Funnel" data={data.charts.funnel} />
        <div className="card p-5">
          <h2 className="mb-4 text-sm text-mist">Campaign Quality</h2>
          <div className="space-y-3 text-sm">
            {(data.charts.campaign_quality || []).map((item) => (
              <div key={item.name} className="rounded-lg border border-white/5 px-3 py-2">
                <div className="flex items-center justify-between">
                  <div className="font-medium">{item.name}</div>
                  <div className="text-lg font-semibold">{item.quality_score}%</div>
                </div>
                <div className="mt-1 text-xs text-mist">
                  A+ {item.a_plus} · A {item.a} · B {item.b} · C {item.c} · Hot {item.hot ?? 0} · Contactable {item.contactable ?? 0}
                </div>
              </div>
            ))}
            {!data.charts.campaign_quality?.length && <div className="text-mist">No campaign quality yet.</div>}
          </div>
        </div>
        <div className="card p-5 lg:col-span-2">
          <h2 className="mb-4 text-sm text-mist">Query Performance</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-[11px] uppercase tracking-wide text-mist">
                <tr>
                  {["Query", "Results", "A+", "A", "B", "C", "A/A+"].map((col) => (
                    <th key={col} className="pb-2 font-medium">{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(data.charts.query_performance || []).map((row) => (
                  <tr key={row.query} className="border-t border-white/5">
                    <td className="py-2">{row.query}</td>
                    <td className="py-2">{row.total}</td>
                    <td className="py-2">{row.a_plus}</td>
                    <td className="py-2">{row.a}</td>
                    <td className="py-2">{row.b}</td>
                    <td className="py-2">{row.c}</td>
                    <td className="py-2">{row.aa_plus_rate}%</td>
                  </tr>
                ))}
                {!data.charts.query_performance?.length && (
                  <tr><td colSpan={7} className="py-4 text-mist">No query yield yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="card px-4 py-3">
      <div className="text-xs capitalize text-mist">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value ?? 0}</div>
    </div>
  );
}

function ChartCard({ title, data }: { title: string; data: { name: string; value: number }[] }) {
  return (
    <div className="card p-5">
      <h2 className="mb-4 text-sm text-mist">{title}</h2>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: "#9aa1ad", fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={64} />
            <YAxis tick={{ fill: "#9aa1ad", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#12141a", border: "1px solid rgba(255,255,255,0.08)" }} />
            <Bar dataKey="value" fill="#5eead4" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
