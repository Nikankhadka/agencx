import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import { QueryProvider } from "@/components/QueryProvider";
import { Toaster } from "@/components/Toaster";
import { PUBLIC_CONFIG_GLOBAL, serverPublicConfig } from "@/lib/public-config";

// Plus Jakarta Sans (self-hosted by next/font) is exposed as the
// --font-jakarta CSS variable, which theme.css picks up for --font-sans and
// --font-display. First build fetches the font once over the network.
const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-jakarta",
  weight: ["400", "500", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Agencx",
  // PRD section 13: user-facing copy never says "AI", "agent" or "automated".
  // This description said both, which made the browser tab the one place the
  // product still sold its mechanism instead of what it does.
  description: "Answer your customers day and night, in your own words.",
};

/**
 * Rendered per request, not prerendered at build.
 *
 * The runtime public config below is only "runtime" if this layout actually
 * runs on a request. Statically prerendered, it executes during `next build`
 * inside the image build - which has no project env - and bakes
 * `{"supabaseUrl":"","supabaseAnonKey":""}` into the HTML forever. That is
 * exactly what the first deploy shipped. Nothing here is static anyway: every
 * surface reads tenant state from the backend.
 */
export const dynamic = "force-dynamic";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`h-full antialiased ${jakarta.variable}`}>
      <head>
        {/* Runtime public config: read on the server, where Vercel injects
            project env vars, because container builds get no --build-arg and
            so cannot inline NEXT_PUBLIC_*. Must run before any client
            component asks for the Supabase client. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `window.${PUBLIC_CONFIG_GLOBAL}=${JSON.stringify(serverPublicConfig())}`,
          }}
        />
      </head>
      <body className="min-h-full flex flex-col" suppressHydrationWarning>
        <AuthProvider><QueryProvider>{children}</QueryProvider></AuthProvider>
        <Toaster />
      </body>
    </html>
  );
}
