"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div style={{ padding: 40, fontFamily: "monospace" }}>
      <h2 style={{ color: "#ff4b4b" }}>Something went wrong</h2>
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
    </div>
  );
}
