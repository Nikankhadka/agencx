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

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * The offering media picker. A URL field and the shared MediaField slot sit
 * side by side: picking a file stages it locally (no upload until Save) and
 * shows it in the field's preview state with Edit (re-pick) and Cancel (drop
 * the pending pick, local only). Removing already-saved media stays on the
 * parent's confirm flow - Cancel never touches the backend, and the field's
 * explicit Remove routes straight through `onRemoveSaved`. Preview object URLs
 * are revoked on replace and on unmount.
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

  return (
    <div className="mt-3">
      <label className="block text-label font-medium uppercase text-ink-a40">
        Image or video URL <span className="normal-case">(optional)</span>
        <input
          data-testid="offering-media-url"
          type="url"
          value={mediaUrl}
          disabled={working || hasPending}
          onChange={(event) => handleUrl(event.target.value)}
          className="mt-2 w-full rounded-field border border-border bg-surface px-3 py-2 text-field text-text outline-none focus:border-text disabled:opacity-50"
        />
      </label>
      {hasPending ? (
        <p className="mt-2 text-meta text-ink-a40">
          File selected - remove it to use a URL instead.
        </p>
      ) : null}
      <div className="mt-3">
        <span
          id="offering-media-label"
          className="block text-label font-medium uppercase text-ink-a40"
        >
          Upload media <span className="normal-case">(optional)</span>
        </span>
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
    </div>
  );
}
