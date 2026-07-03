import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import { FeishuRichText } from "./FeishuRichText";

describe("FeishuRichText", () => {
  it("renders Feishu image tokens as image elements", () => {
    renderWithProviders(
      <FeishuRichText text="请看 [图片：image_token=Rhb9bkUUfoA7rSxq4YzcVTT8nAs，尺寸=1200x1600]" />
    );

    const image = screen.getByTestId("online-case-image");
    expect(image).toHaveAttribute(
      "src",
      "/api/benchmarks/feishu-images/Rhb9bkUUfoA7rSxq4YzcVTT8nAs"
    );
    expect(image).toHaveAttribute("title", "1200x1600");
  });

  it("opens a larger image preview on double click", () => {
    const { container } = renderWithProviders(
      <FeishuRichText text="请看 [图片：image_token=Rhb9bkUUfoA7rSxq4YzcVTT8nAs，尺寸=1200x1600]" />
    );

    fireEvent.doubleClick(within(container).getByTestId("online-case-image"));

    const preview = screen.getByTestId("online-case-image-preview");
    expect(preview).toHaveAttribute(
      "src",
      "/api/benchmarks/feishu-images/Rhb9bkUUfoA7rSxq4YzcVTT8nAs"
    );
  });
});
