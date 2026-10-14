// Whether the signed-in company has any records of its own yet. A company with no
// imported bank balance gets the synthetic demo company's figures from the API
// (data_mode "stub"); those must never look like the company's own numbers, so the
// money pages show a "no records yet" start instead. Asked once per signed-in person.
import { useEffect, useState } from "react";
import { fetchForecast } from "../api/topicE";
import { canOpen } from "./access";
import type { Role } from "../api/client";

export type RecordsState = "checking" | "has" | "none";

const known = new Map<string, Promise<RecordsState>>();

function check(userId: string): Promise<RecordsState> {
  let pending = known.get(userId);
  if (!pending) {
    pending = fetchForecast(30)
      .then((f) => (f.data_mode === "stub" ? "none" : "has") as RecordsState)
      // If it can't be told, show the pages as they are; they handle their own errors.
      .catch(() => "has" as RecordsState);
    known.set(userId, pending);
  }
  return pending;
}

/** Call after an import so the money pages are shown again. */
export function forgetCompanyRecords() {
  known.clear();
}

export function useCompanyRecords(userId: string | null | undefined, role: Role | null | undefined): RecordsState {
  const applies = Boolean(userId) && canOpen("cashflow", role);
  const [state, setState] = useState<{ user: string; value: RecordsState } | null>(null);

  useEffect(() => {
    if (!applies || !userId) return;
    let active = true;
    void check(userId).then((value) => {
      if (active) setState({ user: userId, value });
    });
    return () => { active = false; };
  }, [applies, userId]);

  if (!applies) return "has";
  return state && state.user === userId ? state.value : "checking";
}
