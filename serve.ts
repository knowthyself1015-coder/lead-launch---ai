// Production server for the built Next.js site.
// Next.js standalone build outputs to .next/standalone/.
// This wrapper starts the server on port 3000 bound to 0.0.0.0.
//
// Run `bun run build` before starting. Restart with `bun run publish`.
//
// Starting a new instance supersedes the old one: it frees the port no matter
// which user owns the current server, so publish never collides with an already-
// running server. Every sandbox user has passwordless sudo, so the takeover
// works across user boundaries.

// Pinned, NOT read from the environment. The published preview URL
// (<label>.<PUBLIC_SITE_DOMAIN>) is reverse-proxied to 0.0.0.0:3000 inside the
// sandbox, so the default site MUST bind there.
const PORT = 3000;
const HOST = "0.0.0.0";

// Free PORT regardless of which user owns the current listener.
const freePort =
  `for _ in $(seq 1 25); do ` +
  `pids=$(lsof -t -iTCP:${String(PORT)} -sTCP:LISTEN 2>/dev/null || true); ` +
  `if [ -z "$pids" ]; then exit 0; fi; ` +
  `kill $pids 2>/dev/null || true; sleep 0.2; ` +
  `done`;

// Take over the port
for (let attempt = 1; ; attempt++) {
  await Bun.$`sudo sh -c ${freePort}`.quiet().nothrow();
  try {
    // In Next.js standalone mode, the server.js is at .next/standalone/server.js
    // We need to run it from within the standalone directory so relative paths work.
    // However, since it imports next, we can also just invoke it directly with bun.
    const standaloneDir = `${import.meta.dir}/.next/standalone`;
    const serverPath = `${standaloneDir}/server.js`;

    // Check if the standalone server exists
    const standaloneExists = await Bun.file(serverPath).exists();

    if (standaloneExists) {
      // Start Next.js standalone server as a child process
      const proc = Bun.spawn(["node", serverPath], {
        cwd: standaloneDir,
        env: {
          ...process.env,
          PORT: String(PORT),
          HOST: HOST,
          HOSTNAME: HOST,
        },
        stdio: ["ignore", "inherit", "inherit"],
      });

      // Keep the process alive
      proc.unref();

      console.log(`LeadLaunch AI serving on http://${HOST}:${String(PORT)}`);
    } else {
      // Fallback: run a basic server that shows a build-required message
      // This happens when the site hasn't been built yet
      Bun.serve({
        port: PORT,
        hostname: HOST,
        async fetch() {
          return new Response(
            "Site not built yet. Run `bun run publish` to build and serve.",
            { status: 503 }
          );
        },
      });
      console.log(
        `LeadLaunch AI (dev mode) on http://${HOST}:${String(PORT)}`
      );
    }
    break;
  } catch (err) {
    if (attempt >= 10) throw err;
    await Bun.sleep(200);
  }
}
