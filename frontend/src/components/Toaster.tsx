"use client";

import { useEffect } from "react";
import { Toaster as HotToaster, toast, useToasterStore } from "react-hot-toast";

const TOAST_LIMIT = 3;

export function Toaster() {
  const { toasts } = useToasterStore();

  useEffect(() => {
    toasts
      .filter((t) => t.visible)
      .filter((_, i) => i >= TOAST_LIMIT)
      .forEach((t) => toast.dismiss(t.id));
  }, [toasts]);

  return (
    <HotToaster
      position="top-center"
      toastOptions={{
        duration: 4000,
        style: {
          background: "var(--color-surface)",
          color: "var(--color-text)",
          boxShadow: "var(--shadow-3)",
          borderRadius: "var(--radius-md)",
          fontSize: "var(--text-body-sm-size)",
        },
        success: {
          iconTheme: { primary: "var(--color-success)", secondary: "var(--color-success-subtle)" },
        },
        error: {
          iconTheme: { primary: "var(--color-danger)", secondary: "var(--color-danger-subtle)" },
        },
      }}
    />
  );
}
