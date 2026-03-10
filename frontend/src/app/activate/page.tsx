"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, CheckCircle, Clock, AlertCircle } from "lucide-react";
import { Suspense } from "react";

const MAX_POLLS = 20;
const POLL_INTERVAL_MS = 3000;

function ActivateContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<
    "loading" | "activated" | "pending" | "error"
  >("loading");
  const [message, setMessage] = useState("");
  const [polling, setPolling] = useState(false);
  const pollCount = useRef(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setPolling(false);
  }, []);

  const checkActivation = useCallback(async () => {
    if (!token) return;
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
        stopPolling();
      } else if (data.status === "pending") {
        setStatus("pending");
        setMessage(
          data.message || "Payment is still processing. Please wait."
        );
      } else {
        setStatus("error");
        setMessage(data.message || data.detail || "Activation failed.");
        stopPolling();
      }
    } catch {
      setStatus("error");
      setMessage("Network error. Please try again.");
      stopPolling();
    }
  }, [token, stopPolling]);

  // Initial activation check
  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("No activation token provided.");
      return;
    }
    checkActivation();
  }, [token, checkActivation]);

  // Start auto-polling when status becomes "pending"
  useEffect(() => {
    if (status !== "pending" || intervalRef.current) return;

    pollCount.current = 0;
    setPolling(true);

    intervalRef.current = setInterval(() => {
      pollCount.current += 1;
      if (pollCount.current >= MAX_POLLS) {
        stopPolling();
        return;
      }
      checkActivation();
    }, POLL_INTERVAL_MS);

    return () => stopPolling();
  }, [status, checkActivation, stopPolling]);

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
              {polling ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Checking...
                </div>
              ) : (
                <Button
                  variant="outline"
                  onClick={() => {
                    pollCount.current = 0;
                    setPolling(true);
                    checkActivation();
                    intervalRef.current = setInterval(() => {
                      pollCount.current += 1;
                      if (pollCount.current >= MAX_POLLS) {
                        stopPolling();
                        return;
                      }
                      checkActivation();
                    }, POLL_INTERVAL_MS);
                  }}
                >
                  Check again
                </Button>
              )}
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
