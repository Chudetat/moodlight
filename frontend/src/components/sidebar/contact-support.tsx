"use client";

import { useState } from "react";
import { useSendSupport } from "@/lib/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function ContactSupport() {
  const [message, setMessage] = useState("");
  const sendSupport = useSendSupport();
  const [sent, setSent] = useState(false);

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase text-muted-foreground">
        Contact Support
      </p>
      {sent ? (
        <p className="text-xs text-muted-foreground">
          Sent! We&apos;ll get back to you soon.
        </p>
      ) : (
        <div className="space-y-1">
          <Textarea
            placeholder="Describe your issue..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="min-h-16 text-xs"
          />
          <Button
            size="sm"
            variant="outline"
            className="w-full text-xs"
            disabled={!message.trim() || sendSupport.isPending}
            onClick={() => {
              sendSupport.mutate(
                { message: message.trim() },
                {
                  onSuccess: () => {
                    setSent(true);
                    setMessage("");
                    setTimeout(() => setSent(false), 5000);
                  },
                }
              );
            }}
          >
            {sendSupport.isPending ? "Sending..." : "Send"}
          </Button>
          {sendSupport.isError && (
            <p className="text-xs text-destructive">
              {(sendSupport.error as Error).message}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
