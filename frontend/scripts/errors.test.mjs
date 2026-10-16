// Error messages say what happened and what to do, never a bare "couldn't load".
import assert from "node:assert/strict";
import { test } from "node:test";
import { friendlyActionError, friendlyLoadError } from "../src/api/errors.ts";

test("a server crash says the data is safe", () => {
  assert.match(friendlyLoadError("Internal Server Error"), /went wrong on DuitDuit's server/);
  assert.match(friendlyLoadError("request_failed_500"), /went wrong on DuitDuit's server/);
});

test("rate limits, missing and changed items are named", () => {
  assert.match(friendlyLoadError("rate_limited"), /Too many requests/);
  assert.match(friendlyLoadError("request_failed_404"), /no longer exists/);
  assert.match(friendlyLoadError("request_failed_409"), /changed this at the same time/);
});

test("a failed action says nothing was changed", () => {
  assert.match(friendlyActionError("Internal Server Error"), /nothing was changed/);
  assert.match(friendlyActionError("some_unknown_code"), /nothing was changed.*code: some_unknown_code/);
  assert.equal(friendlyActionError("insufficient_role"), friendlyLoadError("insufficient_role"));
});

test("known codes keep their messages", () => {
  assert.match(friendlyLoadError("authentication_required"), /log in again/);
  assert.match(friendlyLoadError("Failed to fetch"), /can't reach its server/);
});
