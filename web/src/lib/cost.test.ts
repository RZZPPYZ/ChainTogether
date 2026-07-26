import { describe, expect, it } from "vitest";

import { exactTurnCostTitle, formatTurnCost } from "./cost";

describe("turn cost formatting", () => {
  it("turns small dollar amounts into readable cents", () => {
    expect(formatTurnCost(0.0042)).toBe("≈0.42¢");
    expect(formatTurnCost(0.08)).toBe("≈8.0¢");
  });

  it("keeps larger amounts in dollars and rejects missing values", () => {
    expect(formatTurnCost(1.234)).toBe("≈$1.23");
    expect(formatTurnCost(null)).toBeNull();
    expect(formatTurnCost(Number.NaN)).toBeNull();
  });

  it("preserves the precise backend amount in the tooltip", () => {
    expect(exactTurnCostTitle(0.0042)).toBe(
      "Backend-reported cost: $0.004200 USD",
    );
  });
});
