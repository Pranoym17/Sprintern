import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SearchableMultiSelect } from "./searchable-multi-select";
import { ROLE_CATEGORY_OPTIONS } from "@/lib/filter-options";

afterEach(cleanup);

describe("SearchableMultiSelect", () => {
  it("filters valid suggestions and selects one with the keyboard", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<SearchableMultiSelect
      id="roles"
      label="Roles"
      values={[]}
      options={["Software Engineering", "Product Management"]}
      placeholder="Search roles"
      onChange={onChange}
    />);

    const input = screen.getByRole("combobox", { name:"Roles" });
    await user.type(input, "software");
    expect(screen.getByRole("option", { name:"Software Engineering" })).toBeVisible();
    expect(screen.queryByRole("option", { name:"Product Management" })).not.toBeInTheDocument();
    await user.keyboard("{ArrowDown}{Enter}");
    expect(onChange).toHaveBeenCalledWith(["Software Engineering"]);
  });

  it("accepts a custom searchable value", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<SearchableMultiSelect
      id="locations"
      label="Locations"
      values={[]}
      options={["Toronto, ON", "Remote"]}
      placeholder="Search locations"
      onChange={onChange}
    />);

    await user.type(screen.getByRole("combobox", { name:"Locations" }), "Waterloo, ON{Enter}");
    expect(onChange).toHaveBeenCalledWith(["Waterloo, ON"]);
  });

  it("shows grouped choices and lets the unrestricted choice replace narrow values", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<SearchableMultiSelect
      id="all-roles"
      label="Roles"
      values={["software_engineering"]}
      options={ROLE_CATEGORY_OPTIONS}
      placeholder="Search roles"
      onChange={onChange}
      allowCustom={false}
      exclusiveValues={["all"]}
      displayValue={(value) => value === "all" ? "All internship roles" : "Software engineering"}
    />);

    await user.type(screen.getByRole("combobox", { name:"Roles" }), "all");
    expect(screen.getByText("Everything")).toBeVisible();
    await user.click(screen.getByRole("option", { name: /all internship roles/i }));
    expect(onChange).toHaveBeenCalledWith(["all"]);
  });
});
