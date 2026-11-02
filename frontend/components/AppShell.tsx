"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  Building2,
  CalendarCheck2,
  Download,
  LayoutDashboard,
  Upload,
  LogOut,
  Menu,
  Settings,
  Users,
  Workflow,
  X,
} from "lucide-react";
import { api, apiSend } from "@/lib/api";
import { cx } from "@/lib/utils";

const NAV = [
  {
    label: "Find",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      { href: "/campaigns", label: "Campaigns", icon: Building2 },
      { href: "/leads", label: "Leads", icon: Users },
    ],
  },
  {
    label: "Sell",
    items: [
      { href: "/pipeline", label: "Pipeline", icon: Workflow },
      { href: "/follow-ups", label: "Follow-ups", icon: CalendarCheck2 },
    ],
  },
  {
    label: "Data",
    items: [
      { href: "/imports", label: "Imports", icon: Upload },
      { href: "/exports", label: "Exports", icon: Download },
      { href: "/logs", label: "Logs", icon: Activity },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<{ name: string; email: string } | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api<{ name: string; email: string }>("/auth/me")
      .then((data) => {
        setUser(data);
        setReady(true);
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center text-mist">
        Loading workspace…
      </div>
    );
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[220px_1fr]">
      <aside className={cx("border-r border-white/[0.06] bg-[#101217] p-4 lg:sticky lg:top-0 lg:h-screen", open ? "block" : "hidden lg:block")}>
        <div className="mb-8 flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-accent">PulseHub</div>
            <div className="mt-1 text-lg font-semibold">Lead Engine</div>
          </div>
          <button className="lg:hidden" onClick={() => setOpen(false)}>
            <X size={18} />
          </button>
        </div>
        <nav className="space-y-6">
          {NAV.map((group) => (
            <div key={group.label}>
              <div className="mb-2 px-3 text-[10px] uppercase tracking-[0.18em] text-zinc-500">{group.label}</div>
              <div className="space-y-1">
                {group.items.map((item) => {
                  const active = pathname === item.href;
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setOpen(false)}
                      className={cx(
                        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm",
                        active ? "bg-white/10 text-white" : "text-mist hover:bg-white/5 hover:text-white"
                      )}
                    >
                      <Icon size={16} />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
        <div className="mt-10 rounded-2xl border border-white/10 p-3 text-xs text-mist">
          <div className="text-zinc-200">{user?.name}</div>
          <div className="truncate">{user?.email}</div>
          <button
            className="mt-3 flex items-center gap-2 text-zinc-300 hover:text-white"
            onClick={async () => {
              await apiSend("/auth/logout", "POST");
              router.replace("/login");
            }}
          >
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>
      <div>
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-white/10 bg-ink-950/80 px-4 py-3 backdrop-blur lg:hidden">
          <div className="font-medium">PulseHub Lead Engine</div>
          <button onClick={() => setOpen(true)}>
            <Menu size={18} />
          </button>
        </header>
        <main className="p-4 md:p-8">{children}</main>
      </div>
    </div>
  );
}
