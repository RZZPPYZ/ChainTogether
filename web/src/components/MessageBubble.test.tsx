import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MessageBubble } from "./MessageBubble";

describe("MessageBubble turn cost", () => {
  it("shows backend-reported cost as an intuitive per-turn amount", () => {
    render(
      <MessageBubble
        sessionId="session-1"
        message={{ role: "system", type: "result", cost: 0.0042 }}
      />,
    );

    const badge = screen.getByText("Done · Cost ≈0.42¢");
    expect(badge.getAttribute("title")).toBe(
      "Backend-reported cost: $0.004200 USD",
    );
  });
});
