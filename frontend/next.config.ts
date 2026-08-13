import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: "/dashboards",
        destination: "/onboarding",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
