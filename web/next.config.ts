import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: "standalone",
  // Next standalone ищет трассировку относительно этого корня —
  // явно указываем web/, чтобы server.js корректно резолвил файлы.
  outputFileTracingRoot: path.join(__dirname),
  experimental: {
    serverActions: {
      allowedOrigins: [
        "localhost:3000",
        ...(process.env.NEXT_PUBLIC_ALLOWED_ORIGIN
          ? [process.env.NEXT_PUBLIC_ALLOWED_ORIGIN]
          : []),
      ],
    },
  },
};

export default nextConfig;
