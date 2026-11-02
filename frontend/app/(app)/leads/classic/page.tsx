"use client";

import { useEffect, useMemo, useState } from "react";
import { SlidersHorizontal, X } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiSend } from "@/lib/api";
import { PriorityBadge, SalesPriorityBadge, StatusBadge } from "@/components/Badge";
import { EmptyState, Skeleton } from "@/components/EmptyState";
import { PROPERTY_TYPES, cx, formatDate } from "@/lib/utils";

type Lead = {
  id: string;
  name: string;
  property_type: string;
  source_category?: string;
  city: string;
  country: string;
  website: string;
  email: string;
  phone: string;
  address: string;
  postal_code: string;
  google_maps_url: string;
  linkedin: string;
  facebook: string;
  instagram: string;
  rating?: number | null;
  reviews?: number | null;
  query: string;
  priority: string;
  estimated_property_count: string;
  estimated_bed_count?: string;
  independent_operator: string;
  ideal_customer: string;
  claude_reason: string;
  fit_summary?: string;
  overall_score?: number | null;
  icp_score?: number | null;
  opportunity_score?: number | null;
  contactability_score?: number | null;
  data_quality_score?: number | null;
  sales_priority?: string;
  recommended_next_action?: string;
  research_status?: string;
  score_breakdown?: { icp?: string[]; opportunity?: string[]; contactability?: string[] };
  multi_property_signal?: boolean;
  multi_property_confidence?: string;
  multi_property_evidence?: string;
  scale_confidence?: string;
  locations?: { id: string; name: string; city: string; address: string; google_maps_url: string }[];
  sales_account?: { company_name: string; location_count: number; grouping_status: string } | null;
  current_software?: string;
  decision_maker_name?: string;
  decision_maker_role?: string;
  decision_maker_email?: string;
  decision_maker_linkedin?: string;
  company_name?: string;
  location_count?: number;
  grouping_status?: string;
  needs_review?: boolean;
  review_reason?: string;
  sales_status: string;
  assigned_to?: string | null;
  last_contacted_at?: string | null;
  next_followup_at?: string | null;
  notes: string;
  evidence?: { evidence_type: string; evidence_source: string; evidence_text: string; evidence_url: string }[];
  activity?: { action: string; from_status?: string; to_status?: string; created_at?: string | null }[];
};

type Filters = typeof EMPTY_FILTERS;

const EMPTY_FILTERS = {
  search: "",
  priority: "",
  sales_status: "",
  property_type: "",
  city: "",
  country: "",
  campaign_id: "",
  qualification_status: "",
  view: "hot",
  has_email: "",
  has_phone: "",
  has_website: "",
  has_decision_maker: "",
  multi_property: "",
  estimated_properties: "",
  current_software: "",
  min_score: "",
  sales_priority: "",
  research_status: "",
  min_contactability: "",
  sort: "overall_score",
  direction: "desc",
};

const VIEWS = [
  { id: "hot", name: "Best to contact", hint: "Highest commercial value first", filters: { view: "hot" } },
  { id: "qualified", name: "Qualified", hint: "A+, A, and B", filters: { view: "", qualification_status: "qualified" } },
  { id: "all", name: "All leads", hint: "Including rejected", filters: { view: "", qualification_status: "" } },
  { id: "review", name: "Needs review", hint: "Uncertain AI results", filters: { view: "needs_review" } },
  { id: "rejected", name: "Rejected", hint: "Not a PulseHub fit", filters: { view: "", priority: "C" } },
];

const SMART = [
  { name: "🔥 Hot", filters: { sales_priority: "Hot" } },
  { name: "⭐ A+", filters: { priority: "A+" } },
  { name: "🎯 Multi-property", filters: { view: "multi_property" } },
  { name: "📧 Contactable", filters: { view: "contactable" } },
  { name: "🏢 2–10 properties", filters: { view: "scale_2_10" } },
  { name: "🏠 Student", filters: { property_type: "Student Accommodation" } },
  { name: "🏨 Hostels", filters: { property_type: "Hostel" } },
  { name: "🏘 HMO", filters: { property_type: "HMO / Shared Accommodation" } },
  { name: "🌐 Missing DM", filters: { view: "missing_dm" } },
  { name: "🔎 Needs research", filters: { view: "needs_research" } },
  { name: "⚠ Needs review", filters: { view: "needs_review" } },
  { name: "❌ Rejected", filters: { priority: "C" } },
];

const COLUMN_DEFS = [
  { id: "type", label: "Type" },
  { id: "city", label: "City" },
  { id: "score", label: "Score" },
  { id: "priority", label: "Priority" },
  { id: "scale", label: "Scale" },
  { id: "opportunity", label: "Opportunity" },
  { id: "contactability", label: "Contactability" },
  { id: "decision_maker", label: "Decision maker" },
  { id: "email", label: "Email" },
  { id: "phone", label: "Phone" },
  { id: "status", label: "Status" },
] as const;

const DEFAULT_COLUMNS = ["type", "city", "score", "priority", "scale", "opportunity", "contactability", "decision_maker", "email", "phone", "status"];

const CHIP_LABELS: Record<string, string> = {
  search: "Search",
  priority: "Priority",
  sales_status: "Status",
  property_type: "Type",
  city: "City",
  country: "Country",
  campaign_id: "Campaign",
  qualification_status: "Qualification",
  view: "View",
  has_email: "Has email",
  has_phone: "Has phone",
  has_website: "Has website",
  has_decision_maker: "Has decision maker",
  multi_property: "Multi-property",
  estimated_properties: "Properties",
  min_score: "Score",
  sales_priority: "Sales priority",
  research_status: "Research",
  min_contactability: "Contactability",
  current_software: "Software",
};

const VIEW_VALUES: Record<string, string> = {
  hot: "Best to contact",
  multi_property: "Multi-property",
  contactable: "Contactable",
  scale_2_10: "2–10 properties",
  missing_dm: "Missing decision maker",
  needs_review: "Needs review",
};

export default function LeadsPage() {
  const [items, setItems] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string[]>([]);
  const [active, setActive] = useState<Lead | null>(null);
  const [campaigns, setCampaigns] = useState<{ id: string; name: string }[]>([]);
  const [facets, setFacets] = useState<{ cities: string[] }>({ cities: [] });
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [viewId, setViewId] = useState("hot");
  const [searchDraft, setSearchDraft] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [showColumns, setShowColumns] = useState(false);
  const [columns, setColumns] = useState<string[]>(DEFAULT_COLUMNS);

  const query = useMemo(() => {
    const params = new URLSearchParams();
    Object.entries({ ...filters, page: String(page), page_size: String(pageSize) }).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    return params.toString();
  }, [filters, page, pageSize]);

  async function load() {
    setLoading(true);
    const data = await apiGet<{ items: Lead[]; total: number; facets: { cities: string[] } }>(`/leads?${query}`);
    setItems(data.items);
    setTotal(data.total);
    setFacets(data.facets);
    setLoading(false);
  }

  useEffect(() => {
    load().catch((error) => toast.error(error.message));
  }, [query]);

  useEffect(() => {
    apiGet<{ id: string; name: string }[]>("/campaigns").then(setCampaigns).catch(() => undefined);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requested = [...params.keys()].filter((key) => key !== "open");
    const next = { ...EMPTY_FILTERS, view: requested.length ? "" : "hot" };
    (Object.keys(EMPTY_FILTERS) as Array<keyof Filters>).forEach((key) => {
      const value = params.get(key);
      if (value) next[key] = value;
    });
    if (next.view === "needs_review") setViewId("review");
    else if (next.priority === "C" && !next.view) setViewId("rejected");
    else if (next.qualification_status === "qualified" && !next.view && !next.priority) setViewId("qualified");
    else if (next.view === "hot" && requested.length <= 1) setViewId("hot");
    else if (!requested.length) setViewId("hot");
    else setViewId("all");
    setFilters(next);
    setSearchDraft(next.search);
    const openId = params.get("open");
    if (openId) setActive({ id: openId } as Lead);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchDraft === filters.search) return;
      setPage(1);
      setFilters((current) => ({ ...current, search: searchDraft }));
    }, 300);
    return () => clearTimeout(timer);
  }, [searchDraft, filters.search]);

  const activeView = VIEWS.find((view) => view.id === viewId) || VIEWS[0];
  const extraChips = filterChips(filters, campaigns, activeView);

  function update<K extends keyof Filters>(key: K, value: Filters[K]) {
    setPage(1);
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function applyView(view: (typeof VIEWS)[number]) {
    setViewId(view.id);
    setPage(1);
    setFilters((current) => ({
      ...EMPTY_FILTERS,
      search: current.search,
      sort: current.sort,
      direction: current.direction,
      ...view.filters,
    }));
    setShowFilters(false);
  }

  function clearExtras() {
    setPage(1);
    setFilters((current) => ({
      ...EMPTY_FILTERS,
      search: current.search,
      sort: current.sort,
      direction: current.direction,
      ...activeView.filters,
    }));
  }

  const allChecked = items.length > 0 && items.every((item) => selected.includes(item.id));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Leads</h1>
          <p className="mt-1 text-sm text-mist">{activeView.hint}. Click a row to research and contact.</p>
        </div>
        <div className="text-sm text-mist">{loading ? "Loading…" : `${total} ${total === 1 ? "lead" : "leads"}`}</div>
      </div>

      <div className="flex flex-wrap gap-2">
        {VIEWS.map((view) => {
          const selectedView = activeView.id === view.id;
          return (
            <button
              key={view.id}
              className={cx("btn", selectedView ? "btn-primary" : "btn-secondary")}
              onClick={() => applyView(view)}
            >
              {view.name}
            </button>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-2">
        {SMART.map((item) => (
          <button
            key={item.name}
            className="rounded-full border border-white/10 px-2.5 py-1 text-xs text-mist hover:border-white/20 hover:text-white"
            onClick={() => {
              setViewId("all");
              setPage(1);
              setFilters((current) => ({ ...EMPTY_FILTERS, search: current.search, sort: current.sort, direction: current.direction, ...item.filters }));
            }}
          >
            {item.name}
          </button>
        ))}
      </div>

      <div className="card p-3">
        <div className="flex flex-col gap-3 lg:flex-row">
          <input
            className="field lg:flex-1"
            placeholder="Search a business, website, email, or phone"
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:w-[640px]">
            <select className="field" value={filters.property_type} onChange={(e) => update("property_type", e.target.value)}>
              <option value="">All types</option>
              {PROPERTY_TYPES.map((item) => <option key={item}>{item}</option>)}
            </select>
            <select className="field" value={filters.city} onChange={(e) => update("city", e.target.value)}>
              <option value="">All cities</option>
              {facets.cities.map((item) => <option key={item}>{item}</option>)}
            </select>
            <select className="field" value={filters.sales_status} onChange={(e) => update("sales_status", e.target.value)}>
              <option value="">All statuses</option>
              {["new", "qualified", "contacted", "replied", "trial", "customer", "lost"].map((item) => <option key={item}>{item}</option>)}
            </select>
            <select className="field" value={filters.sort} onChange={(e) => update("sort", e.target.value)}>
              <option value="overall_score">Sort: score</option>
              <option value="priority">Sort: priority</option>
              <option value="contactability">Sort: contactability</option>
              <option value="estimated_properties">Sort: properties</option>
              <option value="reviews">Sort: reviews</option>
              <option value="created">Sort: newest</option>
            </select>
          </div>
          <button className={cx("btn btn-secondary shrink-0", showFilters && "bg-white/10")} onClick={() => setShowFilters((value) => !value)}>
            <SlidersHorizontal size={16} />
            More filters
            {advancedCount(filters) > 0 && <span className="rounded-full bg-accent px-1.5 text-[10px] font-semibold text-ink-950">{advancedCount(filters)}</span>}
          </button>
          <div className="relative">
            <button className={cx("btn btn-secondary shrink-0", showColumns && "bg-white/10")} onClick={() => setShowColumns((value) => !value)}>
              Columns
            </button>
            {showColumns && (
              <div className="absolute right-0 z-20 mt-2 w-56 rounded-xl border border-white/10 bg-[#12141a] p-3 shadow-xl">
                {COLUMN_DEFS.map((col) => (
                  <label key={col.id} className="flex items-center gap-2 py-1 text-sm">
                    <input
                      type="checkbox"
                      checked={columns.includes(col.id)}
                      onChange={() => setColumns((current) => current.includes(col.id) ? current.filter((id) => id !== col.id) : [...current, col.id])}
                    />
                    {col.label}
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>

        {showFilters && (
          <div className="mt-4 grid gap-6 border-t border-white/5 pt-4 md:grid-cols-4">
            <FilterGroup title="Fit">
              <select className="field" value={filters.priority} onChange={(e) => update("priority", e.target.value)}>
                <option value="">Any priority</option>
                {["A+", "A", "B", "C"].map((item) => <option key={item}>{item}</option>)}
              </select>
              <select className="field" value={filters.min_score} onChange={(e) => update("min_score", e.target.value)}>
                <option value="">Any score</option>
                <option value="80">80+</option>
                <option value="65">65+</option>
                <option value="40">40+</option>
              </select>
              <select className="field" value={filters.estimated_properties} onChange={(e) => update("estimated_properties", e.target.value)}>
                <option value="">Any property count</option>
                {["1", "2-3", "4-10", "10+", "unknown"].map((item) => <option key={item}>{item}</option>)}
              </select>
              <select className="field" value={filters.multi_property} onChange={(e) => update("multi_property", e.target.value)}>
                <option value="">Any operator size</option>
                <option value="true">Multi-property only</option>
              </select>
            </FilterGroup>
            <FilterGroup title="Contact">
              <select className="field" value={filters.has_phone} onChange={(e) => update("has_phone", e.target.value)}>
                <option value="">Phone optional</option>
                <option value="true">Has phone</option>
              </select>
              <select className="field" value={filters.has_email} onChange={(e) => update("has_email", e.target.value)}>
                <option value="">Email optional</option>
                <option value="true">Has email</option>
              </select>
              <select className="field" value={filters.has_website} onChange={(e) => update("has_website", e.target.value)}>
                <option value="">Website optional</option>
                <option value="true">Has website</option>
              </select>
              <select className="field" value={filters.has_decision_maker} onChange={(e) => update("has_decision_maker", e.target.value)}>
                <option value="">Decision maker optional</option>
                <option value="true">Has decision maker</option>
              </select>
            </FilterGroup>
            <FilterGroup title="Source">
              <select className="field" value={filters.campaign_id} onChange={(e) => update("campaign_id", e.target.value)}>
                <option value="">All campaigns</option>
                {campaigns.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
              <select className="field" value={filters.country} onChange={(e) => update("country", e.target.value)}>
                <option value="">All countries</option>
                <option value="United Kingdom">United Kingdom</option>
              </select>
              <select className="field" value={filters.qualification_status} onChange={(e) => update("qualification_status", e.target.value)}>
                <option value="">Any qualification</option>
                <option value="reviewed">AI reviewed</option>
                <option value="qualified">Qualified A+/A/B</option>
                <option value="unqualified">Not reviewed</option>
              </select>
              <select className="field" value={filters.sales_priority} onChange={(e) => update("sales_priority", e.target.value)}>
                <option value="">Any sales priority</option>
                {["Hot", "High", "Medium", "Low", "Reject"].map((item) => <option key={item}>{item}</option>)}
              </select>
              <select className="field" value={filters.research_status} onChange={(e) => update("research_status", e.target.value)}>
                <option value="">Any research status</option>
                {["not_researched", "ai_researched", "website_researched", "contact_researched", "sales_ready"].map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}
              </select>
              <select className="field" value={filters.min_contactability} onChange={(e) => update("min_contactability", e.target.value)}>
                <option value="">Any contactability</option>
                <option value="50">50+</option>
                <option value="70">70+</option>
              </select>
              <select className="field" value={filters.current_software} onChange={(e) => update("current_software", e.target.value)}>
                <option value="">Any software</option>
                <option value="unknown">Unknown</option>
                <option value="Cloudbeds">Cloudbeds</option>
                <option value="Mews">Mews</option>
                <option value="Guesty">Guesty</option>
              </select>
            </FilterGroup>
            <div className="flex items-end">
              <button className="btn btn-secondary w-full" onClick={clearExtras}>Reset extra filters</button>
            </div>
          </div>
        )}

        {extraChips.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {extraChips.map((chip) => (
              <button key={chip.key} className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs" onClick={() => {
                if (chip.key === "search") setSearchDraft("");
                update(chip.key as keyof Filters, "");
              }}>
                {chip.label}
                <X size={12} />
              </button>
            ))}
            {advancedCount(filters) > 0 && (
              <button className="text-xs text-mist hover:text-white" onClick={clearExtras}>Clear extras</button>
            )}
          </div>
        )}
      </div>

      {selected.length > 0 && (
        <div className="card flex flex-wrap items-center gap-3 px-4 py-3">
          <span className="text-sm">{selected.length} selected</span>
          <button className="btn btn-secondary" onClick={() => apiSend("/leads/bulk", "POST", { lead_ids: selected, sales_status: "contacted" }).then(() => { setSelected([]); load(); })}>Mark Contacted</button>
          <button className="btn btn-secondary" onClick={async () => { const result = await apiSend<{ download_url: string }>("/leads/export", "POST", { lead_ids: selected }); window.location.href = result.download_url; }}>Export</button>
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-[1100px] w-full text-left text-sm">
            <thead className="bg-white/[0.03] text-[11px] uppercase tracking-wide text-mist">
              <tr>
                <th className="px-4 py-3"><input type="checkbox" checked={allChecked} onChange={() => setSelected(allChecked ? [] : items.map((item) => item.id))} /></th>
                <th className="px-3 py-3 font-medium">Business</th>
                {COLUMN_DEFS.filter((col) => columns.includes(col.id)).map((col) => (
                  <th key={col.id} className="px-3 py-3 font-medium">{col.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && Array.from({ length: 8 }).map((_, i) => <tr key={i}><td colSpan={columns.length + 2} className="px-4 py-3"><Skeleton className="h-8" /></td></tr>)}
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={columns.length + 2} className="p-8">
                    <EmptyState title="No matching prospects" body="Try All leads, or clear a filter chip above." />
                  </td>
                </tr>
              )}
              {items.map((lead) => (
                <tr key={lead.id} className="cursor-pointer border-t border-white/5 hover:bg-white/[0.03]" onClick={() => setActive(lead)}>
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" checked={selected.includes(lead.id)} onChange={() => setSelected(selected.includes(lead.id) ? selected.filter((id) => id !== lead.id) : [...selected, lead.id])} />
                  </td>
                  <td className="px-3 py-3">
                    <div className="font-medium">{lead.name}</div>
                    <div className="mt-0.5 text-xs text-mist">
                      {lead.location_count && lead.location_count > 1 ? `${lead.location_count} locations · 1 sales account` : lead.company_name || lead.city || ""}
                    </div>
                  </td>
                  {columns.includes("type") && <td className="px-3 py-3 text-mist">{lead.property_type || "—"}</td>}
                  {columns.includes("city") && <td className="px-3 py-3 text-mist">{lead.city || "—"}</td>}
                  {columns.includes("score") && (
                    <td className="px-3 py-3">
                      <div className="text-lg font-semibold">{lead.overall_score ?? "—"}</div>
                      <SalesPriorityBadge value={lead.sales_priority} />
                    </td>
                  )}
                  {columns.includes("priority") && <td className="px-3 py-3"><PriorityBadge value={lead.priority} /></td>}
                  {columns.includes("scale") && <td className="px-3 py-3 text-mist">{lead.estimated_property_count || "unknown"}{lead.multi_property_signal ? " · multi" : ""}</td>}
                  {columns.includes("opportunity") && <td className="px-3 py-3">{lead.opportunity_score ?? "—"}</td>}
                  {columns.includes("contactability") && <td className="px-3 py-3">{lead.contactability_score ?? "—"}</td>}
                  {columns.includes("decision_maker") && <td className="px-3 py-3 text-mist">{lead.decision_maker_name || "—"}</td>}
                  {columns.includes("email") && <td className="px-3 py-3 text-mist">{lead.email || "—"}</td>}
                  {columns.includes("phone") && <td className="px-3 py-3 text-mist">{lead.phone || "—"}</td>}
                  {columns.includes("status") && <td className="px-3 py-3"><StatusBadge value={lead.sales_status} /></td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 px-4 py-3 text-sm">
          <div className="text-mist">Page {page} · {pageSize} per page</div>
          <div className="flex items-center gap-2">
            <select className="field w-24" value={pageSize} onChange={(e) => { setPage(1); setPageSize(Number(e.target.value)); }}>
              {[25, 50, 100].map((n) => <option key={n}>{n}</option>)}
            </select>
            <button className="btn btn-secondary" disabled={page === 1} onClick={() => setPage(page - 1)}>Prev</button>
            <button className="btn btn-secondary" disabled={page * pageSize >= total} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        </div>
      </div>
      {active && <LeadDrawer leadId={active.id} onClose={() => setActive(null)} onChanged={load} />}
    </div>
  );
}

function advancedCount(filters: Filters) {
  return ["priority", "min_score", "estimated_properties", "multi_property", "has_phone", "has_email", "has_website", "has_decision_maker", "campaign_id", "country"].filter((key) => filters[key as keyof Filters]).length;
}

function filterChips(filters: Filters, campaigns: { id: string; name: string }[], view: (typeof VIEWS)[number]) {
  const implied = new Set(Object.keys(view.filters).filter((key) => view.filters[key as keyof typeof view.filters]));
  return (Object.entries(filters) as Array<[keyof Filters, string]>)
    .filter(([key, value]) => Boolean(value) && !["sort", "direction"].includes(key) && !implied.has(key))
    .map(([key, value]) => {
      let labelValue = value;
      if (key === "view") labelValue = VIEW_VALUES[value] || value;
      if (key === "campaign_id") labelValue = campaigns.find((item) => item.id === value)?.name || value;
      if (key === "qualification_status") labelValue = { reviewed: "AI reviewed", qualified: "Qualified", unqualified: "Not reviewed" }[value] || value;
      if (value === "true") labelValue = "";
      const prefix = CHIP_LABELS[key] || key;
      return { key, label: labelValue ? `${prefix}: ${labelValue}` : prefix };
    });
}

function FilterGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <div className="text-xs uppercase tracking-[0.16em] text-mist">{title}</div>
      {children}
    </div>
  );
}

function LeadDrawer({ leadId, onClose, onChanged }: { leadId: string; onClose: () => void; onChanged: () => void }) {
  const [lead, setLead] = useState<Lead | null>(null);
  const [notes, setNotes] = useState("");
  const [followup, setFollowup] = useState("");
  const [priority, setPriority] = useState("");
  const [propertyType, setPropertyType] = useState("");
  const [properties, setProperties] = useState("");

  useEffect(() => {
    apiGet<Lead>(`/leads/${leadId}`).then((data) => {
      setLead(data);
      setNotes(data.notes || "");
      setFollowup(data.next_followup_at ? data.next_followup_at.slice(0, 10) : "");
      setPriority(data.priority || "");
      setPropertyType(data.property_type || "");
      setProperties(data.estimated_property_count || "");
    });
  }, [leadId]);

  if (!lead) return null;

  async function mark(status: string) {
    await apiSend(`/leads/${leadId}/status/${status}`, "POST");
    toast.success(`Marked ${status}`);
    onChanged();
    setLead(await apiGet<Lead>(`/leads/${leadId}`));
  }

  async function save() {
    await apiSend(`/leads/${leadId}`, "PATCH", {
      notes,
      next_followup_at: followup ? new Date(followup).toISOString() : null,
      priority,
      property_type: propertyType,
      estimated_property_count: properties,
    });
    toast.success("Saved");
    onChanged();
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/50" onClick={onClose}>
      <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-white/10 bg-[#12141a] p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-wide text-accent">Research</div>
            <h2 className="mt-1 text-2xl font-semibold">{lead.name}</h2>
            <div className="mt-2 flex flex-wrap gap-2">
              <span className="text-2xl font-semibold">{lead.overall_score ?? "—"}</span>
              <SalesPriorityBadge value={lead.sales_priority} />
              <PriorityBadge value={lead.priority} />
              <StatusBadge value={lead.sales_status} />
              <span className="text-sm text-mist">{lead.property_type} · {lead.city}</span>
            </div>
            {lead.company_name && (lead.location_count || 0) > 1 && (
              <div className="mt-2 text-sm text-accent">{lead.company_name} · {lead.location_count} locations · 1 sales account</div>
            )}
            {lead.recommended_next_action && <div className="mt-2 text-sm text-zinc-200">Next: {lead.recommended_next_action}</div>}
            {lead.research_status && <div className="mt-1 text-xs text-mist">Research: {lead.research_status.replaceAll("_", " ")}</div>}
          </div>
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
        <div className="mt-5 grid grid-cols-4 gap-2 text-center">
          <Score label="ICP" value={lead.icp_score} />
          <Score label="Opportunity" value={lead.opportunity_score} />
          <Score label="Contact" value={lead.contactability_score} />
          <Score label="Data quality" value={lead.data_quality_score} />
        </div>
        <Section title="Why this lead">
          <p className="text-sm leading-6 text-zinc-200">{lead.fit_summary || lead.claude_reason || "Not reviewed yet."}</p>
          {lead.review_reason && <p className="mt-2 text-sm text-amber-200">Needs review: {lead.review_reason}</p>}
        </Section>
        <Section title="Business">
          <Row label="Website" value={lead.website} href={lead.website} />
          <Row label="Phone" value={lead.phone} />
          <Row label="Email" value={lead.email} />
          <Row label="Address" value={lead.address} />
          <Row label="Maps" value={lead.google_maps_url ? "Open map" : ""} href={lead.google_maps_url} />
          <Row label="LinkedIn" value={lead.linkedin} href={lead.linkedin} />
          <Row label="Facebook" value={lead.facebook} href={lead.facebook} />
          <Row label="Instagram" value={lead.instagram} href={lead.instagram} />
          <Row label="Google category" value={lead.source_category} />
        </Section>
        <Section title="Scale">
          <Row label="Properties" value={lead.estimated_property_count || "unknown"} />
          <Row label="Beds" value={lead.estimated_bed_count} />
          <Row label="Multi-property" value={lead.multi_property_signal ? `Yes · ${lead.multi_property_confidence || "unknown"}` : "No"} />
          <Row label="Confidence" value={lead.scale_confidence} />
          <Row label="Evidence" value={lead.multi_property_evidence} />
          <Row label="Company" value={lead.company_name} />
          {(lead.locations || []).map((item) => (
            <Row key={item.id} label={item.city || "Location"} value={item.name} href={item.google_maps_url} />
          ))}
        </Section>
        <Section title="Intelligence">
          <Row label="Software" value={lead.current_software} />
          <Row label="Decision maker" value={lead.decision_maker_name} />
          <Row label="Role" value={lead.decision_maker_role} />
          <Row label="Ideal customer" value={lead.ideal_customer} />
          <Row label="Last contact" value={formatDate(lead.last_contacted_at)} />
          <Row label="Follow-up" value={formatDate(lead.next_followup_at)} />
          <Row label="Assigned" value={lead.assigned_to} />
        </Section>
        <Section title="Activity">
          {(lead.activity || []).length === 0 && <p className="text-sm text-mist">No activity yet.</p>}
          {(lead.activity || []).map((item, index) => (
            <div key={index} className="text-sm text-mist">
              {formatDate(item.created_at)} · {item.action.replaceAll(":", " ")}
              {item.to_status ? ` → ${item.to_status}` : ""}
            </div>
          ))}
        </Section>
        <Section title="Evidence">
          {(lead.evidence || []).length === 0 && <p className="text-sm text-mist">No evidence stored yet.</p>}
          {(lead.evidence || []).map((item, index) => (
            <div key={index} className="rounded-lg border border-white/5 p-3 text-sm">
              <div className="text-xs uppercase text-mist">{item.evidence_type} · {item.evidence_source}</div>
              <p className="mt-1">{item.evidence_text}</p>
              {item.evidence_url && <a className="text-accent" href={item.evidence_url} target="_blank" rel="noreferrer">Source</a>}
            </div>
          ))}
        </Section>
        <Section title="Sales">
          <div className="grid gap-3 md:grid-cols-2">
            <select className="field" value={priority} onChange={(e) => setPriority(e.target.value)}>
              {["", "A+", "A", "B", "C"].map((item) => <option key={item}>{item || "Priority"}</option>)}
            </select>
            <select className="field" value={propertyType} onChange={(e) => setPropertyType(e.target.value)}>
              {PROPERTY_TYPES.map((item) => <option key={item}>{item}</option>)}
            </select>
            <select className="field" value={properties} onChange={(e) => setProperties(e.target.value)}>
              {["", "1", "2-3", "4-10", "10+", "unknown"].map((item) => <option key={item}>{item || "Estimated properties"}</option>)}
            </select>
          </div>
          <textarea className="field mt-3 min-h-24" placeholder="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
          <label className="mt-3 block text-xs text-mist">Next follow-up</label>
          <input className="field mt-1" type="date" value={followup} onChange={(e) => setFollowup(e.target.value)} />
          <div className="mt-4 flex flex-wrap gap-2">
            {lead.website && <a className="btn btn-secondary" href={lead.website.startsWith("http") ? lead.website : `https://${lead.website}`} target="_blank" rel="noreferrer">Open Website</a>}
            {lead.google_maps_url && <a className="btn btn-secondary" href={lead.google_maps_url} target="_blank" rel="noreferrer">Open Maps</a>}
            {lead.linkedin && <a className="btn btn-secondary" href={lead.linkedin} target="_blank" rel="noreferrer">Open LinkedIn</a>}
            <button className="btn btn-secondary" onClick={() => mark("contacted")}>Mark Contacted</button>
            <button className="btn btn-secondary" onClick={() => mark("replied")}>Mark Replied</button>
            <button className="btn btn-secondary" onClick={() => mark("trial")}>Start Trial</button>
            <button className="btn btn-primary" onClick={() => mark("customer")}>Mark Customer</button>
            <button className="btn btn-danger" onClick={() => { if (confirm("Mark this prospect as lost?")) mark("lost"); }}>Mark Lost</button>
            {lead.needs_review && <button className="btn btn-secondary" onClick={() => { if (confirm("Approve this lead and keep the current classification?")) apiSend(`/leads/${leadId}/review`, "POST", { action: "approve" }).then(() => { toast.success("Approved"); onChanged(); }); }}>Approve</button>}
            {lead.needs_review && <button className="btn btn-danger" onClick={() => { if (confirm("Reject this lead? This marks it C and overrides AI.")) apiSend(`/leads/${leadId}/review`, "POST", { action: "reject" }).then(() => { toast.success("Rejected"); onChanged(); }); }}>Reject</button>}
            <button className="btn btn-secondary" onClick={save}>Save</button>
          </div>
        </Section>
      </aside>
    </div>
  );
}

function Score({ label, value }: { label: string; value?: number | null }) {
  return (
    <div className="rounded-lg bg-white/[0.04] py-3">
      <div className="text-[10px] uppercase text-mist">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value ?? "—"}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-8">
      <h3 className="text-xs uppercase tracking-[0.18em] text-mist">{title}</h3>
      <div className="mt-3 space-y-2">{children}</div>
    </section>
  );
}

function Row({ label, value, href }: { label: string; value?: string | number | null; href?: string }) {
  const text = value === 0 ? "0" : value ? String(value) : "";
  return (
    <div className="grid grid-cols-[140px_1fr] gap-3 text-sm">
      <div className="text-mist">{label}</div>
      {href ? <a className="truncate text-accent hover:underline" href={href} target="_blank" rel="noreferrer">{text || "—"}</a> : <div>{text || "—"}</div>}
    </div>
  );
}
