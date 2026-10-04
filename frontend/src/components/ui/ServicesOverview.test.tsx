import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ServicesOverview } from "./ServicesOverview";

/**
 * 26: the overview is shared between the public storefront and the owner's
 * console preview. The owner-only Edit action is driven solely by the optional
 * `onEdit` prop, so a customer's DOM must be byte-identical without it.
 */
describe("ServicesOverview", () => {
  it("renders the heading and the entries without an owner action", () => {
    const html = renderToStaticMarkup(<ServicesOverview services={["Phone repair"]} />);
    expect(html).toContain("What we offer");
    expect(html).toContain("Phone repair");
    expect(html).not.toContain("services-overview-edit");
  });

  it("renders the owner Edit action when onEdit is given", () => {
    const html = renderToStaticMarkup(
      <ServicesOverview services={["Phone repair"]} onEdit={() => {}} />,
    );
    expect(html).toContain("What we offer");
    expect(html).toContain('data-testid="services-overview-edit"');
    expect(html).toContain(">Edit</button>");
  });

  it("renders nothing for empty services, with or without onEdit", () => {
    expect(renderToStaticMarkup(<ServicesOverview services={[]} />)).toBe("");
    expect(renderToStaticMarkup(<ServicesOverview services={[]} onEdit={() => {}} />)).toBe("");
  });
});
