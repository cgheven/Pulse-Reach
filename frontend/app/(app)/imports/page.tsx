"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, apiGet, apiSend } from "@/lib/api";

type ImportRow = {
  id: string;
  filename: string;
  imported: number;
  updated: number;
  skipped: number;
  duplicates: number;
  errors: number;
  created_at?: string;
};

export default function ImportsPage() {
  const [imports, setImports] = useState<ImportRow[]>([]);

  async function load() {
    setImports(await apiGet<ImportRow[]>("/leads/imports"));
  }

  useEffect(() => {
    load().catch((error) => toast.error(error.message));
  }, []);

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Imports</h1>
        <p className="text-sm text-mist">Existing qualified leads stay intact. Blanks never overwrite good data.</p>
      </div>
      <div className="card space-y-4 p-6">
        <input
          type="file"
          accept=".csv"
          onChange={async (event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            const body = new FormData();
            body.append("file", file);
            const result = await api<ImportRow>("/leads/import", { method: "POST", body });
            toast.success(`Imported ${result.imported}, updated ${result.updated}, duplicates ${result.duplicates}, errors ${result.errors}`);
            load();
          }}
        />
        <button
          className="btn btn-secondary"
          onClick={async () => {
            if (!confirm("Re-import bundled CSVs? Existing sales notes and manual changes will not be overwritten.")) return;
            const rows = await apiSend<ImportRow[]>("/leads/import/existing", "POST");
            toast.success(`Processed ${rows.length} bundled files`);
            load();
          }}
        >
          Re-import bundled CSVs
        </button>
      </div>
      <div className="space-y-2">
        {imports.map((row) => (
          <div key={row.id} className="card px-4 py-3 text-sm">
            <div className="font-medium">{row.filename}</div>
            <div className="mt-1 text-mist">
              Imported {row.imported} · Updated {row.updated} · Skipped {row.skipped} · Duplicates {row.duplicates} · Errors {row.errors}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
