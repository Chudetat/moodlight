import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Signal Track Record | Moodlight Intelligence",
  description:
    "How Moodlight's AI predictions performed against real market outcomes. Every signal is logged, every outcome is tracked.",
  openGraph: {
    title: "Signal Track Record | Moodlight Intelligence",
    description:
      "How Moodlight's AI predictions performed against real market outcomes.",
    type: "website",
    siteName: "Moodlight",
  },
};

export default function TrackRecordLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
