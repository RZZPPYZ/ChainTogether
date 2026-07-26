export function formatTurnCost(cost: number | null | undefined): string | null {
  if (cost == null || !Number.isFinite(cost) || cost < 0) return null;
  if (cost === 0) return "$0.00";
  if (cost < 0.0001) return "<0.01¢";
  if (cost < 0.01) return `≈${(cost * 100).toFixed(2)}¢`;
  if (cost < 1) return `≈${(cost * 100).toFixed(1)}¢`;
  return `≈$${cost.toFixed(2)}`;
}

export function exactTurnCostTitle(cost: number): string {
  return `Backend-reported cost: $${cost.toFixed(6)} USD`;
}
