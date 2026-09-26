import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "fimgs.net", pathname: "/mdimg/perfume/**" },
      { protocol: "https", hostname: "static.luckyscent.com", pathname: "/**" },
    ],
  },
};

export default nextConfig;
