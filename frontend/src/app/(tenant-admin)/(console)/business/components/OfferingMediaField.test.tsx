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
  it("starts on Upload with the picker and no URL field while empty", () => {
    const html = field();
    expect(html).toContain('data-testid="offering-media-mode-upload"');
    expect(html).toContain('data-testid="offering-media-mode-url"');
    expect(html).toContain('data-testid="offering-media-upload"');
    expect(html).toContain('data-testid="offering-media-input"');
    expect(html).toContain('aria-label="Upload media"');
    expect(html).toContain('type="file"');
    expect(html).not.toContain('data-testid="offering-media-url"');
    expect(html).not.toContain('data-testid="offering-media-preview"');
    expect(html).not.toContain('data-testid="offering-media-edit"');
    expect(html).not.toContain('data-testid="offering-media-cancel"');
  });

  it("opens a saved URL in the URL field with Remove, no upload button", () => {
    const html = field({ mediaUrl: "https://youtu.be/example" });
    expect(html).toContain('data-testid="offering-media-url"');
    expect(html).toContain("https://youtu.be/example");
    expect(html).toContain('data-testid="offering-media-remove"');
    expect(html).toContain("Remove current media");
    expect(html).not.toContain('data-testid="offering-media-upload"');
    expect(html).not.toContain('data-testid="offering-media-preview"');
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
    // A pending pick keeps the URL side out of the DOM entirely.
    expect(html).not.toContain('data-testid="offering-media-url"');
  });

  it("renders a video tag for a picked video", () => {
    const html = field({
      mediaFile: new File(["bytes"], "clip.mp4", { type: "video/mp4" }),
      mediaChanged: true,
    });
    expect(html).toContain("<video");
    expect(html).toContain("clip.mp4");
  });

  it("replaces the URL field with pending-removal copy once removal is confirmed", () => {
    const html = field({
      mediaUrl: "https://youtu.be/example",
      mediaChanged: true,
      removeMedia: true,
    });
    expect(html).toContain('data-testid="offering-media-url"');
    expect(html).toContain("Current media will be removed when you save.");
    expect(html).not.toContain('data-testid="offering-media-remove"');
    expect(html).not.toContain('data-testid="offering-media-preview"');
  });

  it("disables the mode toggle and the visible control while working", () => {
    const html = field({ working: true });
    const disabledCount = html.split("disabled").length - 1;
    // Two mode radios plus the visible URL input or Upload button.
    expect(disabledCount).toBeGreaterThanOrEqual(3);
  });
});
