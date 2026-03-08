"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, CheckCircle, Clock, AlertCircle } from "lucide-react";
import { Suspense } from "react";

function ActivateContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<
    "loading" | "activated" | "pending" | "error"
  >("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("No activation token provided.");
      return;
    }

    async function activate() {
      try {
        const res = await fetch("/api/proxy/api/auth/activate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ signup_token: token }),
        });
        const data = await res.json();
        if (data.status === "activated" || data.status === "already_active") {
          setStatus("activated");
          setMessage(data.message || "Account activated successfully.");
        } else if (data.status === "pending") {
          setStatus("pending");
          setMessage(
            data.message || "Payment is still processing. Please wait."
          );
        } else {
          setStatus("error");
          setMessage(data.message || data.detail || "Activation failed.");
        }
      } catch {
        setStatus("error");
        setMessage("Network error. Please try again.");
      }
    }

    activate();
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-lg">Account Activation</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4 text-center">
          {status === "loading" && (
            <>
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">
                Activating your account...
              </p>
            </>
          )}
          {status === "activated" && (
            <>
              <CheckCircle className="h-8 w-8 text-green-400" />
              <p className="text-sm">{message}</p>
              <a href="/login" className="inline-flex h-8 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground">
                Sign in
              </a>
            </>
          )}
          {status === "pending" && (
            <>
              <Clock className="h-8 w-8 text-yellow-400" />
              <p className="text-sm">{message}</p>
              <Button
                variant="outline"
                onClick={() => window.location.reload()}
              >
                Check again
              </Button>
            </>
          )}
          {status === "error" && (
            <>
              <AlertCircle className="h-8 w-8 text-destructive" />
              <p className="text-sm text-destructive">{message}</p>
              <a href="/signup" className="inline-flex h-8 items-center rounded-lg border border-border bg-background px-4 text-sm font-medium hover:bg-muted">
                Try again
              </a>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function ActivatePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-background">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      }
    >
      <ActivateContent />
    </Suspense>
  );
}
