import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ToolStep } from "../lib/toolActivity";
import { ToolActivityGroup } from "./ToolActivityGroup";

function step(overrides: Partial<ToolStep> = {}): ToolStep {
  return {
    id: "use-t1",
    toolName: "Bash",
    input: { command: "bun run test" },
    result: "All good",
    isError: false,
    status: "ok",
    toolUseId: "t1",
    messageIndexes: [0, 1],
    ...overrides,
  };
}

function renderGroup(
  steps: ToolStep[],
  turnEnded: boolean,
  sessionRunning = true,
  sessionId = "session-1",
) {
  return render(
    <ToolActivityGroup
      steps={steps}
      sessionId={sessionId}
      turnEnded={turnEnded}
      sessionRunning={sessionRunning}
    />,
  );
}

describe("ToolActivityGroup disclosure", () => {
  it("collapses a completed successful group to one summary line", () => {
    renderGroup([step()], true);

    expect(screen.getByText(/1 step/)).toBeTruthy();
    expect(screen.queryByText("Ran")).toBeNull();
    expect(screen.queryByText("bun run test")).toBeNull();

    fireEvent.click(screen.getByTestId("tool-activity-toggle"));

    expect(screen.getByText("Ran")).toBeTruthy();
    expect(screen.getByText("bun run test")).toBeTruthy();
  });

  it("expands a group in the live turn by default", () => {
    renderGroup([step({ status: "running", result: undefined })], false);

    expect(screen.getByText("Ran")).toBeTruthy();
    expect(screen.getByText("running")).toBeTruthy();
  });

  it("auto-expands failed steps and keeps the red count after collapsing", () => {
    renderGroup(
      [
        step({
          status: "error",
          isError: true,
          result: "first line\nsecond line\nthird line\nfourth line",
        }),
      ],
      true,
      false,
    );

    // Error groups start open, and the failed step itself starts expanded.
    expect(screen.getByText("1 failed")).toBeTruthy();
    expect(screen.getByText("Ran")).toBeTruthy();
    expect(screen.getByText(/first line/)).toBeTruthy();

    fireEvent.click(screen.getByTestId("tool-activity-toggle"));

    expect(screen.queryByText("Ran")).toBeNull();
    expect(screen.queryByText(/first line/)).toBeNull();
    const failed = screen.getByText("1 failed");
    expect(failed.className).toContain("text-destructive");
  });

  it("lets the user collapse an auto-expanded failed step", () => {
    renderGroup(
      [step({ status: "error", isError: true, result: "boom output" })],
      true,
      false,
    );

    expect(screen.getByText("boom output")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Ran/ }));
    expect(screen.queryByText("boom output")).toBeNull();
  });

  it("auto-collapses an untouched group when the turn ends", () => {
    const { rerender } = renderGroup([step()], false);
    expect(screen.getByText("Ran")).toBeTruthy();

    rerender(
      <ToolActivityGroup
        steps={[step()]}
        sessionId="session-1"
        turnEnded
        sessionRunning={false}
      />,
    );

    expect(screen.queryByText("Ran")).toBeNull();
    expect(screen.getByText(/1 step/)).toBeTruthy();
  });

  it("collapses a legacy finished group without a result badge", () => {
    renderGroup([step()], false, false);

    expect(screen.queryByText("Ran")).toBeNull();
    expect(screen.getByText(/1 step/)).toBeTruthy();
  });

  it("keeps a user-collapsed running group collapsed after the turn ends", () => {
    const running = [step({ status: "running", result: undefined })];
    const { rerender } = renderGroup(running, false);
    fireEvent.click(screen.getByTestId("tool-activity-toggle"));
    expect(screen.queryByText("Ran")).toBeNull();

    rerender(
      <ToolActivityGroup
        steps={[step()]}
        sessionId="session-1"
        turnEnded
        sessionRunning={false}
      />,
    );

    expect(screen.queryByText("Ran")).toBeNull();
  });

  it("keeps a user-expanded historical group open across stream updates", () => {
    const { rerender } = renderGroup([step()], true);
    fireEvent.click(screen.getByTestId("tool-activity-toggle"));
    expect(screen.getByText("Ran")).toBeTruthy();

    const grown = [
      step(),
      step({
        id: "use-t2",
        toolUseId: "t2",
        toolName: "Read",
        input: { file_path: "src/a.ts" },
        result: "x\n",
        messageIndexes: [2, 3],
      }),
    ];
    rerender(
      <ToolActivityGroup
        steps={grown}
        sessionId="session-1"
        turnEnded
        sessionRunning={false}
      />,
    );

    expect(screen.getByText("Ran")).toBeTruthy();
    expect(screen.getByText("Read")).toBeTruthy();
    expect(screen.getByText(/2 steps/)).toBeTruthy();
  });

  it("shows the raw input and output when a step is expanded", () => {
    renderGroup([step()], true);
    fireEvent.click(screen.getByTestId("tool-activity-toggle"));

    expect(screen.queryByText("Input")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Ran/ }));

    expect(screen.getByText("Input")).toBeTruthy();
    expect(screen.getByText("Output")).toBeTruthy();
    expect(screen.getByText(/"command": "bun run test"/)).toBeTruthy();
    expect(screen.getByText("All good")).toBeTruthy();
  });
});
