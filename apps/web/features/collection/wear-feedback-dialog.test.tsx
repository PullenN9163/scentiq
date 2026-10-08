import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { WearFeedbackDialog } from "./wear-feedback-dialog";
const { load, save } = vi.hoisted(() => ({ load: vi.fn(), save: vi.fn() }));
vi.mock("@/lib/server/feedback-actions", () => ({ getWearFeedback: load, saveWearFeedback: save }));
describe("WearFeedbackDialog", () => {
  it("loads saved feedback, supports editing, and closes only after a successful save", async () => {
    load.mockResolvedValue({ rating: 4, longevity: 7, projection: "moderate", comments: "Good for work" });
    save.mockResolvedValue({ status: "success", message: "Feedback saved." });
    const close = vi.fn();
    render(<WearFeedbackDialog wearId="wear" onClose={close} />);
    expect(await screen.findByLabelText("Rating (1–5)")).toHaveValue(4);
    expect(screen.getByLabelText("Projection")).toHaveValue("moderate");
    await userEvent.clear(screen.getByLabelText("Rating (1–5)"));
    await userEvent.type(screen.getByLabelText("Rating (1–5)"), "5");
    await userEvent.click(screen.getByRole("button", { name: "Save feedback" }));
    expect(save).toHaveBeenCalled();
    expect(close).toHaveBeenCalledOnce();
  });
  it("keeps feedback open when saving fails", async () => {
    load.mockResolvedValue(null);
    save.mockResolvedValue({ status: "error", message: "Could not save", values: { rating: "3" } });
    const close = vi.fn();
    render(<WearFeedbackDialog wearId="wear" onClose={close} />);
    await screen.findByLabelText("Rating (1–5)");
    await userEvent.click(screen.getByRole("button", { name: "Save feedback" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save");
    expect(close).not.toHaveBeenCalled();
  });
});
