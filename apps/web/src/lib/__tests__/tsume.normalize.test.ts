import { normalizeMove } from "@/lib/learn/tsume";

test("normalizes basic moves", () => {
  expect(normalizeMove(" 7G7F ")).toBe("7g7f");
  expect(normalizeMove("７ｇ７ｆ")).toBe("7g7f");
  expect(normalizeMove("P-7f")).toBe("p-7f");
});
