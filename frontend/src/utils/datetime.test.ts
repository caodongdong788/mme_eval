import { describe, expect, it } from "vitest";
import {
  formatApiDateTime,
  formatApiDateTimeShort,
  parseApiDateTime,
} from "./datetime";

describe("parseApiDateTime", () => {
  it("treats naive ISO from API as UTC", () => {
    expect(parseApiDateTime("2026-06-16T07:14:08").toISOString()).toBe(
      "2026-06-16T07:14:08.000Z"
    );
  });

  it("accepts Z suffix", () => {
    expect(parseApiDateTime("2026-06-16T07:14:08Z").toISOString()).toBe(
      "2026-06-16T07:14:08.000Z"
    );
  });
});

describe("formatApiDateTime", () => {
  it("converts UTC to local display", () => {
    const text = formatApiDateTime("2026-06-16T07:14:08Z");
    const expected = new Date("2026-06-16T07:14:08Z").toLocaleString();
    expect(text).toBe(expected);
  });
});

describe("formatApiDateTimeShort", () => {
  it("uses Asia/Shanghai independently of the runtime timezone", () => {
    expect(formatApiDateTimeShort("2026-06-11T07:00:00")).toBe(
      "2026-06-11 15:00"
    );
  });
});
