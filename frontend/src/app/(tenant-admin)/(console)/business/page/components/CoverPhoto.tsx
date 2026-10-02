"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "react-hot-toast";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { apiFetch, apiFetchStream } from "@/lib/api";
import { MediaField, type MediaFieldState } from "../../components/MediaField";

/**
 * The cover photo well, ported from `.bk-photo-wrap` in
 * agencx-prototype-v6.html: a 200px band that is a tinted invitation while
 * empty and the photo itself once set, with the "Edit photo" pill in its
 * bottom-right corner either way.
 *
 * RF-5 gives it the shared MediaField vocabulary - empty, uploading, preview,
 * saved - an explicit Remove control (confirmed through the app's dialog, then
 * DELETE /api/business/cover), and a local preview while the PUT is in flight.
 *
 * The file is resized here before it is sent. A phone camera produces 4MB+ of
 * pixels for a band that is 200px tall, and the bytes land in a Postgres row -
 * so the client does the one job it is uniquely able to do cheaply, and the
 * server's 2MB cap becomes a backstop rather than a wall the owner hits.
 */

const MAX_EDGE_PX = 1600;
const JPEG_QUALITY = 0.82;

export async function downscale(file: File): Promise<Blob> {
  // createImageBitmap decodes off the main thread; a browser without it (or a
  // file it cannot decode) falls through to sending the original, which the
  // server will accept or refuse on its own terms.
  if (typeof createImageBitmap !== "function") return file;
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    return file;
  }
  const scale = Math.min(
    1,
    MAX_EDGE_PX / Math.max(bitmap.width, bitmap.height),
  );
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) return file;
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY),
  );
  return blob ?? file;
}

export interface CoverPhotoProps {
  hasCover: boolean;
  onChanged: () => void;
}

export function CoverPhoto({ hasCover, onChanged }: CoverPhotoProps) {
  const [busy, setBusy] = useState(false);
  const [src, setSrc] = useState<string | null>(null);
  // Bumped on every save so the photo is refetched: the URL never changes, and
  // the browser would otherwise keep showing the one that was just replaced.
  const [version, setVersion] = useState(0);
  // The just-picked file's local preview, shown while the PUT is in flight so
  // replacement is visible before the server answers. Revoked on replace, on
  // failure, once the refetched canonical image lands, and on unmount; a
  // separate ref because the setter path is async.
  const [pendingSrc, setPendingSrc] = useState<string | null>(null);
  const pendingRef = useRef<string | null>(null);
  // True while a PUT is in flight. The refetch effect reads it so a refetch
  // for an older upload cannot revoke the preview of a newer pick.
  const uploadingRef = useRef(false);
  const { confirm, dialog } = useConfirm();

  /**
   * The cover is served behind the owner's bearer token, which an <img src>
   * cannot send - so the bytes are fetched and handed to the tag as an object
   * URL. Revoked on replacement and on unmount; leaving them is a real leak on
   * a page the owner edits repeatedly.
   */
  useEffect(() => {
    // No synchronous reset here: `hasCover` gates the render below, so a stale
    // object URL is never shown, and clearing it eagerly would be a cascading
    // setState inside the effect.
    if (!hasCover) return;
    let url: string | null = null;
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiFetchStream("/api/business/cover");
        const blob = await res.blob();
        if (cancelled) return;
        url = URL.createObjectURL(blob);
        setSrc(url);
        // The refetched canonical image has landed, so release the local
        // preview that was shadowing it. Skip it when a newer pick is already
        // uploading - that preview must survive until its own refetch.
        if (!uploadingRef.current && pendingRef.current) {
          URL.revokeObjectURL(pendingRef.current);
          pendingRef.current = null;
          setPendingSrc(null);
        }
      } catch {
        if (!cancelled) setSrc(null);
      }
    })();
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [hasCover, version]);

  useEffect(() => {
    return () => {
      if (pendingRef.current) URL.revokeObjectURL(pendingRef.current);
    };
  }, []);

  function setPending(url: string | null) {
    if (pendingRef.current) URL.revokeObjectURL(pendingRef.current);
    pendingRef.current = url;
    setPendingSrc(url);
  }

  const shown = pendingSrc ?? src;
  const state: MediaFieldState = busy
    ? "uploading"
    : shown
      ? "saved"
      : hasCover
        ? "uploading"
        : "empty";

  async function upload(file: File) {
    setBusy(true);
    uploadingRef.current = true;
    setPending(URL.createObjectURL(file));
    try {
      const body = new FormData();
      const resized = await downscale(file);
      body.append("file", resized, file.name);
      await apiFetch("/api/business/cover", { method: "PUT", body });
      setVersion((n) => n + 1);
      onChanged();
      toast.success("Cover photo updated");
    } catch {
      // Drop the preview so the last saved cover (still in `src`) shows again -
      // a failed upload must not leave the band half-replaced.
      setPending(null);
      toast.error("That image could not be saved. Try a JPEG or PNG under 2MB.");
    } finally {
      uploadingRef.current = false;
      setBusy(false);
    }
  }

  function remove() {
    void confirm({
      title: "Remove cover photo?",
      description: "Your business page falls back to the plain cover.",
      confirmLabel: "Remove",
      tone: "danger",
      onConfirm: async () => {
        setBusy(true);
        try {
          await apiFetch("/api/business/cover", { method: "DELETE" });
          setPending(null);
          setSrc(null);
          setVersion((n) => n + 1);
          onChanged();
          toast.success("Cover photo removed");
        } catch {
          toast.error("That cover photo could not be removed.");
        } finally {
          setBusy(false);
        }
      },
    });
  }

  return (
    <>
      <MediaField
        variant="cover"
        state={state}
        src={shown}
        hint="Tap to add a cover photo"
        busyHint={pendingSrc ? "Adding…" : "Loading…"}
        pickLabel={hasCover ? "Change cover photo" : "Add a cover photo"}
        disabled={busy}
        accept="image/jpeg,image/png,image/webp"
        onFile={(file) => void upload(file)}
        onRemove={hasCover ? remove : undefined}
        removeLabel="Remove"
        testIds={{
          field: "booking-cover",
          input: "booking-cover-input",
          remove: "booking-cover-remove",
        }}
      />
      {dialog}
    </>
  );
}
