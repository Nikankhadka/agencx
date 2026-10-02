"use client";

import { useEffect, useRef, useState } from "react";
import { MediaField, type MediaFieldState } from "./MediaField";

export interface OfferingMediaFieldProps {
  mediaUrl: string;
  mediaFile: File | null;
  mediaChanged: boolean;
  removeMedia: boolean;
  working: boolean;
  onPickFile: (file: File) => void;
  onUrlChange: (value: string) => void;
  onCancelPending: (restoreUrl: string, restoreChanged: boolean) => void;
  onRemoveSaved: () => void;
}

/** RF-5: one source at a time - the shared upload slot, or a URL. */
type MediaMode = "upload" | "url";

const MODE_ACTIVE =
  "rounded-chip border-chip border-accent-subtle bg-accent-subtle px-4 py-2 text-chip text-accent-active transition-colors duration-(--duration-fast)";
const MODE_INACTIVE =
  "rounded-chip border-chip border-hairline px-4 py-2 text-chip text-text-secondary transition-colors duration-(--duration-fast) hover:bg-accent-a07 hover:text-accent-active";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * The offering media picker. A segmented Upload | URL toggle renders one
 * source at a time: the shared MediaField slot, or a URL field. Picking a file
 * stages it locally (no upload until Save) and shows it in the field's preview
 * state with Edit (re-pick) and Cancel (drop the pending pick, local only).
 * Switching to URL with a pick pending drops that pick and restores the URL it
 * had replaced. Removing already-saved media stays on the parent's confirm
 * flow - Cancel never touches the backend, and the field's explicit Remove
 * routes straight through `onRemoveSaved`. Preview object URLs are revoked on
 * replace and on unmount.
 */
export function OfferingMediaField({
  mediaUrl,
  mediaFile,
  mediaChanged,
  removeMedia,
  working,
  onPickFile,
  onUrlChange,
  onCancelPending,
  onRemoveSaved,
}: OfferingMediaFieldProps) {
  // The URL text a file pick replaced, so Cancel can put it back. Owned here
  // so it dies with the modal - no stale restore after save or close.
  const stashedRef = useRef<{ url: string; changed: boolean } | null>(null);
  // The blob for the pending pick. Created in the pick handler, never in
  // render (so StrictMode cannot leak a discarded one), revoked on replace,
  // on cancel, on URL switch, and on unmount.
  const previewRef = useRef<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  // Which source the owner is editing. Lazy, so every open of the modal picks
  // the side that matches what is already saved: a saved URL reads back in its
  // own field, anything else starts on upload.
  const [mode, setMode] = useState<MediaMode>(() =>
    !mediaFile && mediaUrl.trim() ? "url" : "upload",
  );

  useEffect(() => {
    return () => {
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    };
  }, []);

  function setPreview(url: string | null) {
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = url;
    setPreviewUrl(url);
  }

  function handleFile(file: File) {
    if (!mediaFile && mediaUrl && stashedRef.current === null) {
      stashedRef.current = { url: mediaUrl, changed: mediaChanged };
    }
    setPreview(URL.createObjectURL(file));
    onPickFile(file);
  }

  function handleUrl(value: string) {
    // A newly typed URL supersedes whatever a pick had replaced.
    stashedRef.current = null;
    setPreview(null);
    onUrlChange(value);
  }

  function handleCancel() {
    const stashed = stashedRef.current;
    stashedRef.current = null;
    setPreview(null);
    onCancelPending(stashed?.url ?? "", stashed ? stashed.changed : false);
  }

  const hasPending = mediaFile !== null && !removeMedia;
  const hasUrl = mediaUrl.trim() !== "";
  const kind = mediaFile?.type.startsWith("video/") ? "video" : "image";
  const state: MediaFieldState = hasPending
    ? "preview"
    : hasUrl && !removeMedia
      ? "saved"
      : "empty";

  function selectMode(next: MediaMode) {
    if (next === mode) return;
    // A pending pick only makes sense on the upload side; leaving it for the
    // URL side drops it locally and restores whatever it had replaced.
    if (next === "url" && hasPending) handleCancel();
    setMode(next);
  }

  return (
    <div className="mt-3">
      <span className="block text-label font-medium uppercase text-ink-a40">
        Media <span className="normal-case">(optional)</span>
      </span>
      <div className="mt-2 flex gap-2" role="radiogroup" aria-label="Media source">
        <button
          type="button"
          role="radio"
          aria-checked={mode === "upload"}
          data-testid="offering-media-mode-upload"
          disabled={working}
          onClick={() => selectMode("upload")}
          className={mode === "upload" ? MODE_ACTIVE : MODE_INACTIVE}
        >
          Upload
        </button>
        <button
          type="button"
          role="radio"
          aria-checked={mode === "url"}
          data-testid="offering-media-mode-url"
          disabled={working}
          onClick={() => selectMode("url")}
          className={mode === "url" ? MODE_ACTIVE : MODE_INACTIVE}
        >
          URL
        </button>
      </div>

      {mode === "upload" ? (
        <div className="mt-3">
          <MediaField
            variant="offering"
            state={state}
            kind={kind}
            src={previewUrl}
            filename={hasPending && mediaFile ? mediaFile.name : null}
            detail={
              hasPending && mediaFile
                ? `${formatSize(mediaFile.size)} - Ready to save`
                : null
            }
            pickLabel="Upload media"
            disabled={working}
            accept="image/*,video/*"
            onFile={handleFile}
            onCancel={handleCancel}
            onRemove={onRemoveSaved}
            removeLabel="Remove current media"
            testIds={{
              field: "offering-media-upload",
              input: "offering-media-input",
              preview: "offering-media-preview",
              filename: "offering-media-filename",
              edit: "offering-media-edit",
              cancel: "offering-media-cancel",
              remove: "offering-media-remove",
            }}
          />
          {removeMedia ? (
            <p className="mt-2 text-meta text-ink-a40">
              Current media will be removed when you save.
            </p>
          ) : null}
        </div>
      ) : (
        <div className="mt-3">
          <input
            data-testid="offering-media-url"
            type="url"
            value={mediaUrl}
            disabled={working}
            onChange={(event) => handleUrl(event.target.value)}
            placeholder="Paste an image or video link"
            aria-label="Image or video URL"
            className="w-full rounded-field border border-border bg-surface px-3 py-2 text-field text-text outline-none placeholder:text-ink-a40 focus:border-text disabled:opacity-50"
          />
          {hasUrl && !removeMedia ? (
            <button
              type="button"
              disabled={working}
              data-testid="offering-media-remove"
              onClick={onRemoveSaved}
              className="mt-2 block text-action font-medium text-danger transition-colors duration-(--duration-fast) hover:underline active:opacity-60 disabled:opacity-50"
            >
              Remove current media
            </button>
          ) : null}
          {removeMedia ? (
            <p className="mt-2 text-meta text-ink-a40">
              Current media will be removed when you save.
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
