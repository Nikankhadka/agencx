import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  CategoryPicker,
  normalizedCategoryName,
  splitCategoryNames,
} from "./CategoryPicker";

describe("CategoryPicker", () => {
  it("renders every confirmed selection and identifies the primary", () => {
    const html = renderToStaticMarkup(
      <CategoryPicker
        categories={[
          { id: "repairs", name: "Repairs" },
          { id: "screens", name: "Screen care" },
        ]}
        selectedIds={["repairs", "screens"]}
        primaryId="screens"
        onChange={() => {}}
        onCreate={async () => ({ id: "new", name: "New" })}
      />,
    );

    expect(html).toContain("Repairs");
    expect(html).toContain("Screen care");
    expect(html).toContain('aria-label="Make Screen care primary"');
    expect(html).toContain('aria-pressed="true"');
  });

  it("suggests separator-delimited labels as distinct category names", () => {
    expect(splitCategoryNames("Repairs / Screen care & Accessories; Featured")).toEqual([
      "Repairs",
      "Screen care",
      "Accessories",
      "Featured",
    ]);
  });

  it("normalizes punctuation and unicode before matching existing categories", () => {
    expect(normalizedCategoryName("  Screen-care & Repairs  ")).toBe(
      normalizedCategoryName("screen care / repairs"),
    );
  });
});
