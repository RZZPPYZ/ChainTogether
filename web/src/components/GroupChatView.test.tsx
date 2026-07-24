import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GroupMarkdown, highlightMentions } from "./GroupChatView";

describe("group mention highlighting", () => {
  it("highlights canonical and alias handles without changing message text", () => {
    const { container } = render(
      <div>{highlightMentions("@Builder, ask @FENG.", ["Builder", "Feng"])}</div>,
    );

    expect(container.textContent).toBe("@Builder, ask @FENG.");
    expect(
      [...container.querySelectorAll(".mention-highlight")].map(
        (element) => element.textContent,
      ),
    ).toEqual(["@Builder", "@FENG"]);
  });

  it("highlights mentions inside Markdown but leaves code unchanged", () => {
    const { container } = render(
      <GroupMarkdown
        text={"**@Builder** continue, but keep `@Builder` literal."}
        memberNames={["Builder"]}
      />,
    );

    expect(container.querySelectorAll(".mention-highlight")).toHaveLength(1);
    expect(container.querySelector("strong .mention-highlight")?.textContent).toBe(
      "@Builder",
    );
    expect(container.querySelector("code")?.textContent).toBe("@Builder");
  });
});
