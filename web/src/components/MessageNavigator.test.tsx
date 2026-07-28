import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Message } from "../stores/sessionStore";
import { MessageNavigator } from "./MessageNavigator";
import {
  buildUserMessageMarkers,
  isUserAuthoredMessage,
  messagePreview,
} from "../lib/messageNavigation";

describe("user message markers", () => {
  it("recognizes human turns and excludes injected user-role events", () => {
    expect(
      isUserAuthoredMessage({ role: "user", type: "text", content: "Hello" }),
    ).toBe(true);
    expect(
      isUserAuthoredMessage({
        role: "user",
        type: "text",
        content: "  [agent-reply:Builder]\n\nDone",
      }),
    ).toBe(false);
    expect(
      isUserAuthoredMessage({
        role: "user",
        type: "text",
        content: "[group-invocation:group-1:run-1]\n\nBuild it",
      }),
    ).toBe(false);
  });

  it("builds compact previews at the original message indices", () => {
    const messages: Message[] = [
      { role: "user", type: "text", content: "First\nquestion" },
      { role: "assistant", type: "text", content: "Answer" },
      { role: "user", type: "text", content: "Second question" },
    ];

    expect(buildUserMessageMarkers(messages)).toEqual([
      { index: 0, preview: "First question" },
      { index: 2, preview: "Second question" },
    ]);
    expect(messagePreview("", 20)).toBe("Message with attachments");
  });
});

describe("MessageNavigator", () => {
  it("stays hidden until the conversation has multiple user turns", () => {
    const { container } = render(
      <MessageNavigator
        markers={[{ index: 0, preview: "Only message" }]}
        totalItems={1}
        onNavigate={() => {}}
      />,
    );

    expect(container.querySelector(".message-navigator")).toBeNull();
  });

  it("navigates to a marker and highlights the active one", () => {
    const onNavigate = vi.fn();
    render(
      <MessageNavigator
        markers={[
          { index: 0, preview: "First message" },
          { index: 4, preview: "Later message" },
        ]}
        totalItems={5}
        activeIndex={4}
        onNavigate={onNavigate}
      />,
    );

    const later = screen.getByRole("button", {
      name: "Jump to your message 2: Later message",
    });
    expect(later.className).toContain("is-active");
    expect(later.getAttribute("aria-current")).toBe("location");
    fireEvent.click(later);
    expect(onNavigate).toHaveBeenCalledWith(4);
  });
});
