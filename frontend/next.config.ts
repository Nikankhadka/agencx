import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // E-3: /dashboards no longer redirects. It is unlinked like every other
  // advanced screen (E-2) and serves when typed - the eval pass/fail view is
  // where the keep/pivot/stop signals live, and a redirect made it the one
  // hidden screen that had actually stopped existing.

};

export default nextConfig;
