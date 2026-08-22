"use client";

import { useMemo } from "react";
import qrcode from "qrcode-generator";

/**
 * The share link as a QR, drawn as one inline SVG path.
 *
 * Encoding is `qrcode-generator` (MIT, no dependencies of its own): QR is a
 * spec with Reed-Solomon error correction and mask selection, and a subtly
 * wrong implementation produces codes that scan on one phone and fail on
 * another. That is not a wheel worth carving.
 *
 * The rendering is ours, though - the library's own `createSvgTag` emits
 * markup with hardcoded colours, which `check:tokens` forbids and which could
 * not follow a theme. Building the path from `isDark()` lets the code inherit
 * `currentColor`, so it is legible in dark mode without a second asset.
 *
 * Level M (15% recovery) is the usual default: enough to survive a scuffed
 * flyer, not so dense that scanning gets fussy.
 */
export function QrCode({ value, size = 132 }: { value: string; size?: number }) {
  const { path, count } = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(value);
    qr.make();
    const modules = qr.getModuleCount();

    // One path of 1x1 squares in module space; the viewBox does the scaling, so
    // the code stays crisp at any size and carries no rounding error.
    let d = "";
    for (let row = 0; row < modules; row++) {
      for (let col = 0; col < modules; col++) {
        if (qr.isDark(row, col)) d += `M${col} ${row}h1v1h-1z`;
      }
    }
    return { path: d, count: modules };
  }, [value]);

  return (
    <svg
      data-testid="booking-qr"
      role="img"
      aria-label={`QR code for ${value}`}
      width={size}
      height={size}
      viewBox={`0 0 ${count} ${count}`}
      shapeRendering="crispEdges"
      className="text-text"
    >
      <path d={path} fill="currentColor" />
    </svg>
  );
}
