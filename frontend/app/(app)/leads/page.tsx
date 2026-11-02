"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Download, ExternalLink, Globe, Mail, MapPin, Phone, Search, Smartphone, Star } from "lucide-react";
import { apiGet } from "@/lib/api";
import { cx } from "@/lib/utils";
import { EmptyState, Skeleton } from "@/components/EmptyState";

type Facet = { value: string; count: number };

type Listing = {
  id: string;
  name: string;
  city: string;
  address: string;
  type: string;
  gender: string;
  phone: string;
  mobile: string;
  email: string;
  website: string;
  maps_url: string;
  rating: number | null;
  reviews: number | null;
};

type Operator = {
  key: string;
  name: string;
  property_count: number;
  listings_found: number;
  tier: string;
  types: string[];
  genders: string[];
  cities: string[];
  country: string;
  mobile: string;
  email: string;
  phone: string;
  website: string;
  rating: number | null;
  reviews: number;
  matched_ids: string[];
  listings: Listing[];
};

type DirectoryResponse = {
  items: Operator[];
  total_operators: number;
  total_properties: number;
  page: number;
  page_size: number;
  facets: {
    countries: Facet[];
    cities: Facet[];
    types: Facet[];
    genders: Facet[];
    tiers: Facet[];
    contact: { both: number; mobile: number; email: number; any: number };
  };
};

type Filters = { country: string; city: string; type: string; gender: string; tier: string; contact: string; search: string };

const EMPTY: Filters = { country: "", city: "", type: "", gender: "", tier: "", contact: "", search: "" };
const TYPES = ["Dormitory", "HMO", "Hostel", "PG", "Guest House"];
const GENDERS: Array<[string, string]> = [["Male", "Male"], ["Female", "Female"], ["Mixed", "Mixed"], ["Unknown", "Not specified"]];
const TIERS: Array<[string, string]> = [["Premium", "6+"], ["High", "4–5"], ["Medium", "2–3"], ["Low", "1"]];
const PAGE_SIZE = 30;

const TIER_STYLE: Record<string, string> = {
  Premium: "border-violet-400/30 bg-violet-400/10 text-violet-200",
  High: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  Medium: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  Low: "border-white/10 bg-white/[0.04] text-zinc-400",
};

function toQuery(filters: Filters, page?: number) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => value && params.set(key, value));
  if (page) {
    params.set("page", String(page));
    params.set("page_size", String(PAGE_SIZE));
  }
  return params.toString();
}

function readUrlFilters(): Filters {
  if (typeof window === "undefined") return EMPTY;
  const params = new URLSearchParams(window.location.search);
  return Object.fromEntries(Object.keys(EMPTY).map((key) => [key, params.get(key) || ""])) as Filters;
}

function countOf(facets: Facet[] | undefined, value: string) {
  return facets?.find((item) => item.value === value)?.count ?? 0;
}

function hostOf(url: string) {
  try {
    return new URL(url.startsWith("http") ? url : `https://${url}`).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export default function LeadsPage() {
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [searchInput, setSearchInput] = useState("");
  const [ready, setReady] = useState(false);
  const [data, setData] = useState<DirectoryResponse | null>(null);
  const [items, setItems] = useState<Operator[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestId = useRef(0);

  // Read filters from the URL once, so filtered views can be bookmarked and shared.
  useEffect(() => {
    const initial = readUrlFilters();
    setFilters(initial);
    setSearchInput(initial.search);
    setReady(true);
  }, []);

  // Debounce the search box.
  useEffect(() => {
    const timer = setTimeout(() => setFilters((current) => (current.search === searchInput ? current : { ...current, search: searchInput })), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const query = useMemo(() => toQuery(filters), [filters]);

  useEffect(() => {
    if (!ready) return;
    window.history.replaceState(null, "", query ? `/leads?${query}` : "/leads");
    setPage(1);
    load(1, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, ready]);

  async function load(nextPage: number, replace: boolean) {
    const id = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const response = await apiGet<DirectoryResponse>(`/directory?${toQuery(filters, nextPage)}`);
      if (id !== requestId.current) return;
      setData(response);
      setItems((current) => (replace ? response.items : [...current, ...response.items]));
    } catch (err) {
      if (id === requestId.current) setError(err instanceof Error ? err.message : "Could not load leads");
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }

  function set<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters((current) => {
      const next = { ...current, [key]: current[key] === value ? "" : value };
      if (key === "country") next.city = "";
      return next;
    });
  }

  function loadMore() {
    const next = page + 1;
    setPage(next);
    load(next, false);
  }

  const facets = data?.facets;
  const hasFilters = Object.values(filters).some(Boolean);
  const hasMore = data ? items.length < data.total_operators : false;

  return (
    <div className="mx-auto max-w-6xl">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Leads</h1>
          <p className="mt-1 text-sm text-mist">
            {data ? (
              <>
                <span className="text-zinc-200">{data.total_operators.toLocaleString()}</span> operators ·{" "}
                <span className="text-zinc-200">{data.total_properties.toLocaleString()}</span> properties, ranked by number of properties
              </>
            ) : (
              "Loading…"
            )}
          </p>
        </div>
        <a className="btn btn-secondary" href={`/api/directory/export${query ? `?${query}` : ""}`}>
          <Download size={15} /> Export CSV
        </a>
      </header>

      <section className="card mb-6 space-y-4 p-4">
        <div className="grid gap-3 sm:grid-cols-[1fr_1fr_1.4fr]">
          <Select label="Country" value={filters.country} onChange={(value) => set("country", value)} options={facets?.countries ?? []} placeholder="All countries" />
          <Select label="City" value={filters.city} onChange={(value) => set("city", value)} options={facets?.cities ?? []} placeholder="All cities" />
          <label className="block">
            <span className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-mist">Search</span>
            <div className="relative">
              <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input className="field !pl-9" placeholder="Name, phone, email, website…" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} />
            </div>
          </label>
        </div>

        <ChipRow label="Type">
          <Chip active={!filters.type} onClick={() => setFilters((c) => ({ ...c, type: "" }))}>All</Chip>
          {TYPES.map((type) => (
            <Chip key={type} active={filters.type === type} count={countOf(facets?.types, type)} onClick={() => set("type", type)}>{type}</Chip>
          ))}
          <Chip active={filters.type === "Other"} count={countOf(facets?.types, "Other")} onClick={() => set("type", "Other")} muted>Other</Chip>
        </ChipRow>

        <ChipRow label="Gender">
          <Chip active={!filters.gender} onClick={() => setFilters((c) => ({ ...c, gender: "" }))}>All</Chip>
          {GENDERS.map(([value, label]) => (
            <Chip key={value} active={filters.gender === value} count={countOf(facets?.genders, value)} onClick={() => set("gender", value)} muted={value === "Unknown"}>{label}</Chip>
          ))}
        </ChipRow>

        <ChipRow label="Size">
          <Chip active={!filters.tier} onClick={() => setFilters((c) => ({ ...c, tier: "" }))}>All</Chip>
          {TIERS.map(([value, range]) => (
            <Chip key={value} active={filters.tier === value} count={countOf(facets?.tiers, value)} onClick={() => set("tier", value)}>
              {value} <span className="text-zinc-500">· {range}</span>
            </Chip>
          ))}
        </ChipRow>

        <ChipRow label="Contact">
          <Chip active={!filters.contact} onClick={() => setFilters((c) => ({ ...c, contact: "" }))}>Any</Chip>
          <Chip active={filters.contact === "both"} count={facets?.contact.both} onClick={() => set("contact", "both")}>Mobile + Email</Chip>
          <Chip active={filters.contact === "mobile"} count={facets?.contact.mobile} onClick={() => set("contact", "mobile")}>Mobile</Chip>
          <Chip active={filters.contact === "email"} count={facets?.contact.email} onClick={() => set("contact", "email")}>Email</Chip>
        </ChipRow>

        {hasFilters && (
          <div className="flex justify-end">
            <button className="text-xs text-mist underline-offset-4 hover:text-zinc-200 hover:underline" onClick={() => { setFilters(EMPTY); setSearchInput(""); }}>
              Clear all filters
            </button>
          </div>
        )}
      </section>

      {error && <div className="card mb-4 border-rose-500/30 p-4 text-sm text-rose-200">{error}</div>}

      {loading && items.length === 0 ? (
        <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>
      ) : items.length === 0 && !error ? (
        <EmptyState title="No leads match these filters" body="Try a different city or type, or clear the filters. New leads arrive when you run a search from Claude Code or Campaigns." />
      ) : (
        <div className="space-y-3">
          {items.map((operator, index) => <OperatorRow key={operator.key} operator={operator} rank={index + 1} />)}
        </div>
      )}

      {hasMore && (
        <div className="mt-6 flex justify-center">
          <button className="btn btn-secondary" disabled={loading} onClick={loadMore}>
            {loading ? "Loading…" : `Show more (${(data!.total_operators - items.length).toLocaleString()} left)`}
          </button>
        </div>
      )}
    </div>
  );
}

function Select({ label, value, onChange, options, placeholder }: { label: string; value: string; onChange: (value: string) => void; options: Facet[]; placeholder: string }) {
  const known = options.some((option) => option.value === value);
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-mist">{label}</span>
      <select className="field" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{placeholder}</option>
        {value && !known && <option value={value}>{value}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.value} ({option.count})
          </option>
        ))}
      </select>
    </label>
  );
}

function ChipRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <div className="w-20 shrink-0 text-[11px] font-medium uppercase tracking-wider text-mist">{label}</div>
      <div className="-mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0 [&>*]:shrink-0">{children}</div>
    </div>
  );
}

function Chip({ active, count, muted, onClick, children }: { active: boolean; count?: number; muted?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition",
        active ? "border-accent/50 bg-accent/15 text-accent" : "border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.06]",
        !active && (muted ? "text-zinc-500" : "text-zinc-300"),
      )}
    >
      {children}
      {count !== undefined && <span className={cx("tabular-nums", active ? "text-accent/80" : "text-zinc-500")}>{count}</span>}
    </button>
  );
}

function OperatorRow({ operator, rank }: { operator: Operator; rank: number }) {
  const [open, setOpen] = useState(false);
  const estimated = operator.property_count > operator.listings_found;
  const gender = operator.genders.filter((g) => g !== "Unknown");

  return (
    <article className="card overflow-hidden">
      <div className="flex gap-4 p-4">
        <div className="flex w-16 shrink-0 flex-col items-center justify-center rounded-lg border border-white/[0.06] bg-white/[0.02] py-2">
          <div className="text-2xl font-semibold tabular-nums leading-none">{operator.property_count}</div>
          <div className="mt-1 text-[10px] uppercase tracking-wider text-mist">{operator.property_count === 1 ? "property" : "properties"}</div>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs tabular-nums text-zinc-600">#{rank}</span>
            <h2 className="truncate text-base font-medium">{operator.name}</h2>
            <span className={cx("badge", TIER_STYLE[operator.tier])}>{operator.tier}</span>
          </div>

          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-mist">
            <span>{operator.types.join(" · ")}</span>
            {gender.length > 0 && <><span className="text-zinc-700">•</span><span>{gender.join(" · ")}</span></>}
            <span className="text-zinc-700">•</span>
            <span className="inline-flex items-center gap-1"><MapPin size={13} />{[operator.cities.slice(0, 3).join(", "), operator.cities.length > 3 ? `+${operator.cities.length - 3}` : "", operator.country].filter(Boolean).join(" · ")}</span>
            {operator.rating !== null && (
              <><span className="text-zinc-700">•</span><span className="inline-flex items-center gap-1"><Star size={13} />{operator.rating} ({operator.reviews.toLocaleString()})</span></>
            )}
          </div>

          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm">
            <Contact icon={<Smartphone size={14} />} value={operator.mobile} href={`tel:${operator.mobile}`} missing="No mobile" />
            <Contact icon={<Mail size={14} />} value={operator.email} href={`mailto:${operator.email}`} missing="No email" />
            {!operator.mobile && operator.phone && <Contact icon={<Phone size={14} />} value={operator.phone} href={`tel:${operator.phone}`} />}
            {operator.website && <Contact icon={<Globe size={14} />} value={hostOf(operator.website)} href={operator.website.startsWith("http") ? operator.website : `https://${operator.website}`} external />}
          </div>
        </div>
      </div>

      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between border-t border-white/[0.06] px-4 py-2 text-xs text-mist hover:bg-white/[0.02] hover:text-zinc-200"
      >
        <span>
          {operator.listings_found} {operator.listings_found === 1 ? "listing" : "listings"} found
          {estimated && ` · ${operator.property_count} estimated in total`}
        </span>
        <ChevronDown size={14} className={cx("transition", open && "rotate-180")} />
      </button>

      {open && (
        <ul className="divide-y divide-white/[0.05] border-t border-white/[0.06] bg-black/10">
          {operator.listings.map((listing) => (
            <li key={listing.id} className="flex flex-col gap-1 px-4 py-3 text-sm sm:flex-row sm:items-center sm:gap-4">
              <div className="min-w-0 flex-1">
                <div className="truncate">{listing.name}</div>
                <div className="truncate text-xs text-mist">
                  {[listing.type, listing.gender !== "Unknown" ? listing.gender : "", listing.address || listing.city].filter(Boolean).join(" · ")}
                </div>
              </div>
              <div className="flex shrink-0 flex-wrap gap-x-4 gap-y-1 text-xs text-mist">
                {(listing.mobile || listing.phone) && <a className="hover:text-zinc-200" href={`tel:${listing.mobile || listing.phone}`}>{listing.mobile || listing.phone}</a>}
                {listing.email && <a className="hover:text-zinc-200" href={`mailto:${listing.email}`}>{listing.email}</a>}
                {listing.maps_url && (
                  <a className="inline-flex items-center gap-1 hover:text-zinc-200" href={listing.maps_url} target="_blank" rel="noreferrer">
                    Map <ExternalLink size={11} />
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function Contact({ icon, value, href, missing, external }: { icon: React.ReactNode; value: string; href: string; missing?: string; external?: boolean }) {
  if (!value) {
    return missing ? <span className="inline-flex items-center gap-1.5 text-zinc-600">{icon}{missing}</span> : null;
  }
  return (
    <a className="inline-flex min-w-0 items-center gap-1.5 text-zinc-200 hover:text-accent" href={href} {...(external ? { target: "_blank", rel: "noreferrer" } : {})}>
      <span className="text-mist">{icon}</span>
      <span className="truncate">{value}</span>
    </a>
  );
}
