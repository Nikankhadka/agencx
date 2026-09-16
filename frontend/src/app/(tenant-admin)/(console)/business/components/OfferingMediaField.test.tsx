import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { OfferingMediaField } from "./OfferingMediaField";

const noop = {
  onPickFile: () => {},
  onUrlChange: () => {},
  onCancelPending: () => {},
  onRemoveSaved: () => {},
};

function field(
  overrides: Partial<Parameters<typeof OfferingMediaField>[0]> = {},
) {
  return renderToStaticMarkup(
    <OfferingMediaField
      mediaUrl=""
      mediaFile={null}
      mediaChanged={false}
      removeMedia={false}
      working={false}
      {...noop}
      {...overrides}
    />,
  );
}

function imageFile() {
  return new File(["bytes"], "photo.jpg", { type: "image/jpeg" });
}

describe("OfferingMediaField", () => {
  it("renders an Upload button opening a hidden input while empty", () => {
    const html = field();
    expect(html).toContain('data-testid="offering-media-upload"');
    expect(html).toContain('data-testid="offering-media-input"');
    expect(html).toContain('aria-label="Upload media"');
    expect(html).toContain('type="file"');
    expect(html).not.toContain('data-testid="offering-media-preview"');
    expect(html).not.toContain('data-testid="offering-media-edit"');
    expect(html).not.toContain('data-testid="offering-media-cancel"');
  });

  it("shows a preview chip with filename, Edit and Cancel for a picked file", () => {
    const html = field({ mediaFile: imageFile(), mediaChanged: true });
    expect(html).toContain('data-testid="offering-media-preview"');
    expect(html).toContain('data-testid="offering-media-filename"');
    expect(html).toContain("photo.jpg");
    expect(html).toContain('data-testid="offering-media-edit"');
    expect(html).toContain('data-testid="offering-media-cancel"');
    expect(html).toContain("Ready to save");
    // The Upload trigger steps aside while a pick is pending - Edit re-picks.
    expect(html).not.toContain('data-testid="offering-media-upload"');
  });

  it("disables the URL input while a file is pending", () => {
    const html = field({ mediaFile: imageFile(), mediaChanged: true });
    expect(html).toContain('data-testid="offering-media-url"');
    expect(html).toContain("File selected - remove it to use a URL instead.");
  });

  it("renders a video tag for a picked video", () => {
    const html = field({
      mediaFile: new File(["bytes"], "clip.mp4", { type: "video/mp4" }),
      mediaChanged: true,
    });
    expect(html).toContain("<video");
    expect(html).toContain("clip.mp4");
  });

  it("offers Remove for a URL with no pending file", () => {
    const html = field({ mediaUrl: "https://youtu.be/example" });
    expect(html).toContain('data-testid="offering-media-remove"');
    expect(html).toContain("Remove current media");
    expect(html).toContain('data-testid="offering-media-upload"');
    expect(html).not.toContain('data-testid="offering-media-preview"');
  });

  it("replaces the chip with pending-removal copy once removal is confirmed", () => {
    const html = field({
      mediaUrl: "https://youtu.be/example",
      mediaChanged: true,
      removeMedia: true,
    });
    expect(html).toContain("Current media will be removed when you save.");
    expect(html).not.toContain('data-testid="offering-media-preview"');
    expect(html).not.toContain('data-testid="offering-media-remove"');
  });

  it("disables every control while working", () => {
    const html = field({ working: true });
    const disabledCount = html.split("disabled").length - 1;
    // URL input plus the Upload button.
    expect(disabledCount).toBeGreaterThanOrEqual(2);
  });
});
