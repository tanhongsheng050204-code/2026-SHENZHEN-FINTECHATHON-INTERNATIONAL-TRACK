import assert from "node:assert/strict";
import test from "node:test";
import { backendUrl } from "../api/proxy.js";

const ORIGIN = "https://api.example.test";
const viaRewrite = (path, query = "") =>
  `https://app.example.test/api/proxy?__fbpath=${path}${query}`;

test("plain paths and their query strings reach the backend", () => {
  const target = backendUrl(viaRewrite("review-inbox", "&job_function=finance"), ORIGIN);
  assert.equal(target?.href, "https://api.example.test/review-inbox?job_function=finance");
});

// References such as "payable:12:duplicate" or "customer:7" are sent percent-encoded.
for (const [label, path] of [
  ["once", "insights/anomalies/payable%3A12%3Aduplicate/review"],
  ["twice", "insights/anomalies/payable%253A12%253Aduplicate/review"],
]) {
  test(`a reference with colons, encoded ${label}, reaches the backend`, () => {
    const target = backendUrl(viaRewrite(path), ORIGIN);
    assert.equal(target?.pathname, "/insights/anomalies/payable%3A12%3Aduplicate/review");
  });
}

test("a hold on a whole customer reaches the backend", () => {
  const target = backendUrl(viaRewrite("collections/holds/customer%3A7"), ORIGIN);
  assert.equal(target?.pathname, "/collections/holds/customer%3A7");
});

for (const path of ["..", "a/../b", "a/%2E%2E/b", "a/%252E%252E/b", "a%252Fb", "a%5Cb", "a\\b", "a%00b", "%E0%A4%A"]) {
  test(`${path} is refused`, () => assert.equal(backendUrl(viaRewrite(path), ORIGIN), null));
}

test("the backend host can never be changed by the path", () => {
  const target = backendUrl(viaRewrite("https%3A%2F%2Fevil.test%2Fx"), ORIGIN);
  assert.ok(target === null || target.host === "api.example.test");
});
