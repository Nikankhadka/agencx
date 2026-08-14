"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Icon, type IconName } from "@/components/ui/Icon";
import { BrandMark } from "@/components/ui/BrandMark";
import { Drawer } from "@/components/ui/Drawer";
import { useAuth } from "@/components/AuthProvider";
import { apiFetch } from "@/lib/api";

/**
 * T-031: the Surface-2 admin-console shell (frontend.md 7.2). A left sidebar
 * nav wraps every authed console page; login/signup stay outside this route
 * group and keep their own centered-card layout. Route groups never appear in
 * the URL, so /knowledge and /onboarding are unchanged by living under
 * (console).
 *
 * Settings is specced (7.2) but lands later - it renders as a visibly-disabled
 * item rather than a dead link so the nav is honest about what exists today.
 * Dashboards (T-034) is temporarily hidden: its nav item is removed and
 * /dashboards redirects to /onboarding (next.config.ts redirects()).
 *
 * 7.2 specs "icons + labels": each item carries a Material Symbol; the active
 * item is an accent-container pill with the filled glyph, inactive items are
 * quiet text with the outlined glyph.
 */
const NAV_ITEMS: { href: string; label: string; icon: IconName }[] = [
  { href: "/onboarding", label: "Onboarding", icon: "rocket_launch" },
  { href: "/knowledge", label: "Knowledge", icon: "folder_open" },
  { href: "/conversations", label: "Conversations", icon: "forum" },
  { href: "/escalations", label: "Escalations", icon: "support_agent" },
  { href: "/pricing", label: "Pricing", icon: "sell" },
];

const SOON_ITEMS = ["Settings"] as const;

interface TenantMe {
  slug: string;
  name: string;
  brand?: Record<string, unknown>;
}

export default function ConsoleLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { session, isLoading, signOut } = useAuth();
  const [tenant, setTenant] = useState<TenantMe | null>(null);
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && !session) {
      router.replace("/");
    }
  }, [isLoading, session, router]);

  useEffect(() => {
    if (!session) return;
    apiFetch<TenantMe>("/api/tenants/me")
      .then(setTenant)
      .catch(() => setTenant(null));
  }, [session]);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect -- deliberate drawer reset on navigation */
    setNavOpen(false);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [pathname]);

  if (isLoading) {
    return <div aria-busy="true" className="h-dvh bg-bg" />;
  }
  if (!session) return null;

  const displayName =
    (tenant?.brand?.["display_name"] as string | undefined) ?? tenant?.name ?? "Wren";
  const logoUrl = tenant?.brand?.["logo_url"] as string | undefined;

  const navContent = (
    <>
      <span className="flex items-center gap-2.5 px-3 py-2">
        <BrandMark logoUrl={logoUrl} name={displayName} />
        <span className="truncate text-title-3 font-semibold text-text">{displayName}</span>
      </span>
      <ul className="mt-2 flex flex-col gap-0.5">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={[
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-body-sm font-medium transition-colors duration-fast",
                  active
                    ? "bg-accent-container text-text-inverse"
                    : "text-text-secondary hover:bg-surface-container hover:text-text",
                ].join(" ")}
              >
                <Icon name={item.icon} filled={active} size={20} />
                {item.label}
              </Link>
            </li>
          );
        })}
        {SOON_ITEMS.map((label) => (
          <li key={label}>
            <span
              aria-disabled="true"
              className="flex items-center justify-between rounded-md px-3 py-2 text-body-sm font-medium text-text-tertiary"
            >
              {label}
              <span className="rounded-full bg-surface px-2 py-0.5 text-caption font-medium text-text-tertiary">
                soon
              </span>
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-auto pt-4">
        <button
          onClick={() => signOut()}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-body-sm font-medium text-text-secondary hover:bg-surface-container hover:text-text transition-colors duration-fast"
        >
          <Icon name="logout" filled={false} size={20} />
          Sign out
        </button>
      </div>
    </>
  );

  return (
    <div className="flex h-dvh w-full">
      <nav
        aria-label="Console"
        className="hidden w-56 shrink-0 flex-col gap-1 border-r border-border bg-surface-sunken p-4 lg:flex"
      >
        {navContent}
      </nav>

      <Drawer open={navOpen} onClose={() => setNavOpen(false)}>
        {navContent}
      </Drawer>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-surface px-4 lg:hidden">
          <button type="button" onClick={() => setNavOpen(true)} aria-label="Menu">
            <Icon name="menu" size={24} />
          </button>
          <span className="truncate text-title-3 font-semibold text-text">{displayName}</span>
        </header>
        {children}
      </div>
    </div>
  );
}
