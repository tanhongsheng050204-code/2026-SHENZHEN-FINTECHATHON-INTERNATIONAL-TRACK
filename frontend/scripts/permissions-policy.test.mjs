import assert from "node:assert/strict";
import test from "node:test";
import { microphoneIsSelfOnly } from "./permissions-policy.mjs";

test("microphone permits this origin only", () => {
  assert.equal(microphoneIsSelfOnly("camera=(), microphone=(self), geolocation=()"), true);
});
for (const policy of ["camera=()", "microphone=()", "microphone=*", "microphone=(*)",
  'microphone=(self "https://example.test")', "microphone=(self), microphone=*",
  "microphone=(self), microphone = *"]) {
  test(`microphone rejects ${policy}`, () => assert.equal(microphoneIsSelfOnly(policy), false));
}
