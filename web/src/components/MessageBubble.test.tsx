import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MessageBubble } from "./MessageBubble";

describe("MessageBubble turn tokens", () => {
  it("shows the turn's token count instead of a dollar amount", () => {
    render(
      <MessageBubble
        sessionId="session-1"
        message={{
          role: "system",
          type: "result",
          cost: 0.0042,
          context_usage: {
            backend: "claude-code",
            input_tokens: 250,
            cached_input_tokens: 24832,
            cache_creation_input_tokens: 0,
            output_tokens: 2,
            turn_tokens: 25084,
            source: "estimated",
          },
        }}
      />,
    );

    const badge = screen.getByText("Done · 25.1k tokens");
    expect(badge.getAttribute("title")).toBe(
      "This turn: 25,084 tokens (250 input · 24,832 cached · 2 output)",
    );
  });

  it("omits the token suffix when the backend reported no usage", () => {
    render(
      <MessageBubble
        sessionId="session-1"
        message={{ role: "system", type: "result", cost: 0.0042 }}
      />,
    );

    expect(screen.getByText("Done")).toBeTruthy();
  });
});
