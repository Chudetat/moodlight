"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Login failed");
        return;
      }

      router.push("/");
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-6">
      <div className="mb-16 max-w-3xl text-center">
        <div className="mb-10 flex justify-center">
          <Image
            src="/logo.png"
            alt="Moodlight"
            width={180}
            height={36}
            className="h-9 w-auto"
            priority
          />
        </div>
        <h1 className="text-3xl font-light leading-relaxed tracking-tight text-foreground/90 sm:text-[2.75rem] sm:leading-snug">
          Moodlight is the only real-time intelligence platform<br className="hidden sm:inline" />
          {" "}custom engineered for brands<br className="hidden sm:inline" />
          {" "}that move at the speed of culture.
        </h1>
      </div>
      <div className="w-full max-w-sm">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-1.5">
            <Label htmlFor="email" className="text-xs font-normal uppercase tracking-widest text-muted-foreground">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              placeholder="you@company.com"
              className="border-0 border-b border-border bg-transparent rounded-none px-0 text-base focus-visible:ring-0 focus-visible:border-foreground/40 transition-colors"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password" className="text-xs font-normal uppercase tracking-widest text-muted-foreground">
              Password
            </Label>
            <Input
              id="password"
              type="password"
              className="border-0 border-b border-border bg-transparent rounded-none px-0 text-base focus-visible:ring-0 focus-visible:border-foreground/40 transition-colors"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <Button
            type="submit"
            className="w-full mt-4 bg-foreground/10 hover:bg-foreground/15 text-foreground border border-foreground/20 rounded-full transition-all"
            variant="ghost"
            disabled={loading}
          >
            {loading ? "Signing in..." : "Sign in"}
          </Button>

          <p className="text-center text-xs text-muted-foreground pt-2">
            Don&apos;t have an account?{" "}
            <a href="/signup" className="text-foreground/60 hover:text-foreground transition-colors">
              Sign up
            </a>
          </p>
        </form>
      </div>
    </div>
  );
}
