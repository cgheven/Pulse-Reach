"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, apiGet, apiSend } from "@/lib/api";

type Settings = {
  claude_model: string;
  default_market: string;
  default_country: string;
  qualification: { batch_size: number; batch_delay_seconds: number; only_send_if_has_website: boolean };
  sales_statuses: string[];
  property_types: string[];
  search_categories: string[];
  api_keys: { outscraper: { configured: boolean; hint: string }; claude: { configured: boolean; hint: string } };
};

type ImportRow = { id: string; filename: string; imported: number; updated: number; skipped: number; duplicates: number; errors: number; created_at?: string };

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [imports, setImports] = useState<ImportRow[]>([]);
  const [outKey, setOutKey] = useState("");
  const [claudeKey, setClaudeKey] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");

  async function load() {
    setSettings(await apiGet<Settings>("/settings"));
    setImports(await apiGet<ImportRow[]>("/leads/imports"));
  }

  useEffect(() => {
    load().catch((error) => toast.error(error.message));
  }, []);

  if (!settings) return <div className="text-mist">Loading settings…</div>;

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-mist">API keys stay on the server and are never returned to the browser.</p>
      </div>

      <section className="card space-y-4 p-6">
        <h2 className="font-medium">API Keys</h2>
        <p className="text-sm text-mist">Outscraper {settings.api_keys.outscraper.configured ? settings.api_keys.outscraper.hint : "not configured"}</p>
        <input className="field" type="password" placeholder="New Outscraper key" value={outKey} onChange={(e) => setOutKey(e.target.value)} />
        <p className="text-sm text-mist">Claude {settings.api_keys.claude.configured ? settings.api_keys.claude.hint : "not configured"}</p>
        <input className="field" type="password" placeholder="New Anthropic key" value={claudeKey} onChange={(e) => setClaudeKey(e.target.value)} />
        <button
          className="btn btn-primary"
          onClick={async () => {
            await apiSend("/settings/keys", "POST", {
              outscraper_api_key: outKey || undefined,
              anthropic_api_key: claudeKey || undefined,
            });
            setOutKey("");
            setClaudeKey("");
            toast.success("Keys updated");
            load();
          }}
        >
          Save keys
        </button>
      </section>

      <section className="card space-y-4 p-6">
        <h2 className="font-medium">Model & defaults</h2>
        <label className="text-sm text-mist">Claude model</label>
        <input className="field" value={settings.claude_model} onChange={(e) => setSettings({ ...settings, claude_model: e.target.value })} />
        <div className="grid gap-3 md:grid-cols-2">
          <input className="field" value={settings.default_market} onChange={(e) => setSettings({ ...settings, default_market: e.target.value })} />
          <input className="field" value={settings.default_country} onChange={(e) => setSettings({ ...settings, default_country: e.target.value })} />
        </div>
        <button className="btn btn-primary" onClick={() => apiSend("/settings", "PATCH", settings).then(() => toast.success("Saved"))}>
          Save settings
        </button>
      </section>

      <section className="card space-y-3 p-6">
        <h2 className="font-medium">Qualification, statuses, types</h2>
        <p className="text-sm text-mist">Sales statuses: {settings.sales_statuses.join(", ")}</p>
        <p className="text-sm text-mist">Property types: {settings.property_types.join(", ")}</p>
        <p className="text-sm text-mist">Search categories: {settings.search_categories.join(", ")}</p>
      </section>

      <section className="card space-y-4 p-6">
        <h2 className="font-medium">Team</h2>
        <div className="grid gap-3 md:grid-cols-3">
          <input className="field" placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="field" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input className="field" placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <button
          className="btn btn-secondary"
          onClick={async () => {
            await apiSend("/auth/users", "POST", { email, password, name });
            toast.success("User created");
            setEmail("");
            setPassword("");
            setName("");
          }}
        >
          Add user
        </button>
      </section>

      <section className="card space-y-4 p-6">
        <h2 className="font-medium">Intelligence</h2>
        <p className="text-sm text-mist">Recalculate scores, property types, and company grouping without calling Claude or Outscraper.</p>
        <button
          className="btn btn-secondary"
          onClick={async () => {
            const result = await apiSend<{ leads: number; groups: number }>("/settings/recompute", "POST");
            toast.success(`Recomputed ${result.leads} leads · ${result.groups} groups`);
          }}
        >
          Recompute intelligence
        </button>
      </section>

      <section className="card space-y-4 p-6">
        <h2 className="font-medium">Imports</h2>
        <p className="text-sm text-mist">Existing CSVs are imported automatically on first launch. You can also upload more.</p>
        <input
          type="file"
          accept=".csv"
          onChange={async (event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            const body = new FormData();
            body.append("file", file);
            const result = await api<ImportRow>("/leads/import", { method: "POST", body });
            toast.success(`Imported ${result.imported}, updated ${result.updated}, duplicates ${result.duplicates}`);
            load();
          }}
        />
        <button
          className="btn btn-secondary"
          onClick={async () => {
            const rows = await apiSend<ImportRow[]>("/leads/import/existing", "POST");
            toast.success(`Processed ${rows.length} bundled files`);
            load();
          }}
        >
          Re-import bundled CSVs
        </button>
        <div className="space-y-2 text-sm">
          {imports.map((row) => (
            <div key={row.id} className="rounded-xl bg-white/5 px-3 py-2">
              {row.filename}: imported {row.imported}, updated {row.updated}, skipped {row.skipped}, duplicates {row.duplicates}, errors {row.errors}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
