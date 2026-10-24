import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { LensWorld } from "./lens-world.ts";

const directory = mkdtempSync(join(tmpdir(), "lens-meterless-proof-"));
const first = new LensWorld(directory, "proof");
const at = "2026-10-23T09:00:00.000Z";
const sources = [
  { id: "time-17", kind: "timesheet" as const, title: "Four-hour entry", text: "Amina, 4 hours", observedAt: at, location: "timesheets.csv#row=2" },
  { id: "grant-A-claim", kind: "draft" as const, title: "Grant A claim", text: "4 hours charged", observedAt: at, location: "grant_a.csv#row=3" },
  { id: "grant-B-claim", kind: "draft" as const, title: "Grant B claim", text: "4 hours charged", observedAt: at, location: "grant_b.csv#row=3" },
];
const ingestFirst = await first.ingestSources(sources);
const eventsAfterFirst = first.eventCount();
const ingestAgain = await first.ingestSources(sources);
await first.recordFinding({
  id: "overlap-17", sourceIds: sources.map(source => source.id), status: "needs_review",
  summary: "Eight hours claimed against four recorded", calculation: "4 + 4 = 8 > 4 hours",
  observedAt: "2026-10-23T09:01:00.000Z",
});
await first.recordCorrection({
  id: "correction-1", findingId: "overlap-17", actor: "grant-manager",
  explanation: "Changed each grant to two hours; rerun required.", observedAt: "2026-10-23T09:02:00.000Z",
});
const reopened = new LensWorld(directory, "proof");
process.stdout.write(JSON.stringify({
  runtime: "Meterless World Model reference",
  persistedAt: join(directory, ".world", "proof.json"),
  firstProcessed: ingestFirst.processed,
  secondProcessed: ingestAgain.processed,
  secondSkippedUnchanged: ingestAgain.skippedUnchanged,
  idempotentEventCount: eventsAfterFirst,
  finding: reopened.finding("overlap-17")?.attrs,
  sourceLocations: reopened.findingSources("overlap-17").map(source => source.source.url).sort(),
  correction: reopened.findingCorrections("overlap-17")[0]?.attrs,
  auditEntries: reopened.audit().length,
}, null, 2) + "\n");
