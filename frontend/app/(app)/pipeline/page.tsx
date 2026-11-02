"use client";

import { DndContext, DragEndEvent, useDraggable, useDroppable } from "@dnd-kit/core";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { apiGet, apiSend } from "@/lib/api";
import { PriorityBadge } from "@/components/Badge";
import { formatDate } from "@/lib/utils";

const COLUMNS = ["new", "qualified", "contacted", "replied", "trial", "customer", "lost"];

type Card = {
  id: string;
  name: string;
  property_type: string;
  city: string;
  priority: string;
  next_followup_at?: string | null;
  sales_status: string;
};

export default function PipelinePage() {
  const [columns, setColumns] = useState<Record<string, Card[]>>({});

  async function load() {
    const data = await apiGet<{ columns: Record<string, Card[]> }>("/pipeline");
    setColumns(data.columns);
  }

  useEffect(() => {
    load().catch((error) => toast.error(error.message));
  }, []);

  async function onDragEnd(event: DragEndEvent) {
    const leadId = String(event.active.id);
    const over = event.over?.id ? String(event.over.id) : "";
    if (!COLUMNS.includes(over)) return;
    await apiSend(`/leads/${leadId}/status/${over}`, "POST");
    await load();
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Sales Pipeline</h1>
        <p className="text-sm text-mist">Drag a card to update status immediately.</p>
      </div>
      <DndContext onDragEnd={onDragEnd}>
        <div className="flex gap-4 overflow-x-auto pb-6">
          {COLUMNS.map((status) => (
            <Column key={status} status={status} cards={columns[status] || []} />
          ))}
        </div>
      </DndContext>
    </div>
  );
}

function Column({ status, cards }: { status: string; cards: Card[] }) {
  const { setNodeRef } = useDroppable({ id: status });
  return (
    <section ref={setNodeRef} className="card min-w-[260px] flex-1 p-3">
      <div className="mb-3 flex items-center justify-between px-1">
        <h2 className="text-sm font-medium capitalize">{status}</h2>
        <span className="text-xs text-mist">{cards.length}</span>
      </div>
      <div className="space-y-3">
        {cards.map((card) => (
          <PipelineCard key={card.id} card={card} />
        ))}
      </div>
    </section>
  );
}

function PipelineCard({ card }: { card: Card }) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id: card.id });
  const style = transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined;
  return (
    <article ref={setNodeRef} style={style} {...listeners} {...attributes} className="rounded-xl border border-white/10 bg-ink-950 p-3">
      <div className="font-medium">{card.name}</div>
      <div className="mt-1 text-xs text-mist">{card.property_type || "—"} · {card.city || "—"}</div>
      <div className="mt-2 flex items-center justify-between">
        <PriorityBadge value={card.priority} />
        <span className="text-xs text-mist">{formatDate(card.next_followup_at)}</span>
      </div>
    </article>
  );
}
