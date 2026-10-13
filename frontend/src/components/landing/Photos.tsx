// Free photos from Unsplash (Unsplash License), stored with the site so they load
// where unsplash.com does not. They illustrate the kind of business DuitDuit is for;
// nobody pictured is a DuitDuit customer.
import type { ReactNode } from "react";

const STRIP = [
  { src: "/photos/kl-shop.webp", alt: "A traditional herbal jelly shop in Chinatown, Kuala Lumpur, with a person at the counter", title: "A shop on a busy street", line: "Daily takings, supplier bills and a few regulars on credit.", credit: "Polina Kuzovkova", pos: "50% 60%" },
  { src: "/photos/online-seller.webp", alt: "An online seller photographs a parcel with her phone next to a laptop and stacked boxes", title: "An online seller", line: "Marketplace payouts that arrive days after the sale.", credit: "Rifki Kurniawan", pos: "70% 50%" },
  { src: "/photos/warehouse.webp", alt: "A warehouse aisle with boxes stacked on tall shelves", title: "A small importer", line: "Stock paid up front, customers who pay in 60 days.", credit: "Arum Visuals", pos: "50% 50%" },
];

export function PhotoStrip() {
  return (
    <div className="lv-photos">
      <ul>
        {STRIP.map((p) => (
          <li key={p.src}>
            <img src={p.src} alt={p.alt} loading="lazy" decoding="async" style={{ objectPosition: p.pos }} />
            <strong>{p.title}</strong>
            <span>{p.line}</span>
          </li>
        ))}
      </ul>
      <p className="lv-photo-credit">Illustrative photos from Unsplash by {STRIP.map((p) => p.credit).join(", ")}. Nobody pictured is a DuitDuit customer.</p>
    </div>
  );
}

export function PhotoBanner({ src, alt, credit, children, pos = "50% 50%" }: { src: string; alt: string; credit: string; children: ReactNode; pos?: string }) {
  return (
    <figure className="lv-banner">
      <img src={src} alt={alt} loading="lazy" decoding="async" style={{ objectPosition: pos }} />
      <div className="lv-banner-text">{children}</div>
      <figcaption>{credit}</figcaption>
    </figure>
  );
}
