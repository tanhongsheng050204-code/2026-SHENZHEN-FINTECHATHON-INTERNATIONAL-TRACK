/**
 * An image source for the authenticator QR code Supabase returns.
 *
 * Supabase sends the code as SVG, either raw ("<svg …>") or as a data URL whose SVG
 * is not percent-encoded ("data:image/svg+xml;utf-8,<svg …>"). A raw string is not
 * an image URL, and an unencoded "#" in a data URL cuts the image short, so both
 * shapes are rebuilt as a properly encoded data URL. Anything else (a PNG data URL)
 * is used as it is.
 */
export function qrImageSource(qr: string): string {
  const value = qr.trim();
  let svg: string | null = null;
  if (value.startsWith("<")) {
    svg = value;
  } else if (value.startsWith("data:image/svg+xml")) {
    const body = value.slice(value.indexOf(",") + 1);
    try {
      svg = body.startsWith("%3C") || body.startsWith("%3c") ? decodeURIComponent(body) : body;
    } catch {
      svg = body;
    }
  }
  return svg === null ? value : `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}
