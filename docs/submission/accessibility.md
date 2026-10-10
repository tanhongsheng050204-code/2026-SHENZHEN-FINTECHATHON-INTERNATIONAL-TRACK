# Accessibility check (Oct 11, 2026)

**What was tested:**
- the signed-in app (18 screens), the landing page and the security page;
- light and dark themes;
- a local build on the synthetic demo company.

**How it was tested:**
- **axe-core 4** with the WCAG 2.1 A and AA rules, run in Chromium through Playwright. Desktop width is 1280 px.
- **Lighthouse 12**, accessibility category, in Chrome's default mobile emulation.
- **Hand checks** with the keyboard.

These are automated checks plus a keyboard pass. They are not a test with screen-reader users, which is **not measured**.

## Results

| Check | Before | After |
|---|---|---|
| axe, WCAG 2.1 AA | First run, 12 screens × 2 themes: violations on all 24 (colour contrast, a tab list without tabs, a bell button whose name hid its count). The wider 20-page run then found an unlabelled file input and two more contrast issues | **0 violations on all 40 page-theme pairs (20 pages × 2 themes)** |
| Lighthouse accessibility: Today, Cash & finance, Financing, Review inbox, Analysis, Trust, e-Invoicing, Ask | 93–94 on the first Lighthouse run (made after the contrast fixes; top-bar buttons had lost their names at phone width) | **100 on all eight** |
| Lighthouse accessibility: landing page | 97 | 97. The remaining flag is a caption on the hero film, measured while it fades in. |
| Escape closes the Ask drawer, the search palette, the notification panel and the account menu | The notification panel and account menu stayed open | **All four close, and focus returns to the button that opened them** |
| Every element reached with Tab shows a visible focus style (first eight on Today) | — | **All eight show a focus ring** |

## What changed

**Colour tokens (light theme):**

| Token | Old | New | Contrast on white |
|---|---|---|---|
| Brand teal for text and buttons | `#0B7A6B` | `#086759` | 4.44 → 5.66 |
| Green | `#0E9F6E` | `#067350` | 3.39 → 5.87 |
| Amber | `#C27A05` | `#8F5A00` | 3.45 → 5.78 |
| Landing faint ink | — | `#61716C` | 5.14 |

The logo tile keeps `#0B7A6B`, because it is not text.

**Dark theme:** the danger red is now `#F07163` (5.56:1 on cards).

**Text and buttons:**
- Small print is at least 11.5 px.
- No faded copies of small print remain.
- Buttons that hold numbers now inherit the theme's text colour.

**Names and roles:**
- The e-Invoicing switch uses `role="tab"` with `aria-selected`.
- The bell's accessible name includes its unread count.
- The file input has a label.
- The last column of the e-Invoicing table has a header.
- Top-bar labels hidden on narrow screens stay readable by screen readers.

**Keyboard:**
- Escape closes the notification panel and the account menu.
- Focus returns to the button that opened them.

Phone layout is covered by [execution-evidence.md](execution-evidence.md): no sideways scrolling on 18 screens at 375 px, and 44 px touch targets.
