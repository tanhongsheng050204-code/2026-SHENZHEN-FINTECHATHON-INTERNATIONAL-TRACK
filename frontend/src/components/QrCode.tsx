import { useMemo } from "react";
import qrcode from "qrcode-generator";

/**
 * A QR code drawn in the browser. Nothing leaves the page: an online QR service
 * would learn every invoice UIN, and is not reliably reachable from mainland China.
 */
export function QrCode({ value, size = 64, label }: { value: string; size?: number; label: string }) {
  const { count, cells } = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(value);
    qr.make();
    const n = qr.getModuleCount();
    const dark: string[] = [];
    for (let row = 0; row < n; row++) {
      for (let col = 0; col < n; col++) {
        if (qr.isDark(row, col)) dark.push(`M${col + 2} ${row + 2}h1v1h-1z`);
      }
    }
    return { count: n, cells: dark.join("") };
  }, [value]);

  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${count + 4} ${count + 4}`}
      width={size}
      height={size}
      shapeRendering="crispEdges"
      style={{ flex: "0 0 auto", borderRadius: "8px", border: "1px solid var(--line)", background: "#fff" }}
    >
      <path d={cells} fill="#000" />
    </svg>
  );
}
