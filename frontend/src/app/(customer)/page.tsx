import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { brandStyle } from "@/lib/brand";
import { customerSurfaceConfig, resolveTenantBySlug, SLUG_HEADER } from "@/lib/tenant";
import { BrandMark } from "@/components/ui/BrandMark";
import { CustomerChat } from "./CustomerChat";

/**
 * T-005/T-011/T-032: the customer surface. Resolves the slug proxy.ts attached
 * to the request (server-side, so brand never flashes to default), injects the
 * tenant's accent override (frontend.md section 5 - derived steps, AA contrast
 * fallback handled inside brandStyle), shows the calm not-found state for an
 * unknown slug and the unavailable state for a suspended tenant, then hands
 * off to CustomerChat with the tenant-configured greeting + starter chips.
 */
export default async function CustomerHome() {
  const slug = (await headers()).get(SLUG_HEADER);
  if (!slug) notFound();

  const tenant = await resolveTenantBySlug(slug);
  if (!tenant) notFound();

  const displayName = (tenant.brand.display_name as string | undefined) ?? tenant.name;
  const logoUrl = tenant.brand.logo_url as string | undefined;
  const accentOverride = brandStyle(tenant.brand);
  const { greeting, starterQuestions } = customerSurfaceConfig(tenant.customer);

  if (tenant.status === "suspended") {
    return (
      <main className="flex flex-1 flex-col items-center justify-center gap-2 px-4 text-center sm:px-8">
        <h1 className="text-title-2 font-semibold text-text">{displayName}</h1>
        <p className="text-body text-text-secondary">
          This page is currently unavailable.
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex h-dvh w-full max-w-[720px] flex-col">
      {accentOverride ? <style>{accentOverride}</style> : null}
      <header className="flex items-center gap-3 border-b border-border px-4 py-4 sm:px-6">
        <BrandMark logoUrl={logoUrl} name={displayName} />
        <h1 className="text-title-3 font-semibold text-text">{displayName}</h1>
      </header>
      <CustomerChat
        slug={slug}
        displayName={displayName}
        greeting={greeting}
        starterQuestions={starterQuestions}
      />
    </main>
  );
}
