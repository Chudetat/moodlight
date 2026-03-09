import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["echarts", "zrender"],
};

export default nextConfig;
