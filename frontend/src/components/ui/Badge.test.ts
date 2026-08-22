import { describe, expect, it } from "vitest";
import { toneForStatus } from "./Badge";

/**
 * B-3 US-2. The map is a product decision, not an implementation detail: an
 * owner scans these dots and pills to decide what needs them, so a status
 * reading green when it means "still waiting" is a real failure.
 */
describe("toneForStatus", () => {
  it("greens the statuses that mean it went well or it is done", () => {
    for (const status of [
      "approved",
      "paid",
      "ready",
      "ready_for_pickup",
      "resolved",
      "closed",
      "active",
      "delivered",
      "completed",
      "confirmed",
    ]) {
      expect(toneForStatus(status), status).toBe("success");
    }
  });

  it("reds the statuses that mean it did not", () => {
    for (const status of [
      "cancelled",
      "declined",
      "rejected",
      "refunded",
      "failed",
      "suspended",
      "error",
    ]) {
      expect(toneForStatus(status), status).toBe("danger");
    }
  });

  it("ambers the statuses that are still in flight", () => {
    for (const status of [
      "pending",
      "overdue",
      "outstanding",
      "in_progress",
      "processing",
      "provisioning",
      "claimed",
      "escalated",
      "shipped",
    ]) {
      expect(toneForStatus(status), status).toBe("warning");
    }
  });

  it("does not call shipped delivered", () => {
    // The pair that is easiest to get wrong, and the one a waiting customer
    // would notice: on its way is not arrived.
    expect(toneForStatus("shipped")).toBe("warning");
    expect(toneForStatus("delivered")).toBe("success");
  });

  it("leaves statuses with no good/bad charge alone", () => {
    expect(toneForStatus("open")).toBe("info");
    expect(toneForStatus("sent")).toBe("info");
    expect(toneForStatus("draft")).toBe("neutral");
    expect(toneForStatus("expired")).toBe("neutral");
  });

  it("reads one concept however it is spelled", () => {
    // The schema writes in_progress, the design doc writes in-progress, and a
    // tenant may well send "In Progress".
    for (const spelling of ["in_progress", "in-progress", "In Progress", " IN_PROGRESS "]) {
      expect(toneForStatus(spelling), spelling).toBe("warning");
    }
  });

  it("falls back to neutral for a status it has never seen", () => {
    // Tenants define their own; a made-up colour would be worse than no colour.
    expect(toneForStatus("awaiting_courier")).toBe("neutral");
    expect(toneForStatus("")).toBe("neutral");
  });

  it("covers every status the schema can store", () => {
    // Migrations 0003-0020: if a CHECK constraint gains a value and this map
    // does not, the new status renders grey and nobody notices for a release.
    const schemaStatuses = [
      "pending", "processing", "ready", "failed", "draft", // documents
      "open", "human", "escalated", "closed", // conversations
      "provisioning", "active", "suspended", // tenants
      "sent", "expired", // quotes
      "claimed", "resolved", // escalations
    ];
    const unmapped = schemaStatuses.filter(
      (s) => toneForStatus(s) === "neutral" && !["draft", "expired"].includes(s)
    );
    // `human` is deliberately absent: C-6's takeover is shown as a thread
    // stamp and a filter, never as a status pill.
    expect(unmapped).toEqual(["human"]);
  });
});
