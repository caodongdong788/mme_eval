import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { renderWithProviders } from "../test/renderWithProviders";
import { OpenApiKeysPanel } from "./OpenApiKeysPanel";

vi.mock("../api", () => ({
  api: {
    listOpenApiKeys: vi.fn(),
    createOpenApiKey: vi.fn(),
    updateOpenApiKey: vi.fn(),
    rotateOpenApiKey: vi.fn(),
    deleteOpenApiKey: vi.fn(),
  },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("OpenApiKeysPanel", () => {
  it("keeps the complete key viewable after creation", async () => {
    vi.mocked(api.listOpenApiKeys).mockResolvedValue([
      {
        id: 1,
        name: "CX 本地验证",
        api_key: "mme_complete_recoverable_key",
        key_prefix: "mme_complete_r…",
        permissions: ["temporary_evaluations:create"],
        created_by: "管理员",
      },
    ]);

    renderWithProviders(<OpenApiKeysPanel />);

    expect(await screen.findByDisplayValue("mme_complete_recoverable_key")).toBeInTheDocument();
    expect(screen.getByText("完整 Key 可在此随时查看、复制和轮换。")).toBeInTheDocument();
  });
});
