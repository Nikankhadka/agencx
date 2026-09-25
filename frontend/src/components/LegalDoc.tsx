import type { ReactNode } from "react";
import { Container } from "@/components/ui/Container";

/**
 * The shell the privacy page and the terms share: a readable single column with
 * a title, a last-updated line and numbered-by-heading sections. Static server
 * markup, no client JS - a legal page has to load for someone whose browser
 * script failed.
 */
export function LegalDoc({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <main className="flex-1 py-12">
      <Container className="flex flex-col gap-8 text-prose text-text-secondary">
        <header className="flex flex-col gap-2">
          <span className="text-meta font-medium text-text">Agencx</span>
          <h1 className="text-title-1 font-semibold text-text">{title}</h1>
          <p className="text-meta text-text-tertiary">Last updated {updated}</p>
        </header>
        {children}
      </Container>
    </main>
  );
}

export function LegalSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-title-3 font-semibold text-text">{title}</h2>
      {children}
    </section>
  );
}

/** A bulleted list, since Tailwind's reset strips list markers. */
export function LegalList({ children }: { children: ReactNode }) {
  return <ul className="flex list-disc flex-col gap-2 pl-5">{children}</ul>;
}
