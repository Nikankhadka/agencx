/**
 * 20: the owner's own overview of what they do, in the words they typed during
 * the interview - including any rough price they put there themselves ("coffee,
 * $4 to $10"). It is copied, never computed: this block states nothing the owner
 * did not state, and it quotes nothing. Exact prices belong to offerings and the
 * pricing engine, which own the "What we offer" heading whenever the catalog has
 * anything in it - so the two never render together and never disagree.
 *
 * Shared across the route trees on purpose: the public storefront and the
 * owner's preview of it have to show the same block, or the preview is lying.
 */
export function ServicesOverview({
  services,
  className,
}: {
  services: string[];
  className?: string;
}) {
  const entries = services.map((entry) => entry.trim()).filter(Boolean);
  if (entries.length === 0) return null;
  return (
    <section data-testid="services-overview" className={className}>
      <div className="rounded-card bg-surface-container p-4">
        <h3 className="text-label font-medium uppercase text-text-secondary">What we offer</h3>
        <ul className="mt-3 divide-y divide-hairline">
          {entries.map((entry, index) => (
            <li
              key={`${index}-${entry}`}
              className="min-w-0 wrap-anywhere py-2 text-body-sm text-text first:pt-0 last:pb-0"
            >
              {entry}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
