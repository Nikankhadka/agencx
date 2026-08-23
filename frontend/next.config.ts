import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // E-3: /dashboards no longer redirects. It is unlinked like every other
  // advanced screen (E-2) and serves when typed - the eval pass/fail view is
  // where the keep/pivot/stop signals live, and a redirect made it the one
  // hidden screen that had actually stopped existing.

  // B-4: the frontend deploys as a container (frontend/Dockerfile), so the
  // build has to emit a self-contained server rather than assume a host that
  // runs `next start` against an installed node_modules. `standalone` traces
  // exactly the files the server needs into .next/standalone; the Dockerfile
  // copies `public` and `.next/static` in beside it, which that server does not
  // gather itself.
  output: "standalone",
};

export default nextConfig;
