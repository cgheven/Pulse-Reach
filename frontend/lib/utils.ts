export function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function priorityClass(priority?: string) {
  if (priority === "A+") return "bg-emerald-400/15 text-emerald-200 border-emerald-400/25";
  if (priority === "A") return "bg-emerald-500/12 text-emerald-300 border-emerald-500/20";
  if (priority === "B") return "bg-amber-500/12 text-amber-200 border-amber-500/20";
  if (priority === "C") return "bg-zinc-500/15 text-zinc-400 border-zinc-500/20";
  return "bg-white/5 text-mist border-white/10";
}

export function salesPriorityClass(value?: string) {
  const map: Record<string, string> = {
    Hot: "bg-rose-500/15 text-rose-200 border-rose-500/25",
    High: "bg-emerald-500/12 text-emerald-200 border-emerald-500/20",
    Medium: "bg-amber-500/12 text-amber-200 border-amber-500/20",
    Low: "bg-zinc-500/15 text-zinc-300 border-zinc-500/20",
    Reject: "bg-white/5 text-zinc-500 border-white/10",
  };
  return map[value || ""] || "bg-white/5 text-mist border-white/10";
}

export function statusClass(status?: string) {
  const map: Record<string, string> = {
    new: "bg-sky-500/12 text-sky-300 border-sky-500/20",
    qualified: "bg-violet-500/12 text-violet-300 border-violet-500/20",
    contacted: "bg-blue-500/12 text-blue-300 border-blue-500/20",
    replied: "bg-teal-500/12 text-teal-300 border-teal-500/20",
    trial: "bg-orange-500/12 text-orange-300 border-orange-500/20",
    customer: "bg-emerald-500/12 text-emerald-300 border-emerald-500/20",
    lost: "bg-rose-500/12 text-rose-300 border-rose-500/20",
  };
  return map[status || ""] || "bg-white/5 text-mist border-white/10";
}

export const PROPERTY_TYPES = [
  "Hostel",
  "Student Accommodation",
  "Guest House",
  "Hotel",
  "Co-living",
  "HMO / Shared Accommodation",
  "Boarding House",
  "Other",
];
