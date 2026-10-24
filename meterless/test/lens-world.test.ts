import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { LensWorld } from "../lens-world.ts";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const AT = "2026-10-23T09:00:00.000Z";
const sources = [
  { id: "time-17", kind: "timesheet" as const, title: "Amina's four hours", text: "Amina 4 hours reading prep", observedAt: AT, location: "timesheets.csv#row=2" },
  { id: "draft-A-7", kind: "draft" as const, title: "Reading Futures claim", text: "4 hours to time-17", observedAt: AT, location: "reading_futures_draft.csv#row=7" },
  { id: "draft-B-4", kind: "draft" as const, title: "Community Learning claim", text: "4 hours to time-17", observedAt: AT, location: "community_learning_draft.csv#row=4" },
];

function callBridge(directory: string, namespace: string, action: string, input: unknown) {
  const child = spawnSync(process.execPath, ["--experimental-transform-types", join(ROOT, "bridge.ts"), directory, namespace, action], {
    cwd: ROOT, input: JSON.stringify(input), encoding: "utf8",
  });
  assert.equal(child.status, 0, child.stderr || child.stdout);
  return JSON.parse(child.stdout).result;
}

test("source ingest is idempotent and a changed source is not silently ignored", async () => {
  const directory = mkdtempSync(join(tmpdir(), "lens-meterless-"));
  const lens = new LensWorld(directory, "ingest-test");
  const first = await lens.ingestSources(sources);
  assert.equal(first.processed, 3);
  const eventCount = lens.eventCount();
  const second = await lens.ingestSources(sources);
  assert.equal(second.processed, 0);
  assert.equal(second.skippedUnchanged, 3);
  assert.equal(lens.eventCount(), eventCount);
  const third = await lens.ingestSources([{ ...sources[0], text: "Amina 5 hours reading prep" }]);
  assert.equal(third.changed, true);
  assert.equal(lens.source("time-17")?.attrs.text, "Amina 5 hours reading prep");
});

test("finding, linked source provenance, and human correction survive a fresh process", async () => {
  const directory = mkdtempSync(join(tmpdir(), "lens-meterless-"));
  const lens = new LensWorld(directory, "restart-test");
  await lens.ingestSources(sources);
  const finding = {
    id: "overlap-17", sourceIds: sources.map(source => source.id),
    status: "needs_review" as const, summary: "Eight hours claimed against four recorded",
    calculation: "4 + 4 = 8 > 4 hours", observedAt: "2026-10-23T09:01:00.000Z",
  };
  const first = await lens.recordFinding(finding);
  assert.equal(first.changed, true);
  assert.equal((await lens.recordFinding(finding)).changed, false);
  assert.equal(lens.findingSources("overlap-17").length, 3);
  assert.equal(lens.source("time-17")?.source.url, "timesheets.csv#row=2");
  const correction = {
    id: "review-1", findingId: "overlap-17", actor: "grant-manager",
    explanation: "Changed each grant allocation to two hours; recheck pending.",
    observedAt: "2026-10-23T09:02:00.000Z",
  };
  await lens.recordCorrection(correction);
  assert.equal((await lens.recordCorrection(correction)).changed, false);
  await assert.rejects(() => lens.recordCorrection({ ...correction, explanation: "different" }), /already exists/);

  const child = spawnSync(process.execPath, ["--experimental-transform-types", join(ROOT, "bridge.ts"), directory, "restart-test", "read"], {
    cwd: ROOT, input: JSON.stringify({ findingId: "overlap-17" }), encoding: "utf8",
  });
  assert.equal(child.status, 0, child.stderr || child.stdout);
  const response = JSON.parse(child.stdout);
  assert.equal(response.ok, true);
  assert.equal(response.result.finding.attrs.calculation, "4 + 4 = 8 > 4 hours");
  assert.equal(response.result.sources.length, 3);
  assert.equal(response.result.corrections[0].attrs.actor, "grant-manager");
  assert.ok(response.result.audit.some((item: { kind: string }) => item.kind === "upsertEntity"));

  const beforeVersion = response.result.finding.attrs.sourceVersions["time-17"];
  const reopened = new LensWorld(directory, "restart-test");
  await reopened.ingestSources([{ ...sources[0], text: "Amina 5 hours reading prep" }]);
  assert.equal((await reopened.recordFinding(finding)).changed, true);
  assert.notEqual(reopened.finding("overlap-17")?.attrs.sourceVersions?.["time-17"], beforeVersion);
});

test("a finding cannot cite a source absent from the canonical store", async () => {
  const lens = new LensWorld(mkdtempSync(join(tmpdir(), "lens-meterless-")), "missing-test");
  await assert.rejects(() => lens.recordFinding({
    id: "f1", sourceIds: ["invented"], status: "needs_evidence", summary: "Missing",
    observedAt: AT,
  }), /Unknown source invented/);
});

test("the JSON bridge writes and reads the case across independent processes", () => {
  const directory = mkdtempSync(join(tmpdir(), "lens-meterless-"));
  const namespace = "bridge-test";
  assert.equal(callBridge(directory, namespace, "ingest", { sources }).processed, 3);
  assert.equal(callBridge(directory, namespace, "ingest", { sources }).processed, 0);
  assert.equal(callBridge(directory, namespace, "finding", {
    id: "f1", sourceIds: ["time-17", "draft-A-7"], status: "needs_review",
    summary: "Review hours", observedAt: AT,
  }).changed, true);
  assert.equal(callBridge(directory, namespace, "correction", {
    id: "c1", findingId: "f1", actor: "manager", explanation: "Checking timesheet",
    observedAt: AT,
  }).changed, true);
  const read = callBridge(directory, namespace, "read", { findingId: "f1" });
  assert.equal(read.sources.length, 2);
  assert.equal(read.corrections[0].attrs.explanation, "Checking timesheet");
  assert.ok(read.eventCount > 0);
});
