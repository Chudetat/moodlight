"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SignupPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [plan, setPlan] = useState<"monthly" | "annually">("monthly");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/proxy/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password, plan }),
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Signup failed.");
        return;
      }

      // Redirect to Stripe or activation page
      if (data.stripe_url) {
        window.location.href = data.stripe_url;
      } else {
        window.location.href = `/activate?token=${data.signup_token}`;
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <div className="mb-2 text-2xl font-bold tracking-tight">
            Moodlight
          </div>
          <CardTitle className="text-lg font-normal text-muted-foreground">
            Create your account
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>

            <div className="space-y-2">
              <Label>Plan</Label>
              <div className="flex gap-2">
                <button
                  type="button"
                  className={`flex flex-1 flex-col items-center rounded-lg border p-3 text-sm transition-colors ${
                    plan === "monthly"
                      ? "border-primary bg-primary/10 text-foreground"
                      : "border-border text-muted-foreground hover:border-primary/50"
                  }`}
                  onClick={() => setPlan("monthly")}
                >
                  <span className="font-medium">Monthly</span>
                  <span className="text-lg font-bold">$899</span>
                  <span className="text-[10px]">/month</span>
                </button>
                <button
                  type="button"
                  className={`flex flex-1 flex-col items-center rounded-lg border p-3 text-sm transition-colors ${
                    plan === "annually"
                      ? "border-primary bg-primary/10 text-foreground"
                      : "border-border text-muted-foreground hover:border-primary/50"
                  }`}
                  onClick={() => setPlan("annually")}
                >
                  <span className="font-medium">Annual</span>
                  <span className="text-lg font-bold">$8,999</span>
                  <span className="text-[10px]">/year (save 17%)</span>
                </button>
              </div>
            </div>

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Creating account..." : "Sign up"}
            </Button>

            <p className="text-center text-xs text-muted-foreground">
              Already have an account?{" "}
              <a href="/login" className="text-primary hover:underline">
                Sign in
              </a>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
