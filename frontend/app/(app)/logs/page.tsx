"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { apiGet, apiSend } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type LogItem = {
  id: string;
  timestamp?: string;
  type: string;
  action: string;
  campaign_id?: string | null;
  status: string;
  message: string;
};

export default function LogsPage() {
  const [items, setItems] = useState<LogItem[]>([]);
  const [jobs, setJobs] = useState<{ id: string; type: string; status: string; error?: string; created_at?: string }[]>([]);
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (type) params.set("type", type);
    if (status) params.set("status", status);
    apiGet<{ items: LogItem[] }>(`/logs?${params.toString()}`).then((data) => setItems(data.items));
    apiGet<{ id: string; type: string; status: string; error?: string; created_at?: string }[]>("/jobs").then(setJobs).catch(() => undefined);
  }, [type, status]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">System Logs</h1>
        <p className="text-sm text-mist">Discovery, qualification, imports, and campaign events.</p>
      </div>
      <div className="flex gap-3">
        <select className="field max-w-xs" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All types</option>
          {["campaign", "outscraper", "claude", "leads", "import", "job"].map((item) => <option key={item}>{item}</option>)}
        </select>
        <select className="field max-w-xs" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["info", "success", "error"].map((item) => <option key={item}>{item}</option>)}
        </select>
      </div>
      {jobs.some((job) => job.status === "failed") && (
        <div className="card space-y-3 p-5">
          <h2 className="text-sm font-medium">Failed jobs</h2>
          {jobs.filter((job) => job.status === "failed").map((job) => (
            <div key={job.id} className="flex flex-wrap items-center justify-between gap-3 text-sm">
              <div>
                <div>{job.type} · {formatDate(job.created_at)}</div>
                <div className="text-rose-300">{job.error || "Failed"}</div>
              </div>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  if (!confirm("Retry this failed job?")) return;
                  apiSend(`/jobs/${job.id}/retry`, "POST").then(() => toast.success("Retry queued"));
                }}
              >
                Retry
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="card overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/5 text-xs uppercase tracking-wide text-mist">
            <tr>
              {["Timestamp", "Type", "Action", "Campaign", "Status", "Message"].map((col) => (
                <th key={col} className="px-4 py-3 font-medium">{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-t border-white/5">
                <td className="px-4 py-3 text-mist">{item.timestamp ? new Date(item.timestamp).toLocaleString() : formatDate(item.timestamp)}</td>
                <td className="px-4 py-3">{item.type}</td>
                <td className="px-4 py-3">{item.action}</td>
                <td className="px-4 py-3 text-mist">{item.campaign_id ? item.campaign_id.slice(0, 8) : "—"}</td>
                <td className="px-4 py-3">{item.status}</td>
                <td className="px-4 py-3 text-mist">{item.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
