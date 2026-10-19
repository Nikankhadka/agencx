import { describe, expect, it } from "vitest";
import {
  clearQueue,
  coalesce,
  enqueue,
  hasQueued,
  queuedCount,
} from "./chat-queue";

describe("enqueue", () => {
  it("appends in arrival order and trims each question", () => {
    const first = enqueue([], "  Do you fix screens?  ");
    const second = enqueue(first, "How much?");
    expect(second).toEqual(["Do you fix screens?", "How much?"]);
  });

  it("ignores an empty or whitespace-only question", () => {
    expect(enqueue([], "")).toEqual([]);
    expect(enqueue([], "   \n ")).toEqual([]);
    expect(enqueue(["Already queued"], "  ")).toEqual(["Already queued"]);
  });

  it("does not mutate the queue it was given", () => {
    const queue = ["One"];
    enqueue(queue, "Two");
    expect(queue).toEqual(["One"]);
  });
});

describe("coalesce", () => {
  it("joins a burst with one blank line, keeping its order", () => {
    expect(coalesce(["First?", "Second?", "Third?"])).toBe(
      "First?\n\nSecond?\n\nThird?",
    );
  });

  it("leaves a single question unchanged", () => {
    expect(coalesce(["Only question?"])).toBe("Only question?");
  });

  it("is empty when nothing is queued", () => {
    expect(coalesce([])).toBe("");
  });
});

describe("clearQueue and count", () => {
  it("clears to an empty queue", () => {
    expect(clearQueue()).toEqual([]);
  });

  it("reports whether anything is queued and how many", () => {
    expect(hasQueued([])).toBe(false);
    expect(queuedCount([])).toBe(0);
    expect(hasQueued(["One"])).toBe(true);
    expect(queuedCount(["One", "Two"])).toBe(2);
  });
});
