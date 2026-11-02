"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Circle, Loader2, Plus, RotateCcw, Square } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiSend } from "@/lib/api";
import { EmptyState } from "@/components/EmptyState";

const CATEGORIES = [
  "Hostel",
  "Student Accommodation",
  "HMO",
  "Co-living",
  "Guest House",
  "Boarding House",
  "Hotel",
  "Other",
];

const DEFAULT_LIMITS: Record<string, number> = {
  Hostel: 30,
  "Student Accommodation": 40,
  HMO: 30,
  "Co-living": 20,
  "Guest House": 20,
  "Boarding House": 10,
  Hotel: 20,
  Other: 20,
};

type Campaign = {
  id: string;
  name: string;
  market: string;
  country: string;
  status: string;
  last_run_at?: string | null;
  cities: string[];
  searches: { id: string; city: string; category: string; result_limit: number; status: string; results_count: number; quality_score?: number; a_plus_count?: number; a_count?: number; b_count?: number; c_count?: number; contactable_count?: number }[];
  quality?: { quality_score: number; total?: number; ai_reviewed?: number; a_plus: number; a: number; b: number; c: number; hot?: number; contactable: number; multi_property: number; a_plus_rate?: number; aa_plus_rate?: number; contactability_rate?: number; multi_property_rate?: number };
};

type Job = {
  id: string;
  campaign_id?: string;
  status: string;
  error?: string;
  progress: {
    phase?: string;
    steps?: { id: string; name: string; status: string; detail?: string }[];
    progress_current?: number;
    progress_total?: number;
    raw_results?: number;
    unique_results?: number;
    existing_leads?: number;
    new_leads?: number;
    qualification?: { current: number; total: number; a_plus?: number; a: number; b: number; c: number };
  };
  logs?: { timestamp: string; message: string; status: string }[];
};

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [open, setOpen] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [activeName, setActiveName] = useState("");
  const [form, setForm] = useState({
    name: "UK – London Campaign",
    market: "UK",
    country: "United Kingdom",
    cities: ["London"],
    cityInput: "",
    categories: CATEGORIES.filter((item) => item !== "Hotel" && item !== "Other").map((item) => ({
      category: item,
      result_limit: DEFAULT_LIMITS[item],
      enabled: true,
    })),
  });

  async function load() {
    setCampaigns(await apiGet<Campaign[]>("/campaigns"));
  }

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!job || ["completed", "failed", "cancelled"].includes(job.status)) return;
    const timer = setInterval(async () => {
      const next = await apiGet<Job>(`/jobs/${job.id}`);
      setJob(next);
    }, 1200);
    return () => clearInterval(timer);
  }, [job?.id, job?.status]);

  const selectedCategories = form.categories.filter((item) => item.enabled);

  async function createCampaign() {
    if (!form.cities.length || !selectedCategories.length) {
      toast.error("Add at least one city and category");
      return;
    }
    const campaign = await apiSend<Campaign>("/campaigns", "POST", {
      name: form.name,
      market: form.market,
      country: form.country,
      cities: form.cities,
      categories: selectedCategories.map(({ category, result_limit }) => ({ category, result_limit })),
    });
    setOpen(false);
    await load();
    await runCampaign(campaign);
  }

  async function runCampaign(campaign: Campaign) {
    setActiveName(campaign.name);
    const result = await apiSend<{ job_id: string }>("/campaigns/" + campaign.id + "/run", "POST");
    setJob(await apiGet<Job>(`/jobs/${result.job_id}`));
    toast.success("Campaign started");
    await load();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Campaigns</h1>
          <p className="text-sm text-mist">Find new cities, then review the best leads. No terminal needed.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setOpen(true)}>
          <Plus size={16} /> New Campaign
        </button>
      </div>

      {campaigns.length === 0 ? (
        <EmptyState title="No campaigns yet" body="Create a campaign, choose cities and categories, then run it." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {campaigns.map((campaign) => (
            <div key={campaign.id} className="card p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-lg font-medium">{campaign.name}</div>
                  <div className="mt-1 text-sm text-mist">
                    {campaign.market} · {campaign.country} · {campaign.cities.join(", ") || "No cities"}
                  </div>
                </div>
                <span className="badge border-white/10 text-mist">{campaign.status}</span>
              </div>
              {campaign.quality && (
                <div className="mt-4 space-y-2 text-xs text-mist">
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <div>Quality {campaign.quality.quality_score}%</div>
                    <div>A+ {campaign.quality.a_plus} · A {campaign.quality.a}</div>
                    <div>B {campaign.quality.b} · C {campaign.quality.c}</div>
                    <div>Hot {campaign.quality.hot ?? 0} · Multi {campaign.quality.multi_property}</div>
                  </div>
                  <div>A/A+ {campaign.quality.aa_plus_rate ?? campaign.quality.quality_score}% · Contactable {campaign.quality.contactability_rate ?? 0}% · Multi-property {campaign.quality.multi_property_rate ?? 0}%</div>
                </div>
              )}
              <div className="mt-4 space-y-2 text-xs text-mist">
                {campaign.searches.slice(0, 8).map((search) => (
                  <div key={search.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-white/5 px-2 py-1.5">
                    <span>{search.city} + {search.category}</span>
                    <span>
                      {search.results_count || 0} results · A+ {search.a_plus_count ?? 0} · A {search.a_count ?? 0} · B {search.b_count ?? 0} · C {search.c_count ?? 0}
                      {search.quality_score ? ` · ${search.quality_score}%` : ""}
                    </span>
                  </div>
                ))}
              </div>
              <div className="mt-5 flex gap-2">
                <button className="btn btn-primary" onClick={() => runCampaign(campaign)}>
                  Run Campaign
                </button>
                {campaign.status === "failed" && (
                  <button className="btn btn-secondary" onClick={() => runCampaign(campaign)}>
                    <RotateCcw size={14} /> Retry
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {open && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4">
          <div className="card max-h-[90vh] w-full max-w-2xl overflow-y-auto p-6">
            <h2 className="text-xl font-semibold">New Campaign</h2>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <Field label="Campaign Name" value={form.name} onChange={(value) => setForm({ ...form, name: value })} />
              <Field label="Market" value={form.market} onChange={(value) => setForm({ ...form, market: value })} />
              <Field label="Country" value={form.country} onChange={(value) => setForm({ ...form, country: value })} />
            </div>
            <label className="mt-5 block text-sm text-mist">Cities</label>
            <div className="mt-2 flex gap-2">
              <input
                className="field"
                value={form.cityInput}
                placeholder="Add a city"
                onChange={(e) => setForm({ ...form, cityInput: e.target.value })}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    const city = form.cityInput.trim();
                    if (city && !form.cities.includes(city)) setForm({ ...form, cities: [...form.cities, city], cityInput: "" });
                  }
                }}
              />
              <button
                className="btn btn-secondary"
                onClick={() => {
                  const city = form.cityInput.trim();
                  if (city && !form.cities.includes(city)) setForm({ ...form, cities: [...form.cities, city], cityInput: "" });
                }}
              >
                Add
              </button>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {form.cities.map((city) => (
                <button
                  key={city}
                  className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-sm"
                  onClick={() => setForm({ ...form, cities: form.cities.filter((item) => item !== city) })}
                >
                  {city} ×
                </button>
              ))}
            </div>
            <div className="mt-6 text-sm text-mist">Search Categories</div>
            <div className="mt-3 space-y-2">
              {form.categories.map((item, index) => (
                <div key={item.category} className="grid grid-cols-[1fr_120px] items-center gap-3 rounded-xl border border-white/10 px-3 py-2">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={item.enabled}
                      onChange={(e) => {
                        const next = [...form.categories];
                        next[index] = { ...item, enabled: e.target.checked };
                        setForm({ ...form, categories: next });
                      }}
                    />
                    {item.category}
                  </label>
                  <input
                    type="number"
                    className="field"
                    min={1}
                    max={500}
                    value={item.result_limit}
                    onChange={(e) => {
                      const next = [...form.categories];
                      next[index] = { ...item, result_limit: Number(e.target.value) };
                      setForm({ ...form, categories: next });
                    }}
                  />
                </div>
              ))}
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button className="btn btn-secondary" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={() => createCampaign().catch((e) => toast.error(e.message))}>
                Create & Run
              </button>
            </div>
          </div>
        </div>
      )}

      {job && <CampaignProgress job={job} name={activeName} onClose={() => setJob(null)} />}
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <div className="text-sm text-mist">{label}</div>
      <input className="field mt-1" value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function CampaignProgress({ job, name, onClose }: { job: Job; name: string; onClose: () => void }) {
  const q = job.progress?.qualification;
  const done = ["completed", "failed", "cancelled"].includes(job.status);
  const percent = useMemo(() => {
    const total = job.progress?.progress_total || 1;
    return Math.min(100, Math.round(((job.progress?.progress_current || 0) / total) * 100));
  }, [job]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="card w-full max-w-xl p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-xs uppercase tracking-wide text-accent">Live campaign</div>
            <h2 className="mt-1 text-xl font-semibold">{name || "Campaign"}</h2>
          </div>
          <button className="btn btn-secondary" onClick={onClose}>
            {done ? "Close" : "Hide"}
          </button>
        </div>
        <div className="mt-6 space-y-3">
          {(job.progress?.steps || []).map((step) => (
            <div key={step.id} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-3">
                <StepIcon status={step.status} />
                <span>{step.name}</span>
              </div>
              <span className="text-mist">{step.detail}</span>
            </div>
          ))}
        </div>
        <div className="mt-6">
          <div className="mb-2 flex justify-between text-sm text-mist">
            <span>Progress</span>
            <span>
              {job.progress?.progress_current || 0} / {job.progress?.progress_total || 0}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/10">
            <div className="h-full bg-accent" style={{ width: `${percent}%` }} />
          </div>
        </div>
        {job.progress?.raw_results !== undefined && job.progress.phase !== "searching" && (
          <div className="mt-6 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
            <Stat label="Raw Results" value={job.progress.raw_results} />
            <Stat label="Unique Results" value={job.progress.unique_results} />
            <Stat label="Existing Leads" value={job.progress.existing_leads} />
            <Stat label="New Leads" value={job.progress.new_leads} />
          </div>
        )}
        {q && q.total > 0 && (
          <div className="mt-4 rounded-xl border border-white/10 p-4 text-sm">
            <div>Claude Qualification {q.current} / {q.total}</div>
            <div className="mt-2 text-mist">A+: {q.a_plus ?? 0} · A: {q.a} · B: {q.b} · Rejected: {q.c}</div>
          </div>
        )}
        {job.status === "completed" && <div className="mt-4 text-sm text-accent">Campaign completed.</div>}
        {job.status === "failed" && <div className="mt-4 text-sm text-rose-300">{job.error || "Campaign failed."}</div>}
        {!done && (
          <button
            className="btn btn-secondary mt-5"
            onClick={() => job.campaign_id && apiSend(`/campaigns/${job.campaign_id}/cancel`, "POST").catch(() => undefined)}
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}

function StepIcon({ status }: { status: string }) {
  if (status === "done") return <Check size={16} className="text-accent" />;
  if (status === "running") return <Loader2 size={16} className="animate-spin text-accent" />;
  if (status === "failed") return <Square size={14} className="text-rose-300" />;
  return <Circle size={14} className="text-zinc-600" />;
}

function Stat({ label, value }: { label: string; value?: number }) {
  return (
    <div className="rounded-xl bg-white/5 p-3">
      <div className="text-xs text-mist">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value ?? 0}</div>
    </div>
  );
}
