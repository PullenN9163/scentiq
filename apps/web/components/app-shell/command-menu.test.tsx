import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CommandMenu } from "./command-menu";
const { push, search } = vi.hoisted(() => ({ push: vi.fn(), search: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/server/collection-search", () => ({ searchOwnCollection: search }));
describe("CommandMenu", () => {
  beforeEach(() => { search.mockResolvedValue([{ id: "owned", name: "Green Fig", brand: "Private House" }]); vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} }); Element.prototype.scrollIntoView = vi.fn(); });
  it("opens with Ctrl K, searches the collection, and navigates", async () => {
    render(<CommandMenu />);
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(screen.getByRole("dialog", { name: "Search ScentIQ" })).toBeVisible();
    await userEvent.type(screen.getByRole("combobox"), "Fig");
    await userEvent.click(await screen.findByText("Green Fig"));
    expect(push).toHaveBeenCalledWith("/collection/owned");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
