import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { ProfileUpdate } from "@/lib/api-schemas";
import { ProfileFieldSheet } from "./ProfileFieldSheet";

function markup(
  field: keyof ProfileUpdate,
  value: string,
  { multiline = false }: { multiline?: boolean } = {},
) {
  return renderToStaticMarkup(
    <ProfileFieldSheet
      open
      field={field}
      title="Edit"
      label="Field"
      value={value}
      multiline={multiline}
      busy={false}
      error={null}
      onClose={() => {}}
      onSave={() => {}}
    />,
  );
}

/**
 * RF-7: the storefront shortcuts reuse these exact editors, so the editor's
 * static contract is pinned here next to the component (mirroring
 * ContactSheet.test.tsx). Opening wiring and Save/Cancel behavior are E2E.
 */
describe("ProfileFieldSheet", () => {
  it("renders the name editor with the current value and Save/Cancel", () => {
    const html = markup("name", "Bytefix Repairs");
    expect(html).toContain('data-testid="profile-name-input"');
    expect(html).toContain("Bytefix Repairs");
    expect(html).toContain('data-testid="profile-name-save"');
    expect(html).toContain('data-testid="profile-name-cancel"');
  });

  it("renders the hours editor with the current value and Save/Cancel", () => {
    const html = markup("hours", "Mon to Fri 9am to 6pm");
    expect(html).toContain('data-testid="profile-hours-input"');
    expect(html).toContain("Mon to Fri 9am to 6pm");
    expect(html).toContain('data-testid="profile-hours-save"');
    expect(html).toContain('data-testid="profile-hours-cancel"');
  });

  it("renders the description editor as a multiline field", () => {
    const html = markup("description", "A friendly repair shop.", { multiline: true });
    expect(html).toContain("<textarea");
    expect(html).toContain('data-testid="profile-description-input"');
    expect(html).toContain("A friendly repair shop.");
  });
});
