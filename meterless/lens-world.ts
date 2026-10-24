import { WorldModel } from "./vendor/src/index.ts";
import { createHash } from "node:crypto";

export type SourceInput = {
  id: string;
  kind: "timesheet" | "receipt" | "activity" | "draft";
  title: string;
  text: string;
  observedAt: string;
  location: string;
};

export type FindingInput = {
  id: string;
  sourceIds: string[];
  status: "needs_review" | "needs_evidence" | "resolved";
  summary: string;
  calculation?: string;
  observedAt: string;
};

export type CorrectionInput = {
  id: string;
  findingId: string;
  actor: string;
  explanation: string;
  observedAt: string;
};

/** A thin Lens domain adapter around the unmodified Meterless World Model reference runtime. */
export class LensWorld {
  readonly world: WorldModel;

  constructor(directory: string, namespace = "lens-demo") {
    if (!/^[a-zA-Z0-9_-]+$/.test(namespace)) throw new Error("Unsafe namespace");
    this.world = new WorldModel({ storage: "local", directory, namespace });
  }

  private sourceEntityId(id: string): string { return `source:ingest:${id}`; }
  private findingEntityId(id: string): string { return `finding:lens:${id}`; }
  private correctionEntityId(id: string): string { return `correction:lens:${id}`; }

  async ingestSources(inputs: SourceInput[]) {
    for (const input of inputs) {
      if (!input.id || !input.location || !input.observedAt) throw new Error("Source ID, location, and observedAt are required");
    }
    return this.world.ingest(inputs.map(input => ({
      externalId: input.id,
      type: "source",
      title: input.title,
      text: input.text,
      at: input.observedAt,
      source: { kind: "file", at: input.observedAt, url: input.location, by: input.kind },
    })));
  }

  source(id: string) {
    return this.world.view("graph").entity(this.sourceEntityId(id));
  }

  async recordFinding(input: FindingInput) {
    if (!input.id || !input.sourceIds.length || !input.observedAt) throw new Error("Finding ID, sources, and observedAt are required");
    const sourceIds = [...new Set(input.sourceIds)].sort();
    const sourceVersions: Record<string, string> = {};
    for (const id of sourceIds) {
      const source = this.source(id);
      if (!source) throw new Error(`Unknown source ${id}`);
      // Save the exact evidence version reviewed. A later re-ingest changes this
      // fingerprint and therefore produces a new finding event on rerun.
      sourceVersions[id] = createHash("sha256")
        .update(JSON.stringify({ attrs: source.attrs, location: source.source.url }))
        .digest("hex");
    }
    const attrs = { status: input.status, summary: input.summary, calculation: input.calculation ?? null, sourceIds, sourceVersions };
    const prior = this.finding(input.id);
    if (prior && JSON.stringify(prior.attrs) === JSON.stringify(attrs)) return { entity: prior, changed: false };
    const entity = await this.world.upsertEntity({
      type: "finding", externalKey: { system: "lens", id: input.id }, attrs,
      source: { kind: "agent", at: input.observedAt, by: "lens-reconciliation" },
    });
    for (const sourceId of sourceIds) {
      await this.world.relate({
        from: entity.id, type: "supported-by", to: this.sourceEntityId(sourceId), context: this.sourceEntityId(sourceId),
        source: { kind: "agent", at: input.observedAt, by: "lens-reconciliation" },
      });
    }
    return { entity, changed: true };
  }

  finding(id: string) {
    return this.world.view("graph").entity(this.findingEntityId(id));
  }

  findingSources(id: string) {
    if (!this.finding(id)) return [];
    return this.world.view("graph").neighborsOf(this.findingEntityId(id), { via: "supported-by" });
  }

  async recordCorrection(input: CorrectionInput) {
    if (!input.id || !input.actor || !input.explanation.trim() || !input.observedAt) throw new Error("Correction ID, actor, explanation, and observedAt are required");
    if (!this.finding(input.findingId)) throw new Error(`Unknown finding ${input.findingId}`);
    const attrs = { findingId: input.findingId, actor: input.actor, explanation: input.explanation };
    const existing = this.correction(input.id);
    if (existing) {
      if (JSON.stringify(existing.attrs) !== JSON.stringify(attrs)) throw new Error(`Correction ID ${input.id} already exists with different content`);
      return { entity: existing, changed: false };
    }
    const entity = await this.world.upsertEntity({
      type: "correction", externalKey: { system: "lens", id: input.id }, attrs,
      source: { kind: "manual", at: input.observedAt, by: input.actor },
    });
    await this.world.relate({
      from: entity.id, type: "addresses", to: this.findingEntityId(input.findingId),
      source: { kind: "manual", at: input.observedAt, by: input.actor },
    });
    return { entity, changed: true };
  }

  correction(id: string) {
    return this.world.view("graph").entity(this.correctionEntityId(id));
  }

  findingCorrections(id: string) {
    if (!this.finding(id)) return [];
    return this.world.view("graph").incoming(this.findingEntityId(id), { via: "addresses" });
  }

  audit() { return this.world.audit(); }
  eventCount() { return this.world.events().length; }
}
