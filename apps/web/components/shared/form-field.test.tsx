import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Field, FormMessage } from "./form-field";
import { Input } from "@/components/ui/input";
import type { ActionState } from "@/lib/action-state";

const idle: ActionState = { status: "idle" };

describe("Field", () => {
  it("labels the control and uses the fallback value", () => {
    render(
      <Field name="display_name" label="Display name" state={idle} fallbackValue="Maya">
        {(props) => <Input type="text" {...props} />}
      </Field>,
    );

    const input = screen.getByLabelText("Display name");
    expect(input).toHaveValue("Maya");
    expect(input).not.toHaveAttribute("aria-invalid");
  });

  it("keeps the submitted value after a failure", () => {
    const failed: ActionState = {
      status: "error",
      fieldErrors: { display_name: "Enter a display name" },
      values: { display_name: "  " },
    };

    render(
      <Field name="display_name" label="Display name" state={failed} fallbackValue="Maya">
        {(props) => <Input type="text" {...props} />}
      </Field>,
    );

    // The user's input survives rather than reverting to the stored value.
    expect(screen.getByLabelText("Display name")).toHaveValue("  ");
  });

  it("associates the error with the control", () => {
    const failed: ActionState = {
      status: "error",
      fieldErrors: { display_name: "Enter a display name" },
    };

    render(
      <Field name="display_name" label="Display name" state={failed}>
        {(props) => <Input type="text" {...props} />}
      </Field>,
    );

    const input = screen.getByLabelText("Display name");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a display name");
    expect(input).toHaveAttribute("aria-describedby", "field-display_name-error");
  });

  it("describes the control with a hint", () => {
    render(
      <Field name="price" label="Price" state={idle} hint="Optional, e.g. 129.50">
        {(props) => <Input type="text" {...props} />}
      </Field>,
    );

    expect(screen.getByLabelText("Price")).toHaveAttribute(
      "aria-describedby",
      "field-price-hint",
    );
    expect(screen.getByText("Optional, e.g. 129.50")).toBeVisible();
  });
});

describe("FormMessage", () => {
  it("renders nothing while idle", () => {
    const { container } = render(<FormMessage state={idle} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("announces a success as a status", () => {
    render(<FormMessage state={{ status: "success", message: "Profile updated." }} />);

    expect(screen.getByRole("status")).toHaveTextContent("Profile updated.");
  });

  it("announces a failure as an alert", () => {
    render(<FormMessage state={{ status: "error", message: "Something went wrong." }} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong.");
  });
});
