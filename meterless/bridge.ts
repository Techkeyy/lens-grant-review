import { LensWorld } from "./lens-world.ts";

// One JSON request per process. All records live in Meterless's local event store.
// Usage: node --import tsx bridge.ts <directory> <namespace> <action> < request.json
const [directory, namespace, action] = process.argv.slice(2);
if (!directory || !namespace || !action) {
  console.error("Usage: bridge.ts <directory> <namespace> <action> < request.json");
  process.exit(2);
}

const chunks: Buffer[] = [];
for await (const chunk of process.stdin) chunks.push(Buffer.from(chunk));
const raw = Buffer.concat(chunks).toString("utf8").trim();
const input = raw ? JSON.parse(raw) : {};
const lens = new LensWorld(directory, namespace);

try {
  let result: unknown;
  switch (action) {
    case "ingest": result = await lens.ingestSources(input.sources); break;
    case "finding": result = await lens.recordFinding(input); break;
    case "correction": result = await lens.recordCorrection(input); break;
    case "read": result = {
      finding: lens.finding(input.findingId) ?? null,
      sources: lens.findingSources(input.findingId),
      corrections: lens.findingCorrections(input.findingId),
      audit: lens.audit(),
      eventCount: lens.eventCount(),
    }; break;
    case "audit": result = { audit: lens.audit(), eventCount: lens.eventCount() }; break;
    default: throw new Error(`Unknown action ${action}`);
  }
  process.stdout.write(JSON.stringify({ ok: true, result }) + "\n");
} catch (error) {
  process.stdout.write(JSON.stringify({ ok: false, error: error instanceof Error ? error.message : String(error) }) + "\n");
  process.exitCode = 1;
}
