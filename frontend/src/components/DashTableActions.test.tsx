import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { DashTableActions, DashTableDangerLink, DashTableLink, DashTableNavLink } from "./DashTableActions";

describe("DashTableActions", () => {
  it("renders purple action link and red danger link as plain text", () => {
    render(
      <DashTableActions>
        <DashTableLink onClick={vi.fn()}>查看</DashTableLink>
        <DashTableDangerLink onClick={vi.fn()}>删除</DashTableDangerLink>
      </DashTableActions>
    );
    const view = screen.getByRole("button", { name: "查看" });
    const del = screen.getByRole("button", { name: "删除" });
    expect(view.tagName).toBe("A");
    expect(del.tagName).toBe("A");
    expect(view).toHaveClass("dash-table__link");
    expect(del).toHaveClass("dash-table__danger-link");
  });

  it("renders router nav link with dash-table__link", () => {
    render(
      <MemoryRouter>
        <DashTableNavLink to="/pairwise/1">查看</DashTableNavLink>
      </MemoryRouter>
    );
    const link = screen.getByRole("link", { name: "查看" });
    expect(link).toHaveAttribute("href", "/pairwise/1");
    expect(link).toHaveClass("dash-table__link");
  });

  it("renders download anchor when href is provided", () => {
    render(<DashTableLink href="/api/download">下载</DashTableLink>);
    const link = screen.getByRole("link", { name: "下载" });
    expect(link).toHaveAttribute("href", "/api/download");
    expect(link).toHaveClass("dash-table__link");
  });
});
