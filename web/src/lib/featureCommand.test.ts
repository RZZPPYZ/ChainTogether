import { describe, expect, it } from "vitest";

import { parseFeatureCommand, resolveFeatureRoles } from "./featureCommand";


describe("group /feature command", () => {
  it("treats the remaining sentence as an autonomous start requirement", () => {
    expect(parseFeatureCommand("/feature build a durable export flow")).toEqual({
      kind: "start",
      requirement: "build a durable export flow",
    });
  });

  it("parses lifecycle controls without confusing requirements that start similarly", () => {
    expect(parseFeatureCommand("/feature status")).toEqual({ kind: "status" });
    expect(parseFeatureCommand("/feature resume")).toEqual({ kind: "resume" });
    expect(parseFeatureCommand("/feature status dashboard")).toEqual({
      kind: "start",
      requirement: "status dashboard",
    });
  });

  it("requires a sentence and resolves three distinct live role handles", () => {
    expect(() => parseFeatureCommand("/feature")).toThrow("requirement");
    const members = [
      { id: "a", name: "Owner", alias: "Maker" },
      { id: "b", name: "Reviewer", alias: null },
      { id: "c", name: "Guardian", alias: "Vision" },
    ];
    expect(
      parseFeatureCommand(
        "/feature roles owner=@Maker reviewer=@Reviewer guardian=@Vision",
      ),
    ).toEqual({
      kind: "roles",
      handles: ["@Maker", "@Reviewer", "@Vision"],
    });
    expect(resolveFeatureRoles(["@Maker", "@Reviewer", "@Vision"], members)).toEqual({
      owner_agent_id: "a",
      reviewer_agent_id: "b",
      vision_guardian_agent_id: "c",
    });
    expect(() =>
      resolveFeatureRoles(["@Owner", "@Owner", "@Guardian"], members),
    ).toThrow("distinct");
  });

  it("rejects an incomplete roles control instead of starting a feature", () => {
    expect(() =>
      parseFeatureCommand("/feature roles owner=@Owner reviewer=@Reviewer"),
    ).toThrow("guardian");
  });
});
