import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import { QueryProvider } from "@/components/QueryProvider";
import { Toaster } from "@/components/Toaster";

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
      <body className="min-h-full flex flex-col" suppressHydrationWarning>
        <AuthProvider><QueryProvider>{children}</QueryProvider></AuthProvider>
        <Toaster />
      </body>
    </html>
  );
}
