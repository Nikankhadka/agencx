import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { BusinessProfile } from "@/lib/api-schemas";
import { ContactSheet } from "./ContactSheet";

const profile: BusinessProfile = {
  name: "Bytefix Repairs",
  hours: "",
  description: "",
  business_contact: "owner@bytefix.dev",
  abn: "",
  gst: "",
  services: [],
  customer_voice_preset: "warm_casual",
  customer_voice_custom_style: "",
};

function markup(overrides: Partial<BusinessProfile> = {}) {
  return renderToStaticMarkup(
    <ContactSheet
      open
      profile={{ ...profile, ...overrides }}
      busy={false}
      error={null}
      onClose={() => {}}
      onSave={() => {}}
    />,
  );
}

describe("ContactSheet", () => {
  it("renders one contact field with the phone toggle, Save and Cancel", () => {
    const html = markup();
    expect(html).toContain('data-testid="contact-detail-input"');
    expect(html).toContain('data-testid="contact-phone-toggle"');
    expect(html).toContain('data-testid="contact-save"');
    expect(html).toContain('data-testid="contact-cancel"');
    expect(html).toContain("owner@bytefix.dev");
    expect(html).toContain("Phone number");
  });

  it("has no contact name field", () => {
    expect(markup()).not.toContain("contact-name-input");
  });
});
