/**
 * Static export. This site has no backend of its own: the only request it
 * makes at runtime is the waitlist POST, straight to the MetalArm API, so
 * there is nothing for a Node server to do and a CDN serves it faster.
 *
 * NEXT_PUBLIC_API_URL is baked in at build time; it defaults to the local
 * stack so `npm run dev` works with `docker compose up` and nothing else.
 */
const nextConfig = {
  output: 'export',
  images: { unoptimized: true },  // no image server in a static export
  trailingSlash: true,
};

export default nextConfig;
