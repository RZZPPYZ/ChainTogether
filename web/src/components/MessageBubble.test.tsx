import { fireEvent, render, screen } from "@testing-library/react";
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

describe("MessageBubble thinking", () => {
  it("shows a collapsed thinking block and expands it on click", () => {
    render(
      <MessageBubble
        sessionId="session-1"
        message={{
          role: "assistant",
          type: "thinking",
          content: "Step one: inspect the caller.",
        }}
      />,
    );

    expect(screen.getByText("Thinking")).toBeTruthy();
    expect(screen.queryByText(/Step one/)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /Thinking/ }));

    expect(screen.getByText(/Step one/)).toBeTruthy();
  });

  it("renders nothing for a blank thinking block", () => {
    const { container } = render(
      <MessageBubble
        sessionId="session-1"
        message={{ role: "assistant", type: "thinking", content: "  " }}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});

describe("MessageBubble tool activity", () => {
  it("leaves tool messages to the activity trail component", () => {
    const { container } = render(
      <MessageBubble
        sessionId="session-1"
        message={{
          role: "tool",
          type: "tool_use",
          tool_name: "Bash",
          tool_input: { command: "ls" },
          tool_use_id: "tool-1",
        }}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
