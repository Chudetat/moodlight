"use client";

import { useRef, useState, useEffect, type ReactNode } from "react";

interface LazySectionProps {
  children: ReactNode;
  fallback?: ReactNode;
  rootMargin?: string;
  className?: string;
}

/**
 * IntersectionObserver wrapper — only renders children
 * when the section enters (or is about to enter) the viewport.
 */
export function LazySection({
  children,
  fallback,
  rootMargin = "200px",
  className,
}: LazySectionProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [rootMargin]);

  return (
    <div ref={ref} className={className}>
      {visible ? children : (fallback ?? <SectionSkeleton />)}
    </div>
  );
}

function SectionSkeleton() {
  return (
    <div className="space-y-3 rounded-lg border border-border bg-card p-6">
      <div className="h-5 w-48 animate-pulse rounded bg-muted" />
      <div className="h-40 animate-pulse rounded bg-muted" />
    </div>
  );
}
