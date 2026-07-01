import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OnlineCasePreview } from "./OnlineCasePreview";
import { renderWithProviders } from "../test/renderWithProviders";

const YAML_TEXT = `
- sample_id: online_99
  scenario: 线上真实对话
  sub_scenario: 抗阻运动与瑜伽对比
  level: L2
  score_profile: default
  source: online
  turns:
  - role: user
    content: 抗阻运动好还是做瑜伽好
  - role: assistant
    content: |-
      看你现在的状态，两种运动其实各有侧重——


      **抗阻运动（轻量力量训练）**对内分泌治疗期的你更友好一些。



      **瑜伽**也不错，但建议选偏舒缓的流派。

      具体怎么选，可以跟医生或康复师确认一下：
      - 关节目前影响日常行走了，运动强度得怎么定
      - 有没有需要避开的动作类型
`;

describe("OnlineCasePreview", () => {
  it("renders online markdown as compact readable Q&A", () => {
    const { container } = renderWithProviders(<OnlineCasePreview yamlText={YAML_TEXT} />);

    expect(screen.getByText("用户问题")).toBeInTheDocument();
    expect(screen.getByText("Cx 回复")).toBeInTheDocument();
    expect(screen.getByText("抗阻运动好还是做瑜伽好")).toBeInTheDocument();
    expect(container.textContent).not.toContain("**");
    expect(container.querySelectorAll('p strong')).toHaveLength(2);
    expect(container.querySelectorAll("ul li")).toHaveLength(2);
    const paragraphs = Array.from(container.querySelectorAll('[data-testid="online-case-paragraph"]'));
    expect(paragraphs).toHaveLength(5);
    expect(paragraphs.every((node) => node.textContent?.trim())).toBe(true);
  });

  it("renders every user and assistant turn from online benchmark YAML", () => {
    const { container } = renderWithProviders(
      <OnlineCasePreview
        yamlText={`
- sample_id: online_rec
  turns:
  - role: user
    content: 第一问
  - role: assistant
    content: 第一答
  - role: user
    content: 第二问
  - role: assistant
    content: 第二答
`}
      />
    );
    const preview = within(container);

    expect(preview.getByText("第 1 轮")).toBeInTheDocument();
    expect(preview.getByText("第 2 轮")).toBeInTheDocument();
    expect(preview.getByText("第一问")).toBeInTheDocument();
    expect(preview.getByText("第一答")).toBeInTheDocument();
    expect(preview.getByText("第二问")).toBeInTheDocument();
    expect(preview.getByText("第二答")).toBeInTheDocument();
  });

  it("renders Feishu image tokens as images and ignores sibling notes", () => {
    const { container } = renderWithProviders(
      <OnlineCasePreview
        yamlText={`
- sample_id: online_img
  turns:
  - role: user
    content: '[图片：image_token=Rhb9bkUUfoA7rSxq4YzcVTT8nAs，尺寸=1200x1600]'
  - role: assistant
    content: |-
      这是报告解读。
  notes: 第一轮用户输入：image_token=Rhb9bkUUfoA7rSxq4YzcVTT8nAs 1200x1600
`}
      />
    );

    const image = screen.getByTestId("online-case-image");
    expect(image).toHaveAttribute(
      "src",
      "/api/benchmarks/feishu-images/Rhb9bkUUfoA7rSxq4YzcVTT8nAs"
    );
    expect(screen.getByText("这是报告解读。")).toBeInTheDocument();
    expect(container.textContent).not.toContain("notes:");
  });
});
