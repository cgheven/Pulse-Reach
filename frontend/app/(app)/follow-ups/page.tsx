"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { apiGet, apiSend } from "@/lib/api";
import { PriorityBadge, SalesPriorityBadge, StatusBadge } from "@/components/Badge";
import { EmptyState } from "@/components/EmptyState";
import { formatDate } from "@/lib/utils";

type Item = {
  id: string;
  name: string;
  business?: string;
  status: string;
  priority: string;
  sales_priority?: string;
  decision_maker_name?: string;
  due_at?: string | null;
  notes: string;
};

export default function FollowUpsPage() {
  const [data, setData] = useState<{ today: Item[]; overdue: Item[]; upcoming: Item[] }>({ today: [], overdue: [], upcoming: [] });

  async function load() {
    setData(await apiGet( "/followups"));
  }

  useEffect(() => {
    load().catch((error) => toast.error(error.message));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Follow-ups</h1>
        <p className="text-sm text-mist">Today, overdue, and upcoming outreach.</p>
      </div>
      <Section title="Today" items={data.today} onChange={load} />
      <Section title="Overdue" items={data.overdue} onChange={load} />
      <Section title="Upcoming" items={data.upcoming} onChange={load} />
    </div>
  );
}

function Section({ title, items, onChange }: { title: string; items: Item[]; onChange: () => void }) {
  return (
    <section className="card p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-medium">{title}</h2>
        <span className="text-sm text-mist">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <EmptyState title={`No ${title.toLowerCase()} follow-ups`} body="Set a next follow-up date from a lead to see it here." />
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <article key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 px-4 py-3">
              <div>
                <div className="font-medium">{item.business || item.name}</div>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-mist">
                  <StatusBadge value={item.status} />
                  <PriorityBadge value={item.priority} />
                  <SalesPriorityBadge value={item.sales_priority} />
                  {item.decision_maker_name && <span>{item.decision_maker_name}</span>}
                  <span>{formatDate(item.due_at)}</span>
                </div>
                {item.notes && <p className="mt-2 max-w-xl text-sm text-mist">{item.notes}</p>}
              </div>
              <div className="flex gap-2">
                <button className="btn btn-secondary" onClick={() => apiSend(`/followups/${item.id}/complete`, "POST").then(onChange)}>
                  Complete
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={async () => {
                    const next = window.prompt("Reschedule to (YYYY-MM-DD)");
                    if (!next) return;
                    await apiSend(`/followups/${item.id}/reschedule`, "POST", { due_at: new Date(next).toISOString() });
                    onChange();
                  }}
                >
                  Reschedule
                </button>
                <a className="btn btn-secondary" href={`/leads/classic?open=${item.id}`}>Open Lead</a>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
