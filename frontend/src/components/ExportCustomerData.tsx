import { useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { exportCustomerData } from "../api/security";
import { ApiError, friendlyLoadError } from "../api/client";
import { useI18n } from "../lib/i18n";

/**
 * PDPA data portability for Compliance: this customer's records as a JSON file.
 * Each protected value in it is a disclosure recorded on the audit chain.
 */
export function ExportCustomerData({ customerId }: { customerId: number }) {
  const { tx } = useI18n();
  const { identity } = useAuth();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  if (identity?.role !== "compliance") return null;

  const download = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const file = await exportCustomerData(customerId);
      const url = URL.createObjectURL(file);
      const link = document.createElement("a");
      link.href = url;
      link.download = `customer-${customerId}-export.json`;
      link.click();
      URL.revokeObjectURL(url);
      setMessage(tx("Export downloaded. It is recorded on the audit trail; send it to the person securely."));
    } catch (e) {
      setMessage(friendlyLoadError(e instanceof ApiError ? e.code : ""));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="dd-export">
      <button className="fb-btn fb-btn-outline" type="button" disabled={busy} onClick={() => void download()}>
        {busy ? tx("Preparing…") : tx("Export this customer's data (PDPA)")}
      </button>
      {message && <span className="fb-fine" role="status">{message}</span>}
    </div>
  );
}
