import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import { FeishuMention } from "./FeishuMention";

describe("FeishuMention", () => {
  it("renders a creator as a Feishu-style mention", () => {
    renderWithProviders(<FeishuMention name="曹冬东" />);

    expect(screen.getByLabelText("@曹冬东")).toHaveTextContent("@曹冬东");
  });

  it("uses a neutral placeholder for historical anonymous runs", () => {
    renderWithProviders(<FeishuMention name={null} />);

    expect(screen.getByText("—")).toHaveClass("feishu-mention--empty");
  });
});
