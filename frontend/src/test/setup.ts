import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Ant Design 会读取伪元素样式；jsdom 不实现第二个参数且会向 stderr 输出噪音。
// 测试并不依赖伪元素布局，统一退化为元素本身的计算样式。
const nativeGetComputedStyle = window.getComputedStyle.bind(window);
vi.spyOn(window, "getComputedStyle").mockImplementation((element) =>
  nativeGetComputedStyle(element)
);
