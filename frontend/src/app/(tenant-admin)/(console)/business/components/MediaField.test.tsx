import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MediaField } from "./MediaField";

const noop = {
  onFile: () => {},
  onCancel: () => {},
  onRemove: () => {},
};

function cover(overrides: Partial<Parameters<typeof MediaField>[0]> = {}) {
  return renderToStaticMarkup(
    <MediaField
      variant="cover"
      state="empty"
      hint="Tap to add a cover photo"
      pickLabel="Add a cover photo"
      accept="image/jpeg,image/png,image/webp"
      testIds={{
        field: "booking-cover",
        input: "booking-cover-input",
        remove: "booking-cover-remove",
      }}
      {...noop}
      {...overrides}
    />,
  );
}

function offering(overrides: Partial<Parameters<typeof MediaField>[0]> = {}) {
  return renderToStaticMarkup(
    <MediaField
      variant="offering"
      state="empty"
      pickLabel="Upload media"
      accept="image/*,video/*"
      testIds={{
        field: "offering-media-upload",
        input: "offering-media-input",
        preview: "offering-media-preview",
        filename: "offering-media-filename",
        edit: "offering-media-edit",
        cancel: "offering-media-cancel",
        remove: "offering-media-remove",
      }}
      {...noop}
      {...overrides}
    />,
  );
}

describe("MediaField", () => {
  describe("cover variant", () => {
    it("invites a photo while empty and offers no removal", () => {
      const html = cover();
      expect(html).toContain('data-testid="booking-cover"');
      expect(html).toContain('data-testid="booking-cover-input"');
      expect(html).toContain("Tap to add a cover photo");
      expect(html).not.toContain("Edit photo");
      expect(html).not.toContain('data-testid="booking-cover-remove"');
    });

    it("keeps removal absent while empty even when removal is wired", () => {
      const html = cover({ onRemove: noop.onRemove });
      expect(html).not.toContain('data-testid="booking-cover-remove"');
    });

    it("shows the chosen file and the Edit photo control while uploading", () => {
      const html = cover({ state: "uploading", src: "blob:preview" });
      expect(html).toContain("<img");
      expect(html).toContain("blob:preview");
      expect(html).toContain("Edit photo");
    });

    it("shows the explicit remove affordance once a cover exists", () => {
      const html = cover({
        state: "saved",
        src: "blob:saved",
        onRemove: noop.onRemove,
        removeLabel: "Remove",
      });
      expect(html).toContain('data-testid="booking-cover-remove"');
      expect(html).toContain("Remove");
    });

    it("renders the busy hint, not the empty hint, while uploading", () => {
      const html = cover({ state: "uploading", busyHint: "Loading…" });
      expect(html).toContain("Loading…");
      expect(html).not.toContain("Tap to add a cover photo");
    });

    it("disables every control while a save is in flight", () => {
      const html = cover({
        state: "saved",
        src: "blob:saved",
        disabled: true,
        onRemove: noop.onRemove,
      });
      // The slot, the Edit pill and the Remove pill all carry disabled.
      const disabledCount = html.split("disabled").length - 1;
      expect(disabledCount).toBeGreaterThanOrEqual(3);
    });

    it("uses the pick label it is given, so a set cover reads as a change", () => {
      expect(cover({ pickLabel: "Change cover photo" })).toContain(
        'aria-label="Change cover photo"',
      );
    });
  });

  describe("offering variant", () => {
    it("renders an Upload button and hidden input while empty", () => {
      const html = offering();
      expect(html).toContain('data-testid="offering-media-upload"');
      expect(html).toContain('data-testid="offering-media-input"');
      expect(html).toContain('aria-label="Upload media"');
      expect(html).not.toContain('data-testid="offering-media-preview"');
      expect(html).not.toContain('data-testid="offering-media-remove"');
    });

    it("shows a preview chip with filename, Edit and Cancel for a picked file", () => {
      const html = offering({
        state: "preview",
        kind: "image",
        src: "blob:picked",
        filename: "photo.jpg",
        detail: "24 KB - Ready to save",
      });
      expect(html).toContain('data-testid="offering-media-preview"');
      expect(html).toContain('data-testid="offering-media-filename"');
      expect(html).toContain("photo.jpg");
      expect(html).toContain("24 KB - Ready to save");
      expect(html).toContain('data-testid="offering-media-edit"');
      expect(html).toContain('data-testid="offering-media-cancel"');
      // The Upload trigger steps aside while a pick is pending - Edit re-picks.
      expect(html).not.toContain('data-testid="offering-media-upload"');
    });

    it("renders a video tag for a picked video", () => {
      const html = offering({
        state: "preview",
        kind: "video",
        src: "blob:clip",
        filename: "clip.mp4",
        detail: "2.0 MB - Ready to save",
      });
      expect(html).toContain("<video");
      expect(html).toContain("blob:clip");
      expect(html).toContain("clip.mp4");
    });

    it("offers explicit removal for saved media with no pending pick", () => {
      const html = offering({
        state: "saved",
        src: "https://example.test/photo.jpg",
        onRemove: noop.onRemove,
        removeLabel: "Remove current media",
      });
      expect(html).toContain('data-testid="offering-media-remove"');
      expect(html).toContain("Remove current media");
      expect(html).toContain('data-testid="offering-media-upload"');
    });

    it("hides removal while a pending pick is previewed", () => {
      const html = offering({
        state: "preview",
        src: "blob:picked",
        filename: "photo.jpg",
        detail: "24 KB - Ready to save",
        onRemove: noop.onRemove,
        removeLabel: "Remove current media",
      });
      expect(html).not.toContain('data-testid="offering-media-remove"');
    });

    it("disables the controls while working", () => {
      const html = offering({ disabled: true });
      const disabledCount = html.split("disabled").length - 1;
      // The hidden input is not disabled, so the Upload button is the one hit.
      expect(disabledCount).toBeGreaterThanOrEqual(1);
    });
  });
});
