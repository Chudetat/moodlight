"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html>
      <body style={{ padding: 40, fontFamily: "monospace", background: "#0e1117", color: "#fafafa" }}>
        <h2>Dashboard Error</h2>
        <pre style={{ color: "#ff4b4b", whiteSpace: "pre-wrap", maxWidth: 800 }}>
          {error.message}
        </pre>
        <pre style={{ color: "#8b8b9e", whiteSpace: "pre-wrap", maxWidth: 800, fontSize: 12 }}>
          {error.stack}
        </pre>
        <button
          onClick={reset}
          style={{ marginTop: 20, padding: "8px 16px", cursor: "pointer" }}
        >
          Try again
        </button>
      </body>
    </html>
  );
}
