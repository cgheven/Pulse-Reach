"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { apiSend } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@pulsehub.local");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      await apiSend("/auth/login", "POST", { email, password });
      router.replace("/");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <form onSubmit={submit} className="card w-full max-w-md p-8">
        <div className="text-xs uppercase tracking-[0.24em] text-accent">PulseHub</div>
        <h1 className="mt-2 text-2xl font-semibold">Lead Engine</h1>
        <p className="mt-2 text-sm text-mist">Internal sales workspace. Sign in to continue.</p>
        <label className="mt-8 block text-sm text-mist">Email</label>
        <input className="field mt-1" type="text" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <label className="mt-4 block text-sm text-mist">Password</label>
        <input className="field mt-1" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <button className="btn btn-primary mt-6 w-full" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
