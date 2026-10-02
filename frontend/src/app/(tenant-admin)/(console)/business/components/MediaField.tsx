"use client";

import { useRef, type ChangeEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";

/**
 * The shared media vocabulary for RF-5. Every place the owner attaches a
 * photo to their business - the cover band and an offering - renders this one
 * component, so the same states and the same explicit remove affordance show
 * up in both: empty, uploading, preview, saved.
 *
 * It is presentational and controlled: the wrapper owns the file, the API
 * call, and the saved URL. MediaField owns the hidden file input, the media
 * element, and the remove trigger - the three things the two call sites would
 * otherwise each re-implement.
 *
 * `variant` is the one layout switch. "cover" is the prototype's 200px
 * `.bk-photo-wrap` band; "offering" is the compact slot chip inside the
 * offering sheet. Two variants is a layout choice, not a mode matrix - the
 * state vocabulary, preview, and removal below are shared.
 */
export type MediaFieldState = "empty" | "uploading" | "preview" | "saved";

export interface MediaFieldTestIds {
  /** The slot control. */
  field: string;
  /** The hidden file input. */
  input: string;
  /** The pending-chip wrapper (offering). */
  preview?: string;
  /** The pending file's name (offering). */
  filename?: string;
  /** The re-pick control (offering). */
  edit?: string;
  /** The drop-pending control (offering). */
  cancel?: string;
  /** The explicit remove control. */
  remove?: string;
}

export interface MediaFieldProps {
  variant: "cover" | "offering";
  state: MediaFieldState;
  /** Blob URL while uploading/previewing, or the served URL when saved. */
  src?: string | null;
  /** Video previews render a <video>; everything else renders an <img>. */
  kind?: "image" | "video";
  /** Empty-state invitation (cover band). */
  hint?: string;
  /** In-flight copy for the cover band. */
  busyHint?: string;
  /** Accessible name for the pick control and hidden input. */
  pickLabel: string;
  /** Pending file name (offering chip). */
  filename?: string | null;
  /** Pending file detail line (offering chip). */
  detail?: string | null;
  disabled?: boolean;
  accept: string;
  onFile: (file: File) => void;
  /** Drop a pending pick (offering). */
  onCancel?: () => void;
  /**
   * Explicit removal, routed by the wrapper through its confirm flow. It
   * renders per variant: the cover shows it in any non-empty state, so a
   * cover that is still loading can still be removed, while the offering
   * shows it only once media is saved - never while a pending pick would
   * replace that media on save.
   */
  onRemove?: () => void;
  removeLabel?: string;
  testIds: MediaFieldTestIds;
}

export function MediaField({
  variant,
  state,
  src,
  kind = "image",
  hint = "",
  busyHint,
  pickLabel,
  filename,
  detail,
  disabled = false,
  accept,
  onFile,
  onCancel,
  onRemove,
  removeLabel = "Remove",
  testIds,
}: MediaFieldProps) {
  const fileRef = useRef<HTMLInputElement>(null);

  function openPicker() {
    if (!disabled) fileRef.current?.click();
  }

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) onFile(file);
  }

  const hasMedia = Boolean(src) && state !== "empty";
  // Removal is offered whenever there is saved media to remove. `empty` has
  // nothing to remove, and the offering hides it while a pending pick is in
  // flight (that pick would replace the saved media on save). The cover shows
  // it for any non-empty state so a cover that is still loading can still be
  // removed once it lands.
  const showRemove =
    onRemove !== undefined &&
    (variant === "cover" ? state !== "empty" : state === "saved");

  const input = (
    <input
      ref={fileRef}
      type="file"
      accept={accept}
      tabIndex={-1}
      aria-label={pickLabel}
      data-testid={testIds.input}
      onChange={handleFile}
      className="hidden"
    />
  );

  if (variant === "cover") {
    return (
      <div className="relative">
        <button
          type="button"
          onClick={openPicker}
          disabled={disabled}
          aria-label={pickLabel}
          data-testid={testIds.field}
          className="flex h-[200px] w-full flex-col items-center justify-center gap-3 overflow-hidden bg-accent-a09 transition-[filter] duration-(--duration-fast) hover:brightness-95 active:brightness-90"
        >
          {hasMedia ? (
            /* eslint-disable-next-line @next/next/no-img-element --
               an object URL for bytes from our own authed API, not an asset
               next/image could fetch or optimise. */
            <img src={src ?? undefined} alt="" className="h-full w-full object-cover" />
          ) : (
            <>
              <span className="text-accent-a35">
                <Icon name="photo_camera" size={36} />
              </span>
              <span className="text-body-sm text-accent-a50">
                {state === "uploading" ? (busyHint ?? "Adding…") : hint}
              </span>
            </>
          )}
        </button>

        {state !== "empty" ? (
          <button
            type="button"
            onClick={openPicker}
            disabled={disabled}
            className="absolute bottom-3 right-3 flex items-center gap-2 rounded-chip bg-scrim px-3 py-2 text-badge font-medium text-text-inverse transition-[filter] duration-(--duration-fast) hover:brightness-110 active:brightness-95"
          >
            <Icon name="edit" size={11} />
            {disabled ? "Saving…" : "Edit photo"}
          </button>
        ) : null}

        {showRemove ? (
          <button
            type="button"
            onClick={onRemove}
            disabled={disabled}
            aria-label={removeLabel}
            data-testid={testIds.remove}
            className="absolute bottom-3 left-3 flex items-center gap-2 rounded-chip bg-scrim px-3 py-2 text-badge font-medium text-text-inverse transition-[filter] duration-(--duration-fast) hover:brightness-110 active:brightness-95 disabled:opacity-50"
          >
            <Icon name="delete" size={12} />
            {removeLabel}
          </button>
        ) : null}

        {input}
      </div>
    );
  }

  return (
    <div>
      {state === "preview" && filename ? (
        <div
          role="status"
          data-testid={testIds.preview}
          className="mt-2 flex items-center gap-3 rounded-field border border-border bg-surface-sunken px-3 py-2"
        >
          {kind === "video" ? (
            <video
              src={src ?? undefined}
              muted
              playsInline
              preload="metadata"
              aria-hidden="true"
              tabIndex={-1}
              className="h-12 w-12 shrink-0 rounded-md object-cover"
            />
          ) : src ? (
            /* eslint-disable-next-line @next/next/no-img-element --
               a blob object URL for the just-picked file, not an asset
               next/image could fetch or optimise. */
            <img
              src={src}
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
              data-testid={testIds.filename}
              aria-live="polite"
              className="block truncate text-body-sm font-medium text-text"
            >
              {filename}
            </span>
            {detail ? (
              <span className="mt-1 block text-meta text-ink-a40">{detail}</span>
            ) : null}
          </span>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={disabled}
            onClick={openPicker}
            data-testid={testIds.edit}
            aria-label="Change selected media"
          >
            <Icon name="edit" size={14} />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={disabled}
            onClick={onCancel}
            data-testid={testIds.cancel}
            aria-label="Cancel selected media"
          >
            <Icon name="cancel" size={14} />
          </Button>
        </div>
      ) : (
        <Button
          type="button"
          variant="secondary"
          disabled={disabled}
          onClick={openPicker}
          data-testid={testIds.field}
          aria-label={pickLabel}
          className="mt-2"
        >
          <Icon name="photo_camera" size={16} />
        </Button>
      )}

      {showRemove ? (
        <button
          type="button"
          onClick={onRemove}
          disabled={disabled}
          data-testid={testIds.remove}
          className="mt-2 block text-action font-medium text-danger transition-colors duration-(--duration-fast) hover:underline active:opacity-60 disabled:opacity-50"
        >
          {removeLabel}
        </button>
      ) : null}

      {input}
    </div>
  );
}
