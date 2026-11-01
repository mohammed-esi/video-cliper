import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  pruneExportSelection,
  selectAllClipIds,
  toggleExportSelectionId,
} from "./export-selection.ts";

describe("export selection helpers", () => {
  it("toggles individual clip ids", () => {
    const first = toggleExportSelectionId(new Set(), "a", true);
    assert.deepEqual([...first], ["a"]);
    const second = toggleExportSelectionId(first, "a", false);
    assert.equal(second.size, 0);
  });

  it("selects all clip ids", () => {
    const all = selectAllClipIds([{ id: "a" }, { id: "b" }]);
    assert.deepEqual([...all].sort(), ["a", "b"]);
  });

  it("drops stale ids when clips change", () => {
    const pruned = pruneExportSelection(
      new Set(["a", "b", "missing"]),
      new Set(["a", "b"]),
    );
    assert.deepEqual([...pruned].sort(), ["a", "b"]);
  });
});
