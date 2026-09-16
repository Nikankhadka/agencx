"use client";

import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";

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
 * The offering media picker. A secondary Upload button (with the shared hover
 * fill) opens a hidden file input; a picked file shows a preview chip with
 * Edit (re-pick) and Cancel (drop the pending pick, local only). Removing
 * already-saved media stays on the confirm flow - Cancel never touches the
 * backend. Preview object URLs are revoked on replace and on unmount.
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
  const fileRef = useRef<HTMLInputElement>(null);
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

  function handlePick(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
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
    if (fileRef.current) fileRef.current.value = "";
    setPreview(null);
    onCancelPending(stashed?.url ?? "", stashed ? stashed.changed : false);
  }

  const hasPending = mediaFile !== null && !removeMedia;
  const hasUrl = mediaUrl.trim() !== "";
  const isVideo = mediaFile?.type.startsWith("video/") ?? false;

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
        {hasPending && mediaFile ? (
          <div
            role="status"
            data-testid="offering-media-preview"
            className="mt-2 flex items-center gap-3 rounded-field border border-border bg-surface-sunken px-3 py-2"
          >
            {isVideo ? (
              <video
                src={previewUrl ?? undefined}
                muted
                playsInline
                preload="metadata"
                aria-hidden="true"
                tabIndex={-1}
                className="h-12 w-12 shrink-0 rounded-md object-cover"
              />
            ) : previewUrl ? (
              /* eslint-disable-next-line @next/next/no-img-element --
                 a blob object URL for the just-picked file, not an asset
                 next/image could fetch or optimise. */
              <img
                src={previewUrl}
                alt=""
                className="h-12 w-12 shrink-0 rounded-md object-cover"
              />
            ) : (
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md bg-surface-container text-ink-a40">
                <Icon name="attach_file" size={20} />
              </span>
            )}
            <span className="min-w-0 flex-1">
              <span
                data-testid="offering-media-filename"
                aria-live="polite"
                className="block truncate text-body-sm font-medium text-text"
              >
                {mediaFile.name}
              </span>
              <span className="mt-1 block text-meta text-ink-a40">
                {formatSize(mediaFile.size)} - Ready to save
              </span>
            </span>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={working}
              onClick={() => fileRef.current?.click()}
              data-testid="offering-media-edit"
              aria-label="Change selected media"
            >
              <Icon name="edit" size={14} />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={working}
              onClick={handleCancel}
              data-testid="offering-media-cancel"
              aria-label="Cancel selected media"
            >
              <Icon name="cancel" size={14} />
            </Button>
          </div>
        ) : (
          <Button
            type="button"
            variant="secondary"
            disabled={working}
            onClick={() => fileRef.current?.click()}
            data-testid="offering-media-upload"
            aria-label="Upload media"
            className="mt-2"
          >
            <Icon name="photo_camera" size={16} />
          </Button>
        )}
        {removeMedia ? (
          <p className="mt-2 text-meta text-ink-a40">
            Current media will be removed when you save.
          </p>
        ) : hasUrl && !hasPending ? (
          <button
            type="button"
            onClick={onRemoveSaved}
            disabled={working}
            data-testid="offering-media-remove"
            className="mt-2 block text-action font-medium text-danger transition-colors duration-(--duration-fast) hover:underline active:opacity-60 disabled:opacity-50"
          >
            Remove current media
          </button>
        ) : null}
      </div>
      <input
        ref={fileRef}
        type="file"
        accept="image/*,video/*"
        tabIndex={-1}
        aria-label="Upload offering photo or video"
        data-testid="offering-media-input"
        onChange={handlePick}
        className="hidden"
      />
    </div>
  );
}
