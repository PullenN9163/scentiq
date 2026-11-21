import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    // Catalog photos are small CDN thumbnails. Serving them directly saves a server
    // round trip and image-resizing CPU on every first view.
    unoptimized: true,
    remotePatterns: [
      { protocol: "https", hostname: "fimgs.net", pathname: "/mdimg/perfume/**" },
      { protocol: "https", hostname: "static.luckyscent.com", pathname: "/**" },
    ],
  },
};

export default nextConfig;
