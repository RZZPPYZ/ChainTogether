export type FeatureCommand =
  | { kind: "start"; requirement: string }
  | { kind: "status" }
  | { kind: "resume" }
  | { kind: "roles"; handles: [string, string, string] };

export interface FeatureRoleMember {
  id: string;
  name: string;
  alias?: string | null;
}

export interface FeatureRoleIds {
  owner_agent_id: string;
  reviewer_agent_id: string;
  vision_guardian_agent_id: string;
}

export function parseFeatureCommand(input: string): FeatureCommand | null {
  const match = input.trim().match(/^\/feature(?:\s+([\s\S]*))?$/i);
  if (!match) return null;
  const argument = (match[1] ?? "").trim();
  if (!argument) {
    throw new Error("Add a feature requirement after /feature.");
  }
  if (argument.toLowerCase() === "status") return { kind: "status" };
  if (argument.toLowerCase() === "resume") return { kind: "resume" };
  const roles = argument.match(
    /^roles\s+owner=(\S+)\s+reviewer=(\S+)\s+guardian=(\S+)$/i,
  );
  if (roles) {
    return { kind: "roles", handles: [roles[1], roles[2], roles[3]] };
  }
  if (/^roles\b/i.test(argument)) {
    throw new Error(
      "Use /feature roles owner=@Name reviewer=@Name guardian=@Name.",
    );
  }
  return { kind: "start", requirement: argument };
}

export function resolveFeatureRoles(
  handles: [string, string, string],
  members: FeatureRoleMember[],
): FeatureRoleIds {
  const resolve = (raw: string) => {
    const handle = raw.replace(/^@/, "").toLocaleLowerCase();
    const matches = members.filter((member) =>
      [member.name, member.alias]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLocaleLowerCase() === handle),
    );
    if (matches.length !== 1) {
      throw new Error(`Feature role ${raw} must match one live group agent.`);
    }
    return matches[0].id;
  };
  const ids = handles.map(resolve) as [string, string, string];
  if (new Set(ids).size !== 3) {
    throw new Error("Feature owner, reviewer, and vision guardian must be distinct.");
  }
  return {
    owner_agent_id: ids[0],
    reviewer_agent_id: ids[1],
    vision_guardian_agent_id: ids[2],
  };
}
