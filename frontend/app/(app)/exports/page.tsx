"use client";

import { useState } from "react";
import { toast } from "sonner";
import { apiSend } from "@/lib/api";

const PRESETS = ["All Leads", "A+", "A", "A+B", "Hot", "Contactable", "Trials", "Customers", "B Leads", "New Leads", "Contacted"];

export default function ExportsPage() {
  const [preset, setPreset] = useState("A+B");
  const [priority, setPriority] = useState("");
  const [salesStatus, setSalesStatus] = useState("");
  const [city, setCity] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ row_count: number; download_url: string; filename: string } | null>(null);

  async function exportCsv(nextPreset = preset) {
    setBusy(true);
    try {
      const data = await apiSend<{ row_count: number; download_url: string; filename: string }>("/leads/export", "POST", {
        preset: nextPreset,
        priority: priority || undefined,
        sales_status: salesStatus || undefined,
        city: city || undefined,
      });
      setResult(data);
      toast.success(`Export ready · ${data.row_count} rows`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Export failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Exports</h1>
        <p className="text-sm text-mist">Download the prospects worth contacting.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {["A+", "A", "A+B", "Hot", "Contactable", "Trials", "Customers"].map((item) => (
          <button key={item} className="btn btn-secondary" disabled={busy} onClick={() => { setPreset(item); exportCsv(item); }}>
            Export {item}
          </button>
        ))}
      </div>
      <div className="card space-y-4 p-6">
        <select className="field" value={preset} onChange={(e) => setPreset(e.target.value)}>
          {PRESETS.map((item) => <option key={item}>{item}</option>)}
        </select>
        <div className="grid gap-3 md:grid-cols-3">
          <select className="field" value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="">Priority</option>
            {["A+", "A", "B", "C"].map((item) => <option key={item}>{item}</option>)}
          </select>
          <select className="field" value={salesStatus} onChange={(e) => setSalesStatus(e.target.value)}>
            <option value="">Sales Status</option>
            {["new", "qualified", "contacted", "replied", "trial", "customer"].map((item) => <option key={item}>{item}</option>)}
          </select>
          <input className="field" placeholder="City" value={city} onChange={(e) => setCity(e.target.value)} />
        </div>
        <button className="btn btn-primary" disabled={busy} onClick={() => exportCsv()}>
          {busy ? "Preparing…" : "Export CSV"}
        </button>
        {result && (
          <div className="rounded-xl border border-white/10 p-4 text-sm">
            Ready: {result.row_count} rows
            <a className="btn btn-secondary ml-3" href={result.download_url}>Download</a>
          </div>
        )}
      </div>
    </div>
  );
}
