# Responsive test report — 2026-11-21

## Automated/static checks run

- `index.html` contains a mobile-menu trigger linked to `#sidebar` with `aria-controls` and `aria-expanded`.
- A separate overlay button and drawer close button are present.
- `app.js` closes the drawer through overlay click, Escape, navigation, close button and desktop breakpoint reset.
- `body.drawer-open` locks page scrolling; the sidebar uses fixed positioning and `100dvh` below 780px.
- Modal rules at the mobile breakpoint use a full viewport dialog and safe-area spacing.
- API regression suite: 6/6 passes (see `TEST_REPORT.md`).

## Browser matrix

| Viewport | Result | Evidence |
|---|---|---|
| 360, 375, 390, 430px | Pending manual browser test | Browser automation unavailable |
| 768, 1024px | Pending manual browser test | Browser automation unavailable |
| 1366, 1440, 1920px | Pending manual browser test | Browser automation unavailable |

## Manual acceptance checklist

1. At ≤780px, press the menu button; confirm the overlay appears and body content cannot scroll.
2. Close it by tapping the overlay, X, menu button, Escape, and a navigation item.
3. Resize from mobile to desktop with the drawer open; confirm overlay/drawer state resets.
4. Open login/customer/appointment/modal flows at 360px; confirm close control and submit buttons remain reachable.
5. Horizontally scroll wide tables inside their card; confirm the page itself does not scroll sideways.
