---
version: alpha
name: Terminal Dark
description: A cold, authoritative dark design system for data-dense dashboard applications. Optimized for professional tools where information density, legibility, and zero decorative chrome are paramount.
colors:
  primary: "#ffffff"
  on-primary: "#000000"
  secondary: "#a0a0a0"
  on-secondary: "#000000"
  tertiary: "#666666"
  on-tertiary: "#ffffff"
  surface: "#000000"
  surface-dim: "#000000"
  surface-bright: "#222222"
  surface-container-lowest: "#000000"
  surface-container-low: "rgba(255,255,255,0.05)"
  surface-container: "rgba(255,255,255,0.07)"
  surface-container-high: "rgba(255,255,255,0.09)"
  surface-container-highest: "rgba(255,255,255,0.12)"
  on-surface: "#ffffff"
  on-surface-variant: "#a0a0a0"
  outline: "#333333"
  outline-variant: "#222222"
  inverse-surface: "#ffffff"
  inverse-on-surface: "#000000"
  accent-positive: "#4ade80"
  on-accent-positive: "#000000"
  accent-negative: "#777777"
  on-accent-negative: "#ffffff"
  border-subtle: "#222222"
  border-strong: "#333333"
  border-hover: "#555555"
  heatmap-strong-positive: "#38a169"
  heatmap-moderate-positive: "#68d391"
  heatmap-slight-positive: "#9ae6b4"
  heatmap-slight-negative: "#fc8181"
  heatmap-moderate-negative: "#e53e3e"
  heatmap-strong-negative: "#9b2c2c"
  error: "#ff6b6b"
  on-error: "#000000"
  background: "#000000"
  on-background: "#ffffff"
typography:
  display-lg:
    fontFamily: Google Sans
    fontSize: 32px
    fontWeight: "400"
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Google Sans
    fontSize: 28px
    fontWeight: "400"
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Google Sans
    fontSize: 20px
    fontWeight: "400"
    lineHeight: 28px
    letterSpacing: -0.01em
  title-md:
    fontFamily: Google Sans
    fontSize: 15px
    fontWeight: "600"
    lineHeight: 20px
    letterSpacing: 0.1em
  body-md:
    fontFamily: Google Sans
    fontSize: 14px
    fontWeight: "400"
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Google Sans
    fontSize: 13px
    fontWeight: "400"
    lineHeight: 18px
    letterSpacing: 0em
  label-md:
    fontFamily: Google Sans
    fontSize: 11px
    fontWeight: "400"
    lineHeight: 16px
    letterSpacing: 0.1em
  label-sm:
    fontFamily: Google Sans
    fontSize: 10px
    fontWeight: "400"
    lineHeight: 14px
    letterSpacing: 0.12em
  data-md:
    fontFamily: Google Sans Code
    fontSize: 14px
    fontWeight: "400"
    lineHeight: 20px
    letterSpacing: 0em
  data-sm:
    fontFamily: Google Sans Code
    fontSize: 12px
    fontWeight: "400"
    lineHeight: 16px
    letterSpacing: 0em
rounded:
  sm: 0px
  md: 6px
  lg: 0px
  full: 9999px
spacing:
  unit: 8px
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  2xl: 32px
  3xl: 40px
  4xl: 48px
  sidebar-width: 240px
  content-max: 1400px
components:
  button-default:
    backgroundColor: transparent
    textColor: "{colors.secondary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: 8px 16px
    height: 32px
  button-default-hover:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
  button-primary:
    backgroundColor: transparent
    textColor: "{colors.primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: 8px 16px
    height: 32px
  button-primary-hover:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
  button-destructive:
    backgroundColor: transparent
    textColor: "{colors.accent-negative}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: 8px 16px
  button-destructive-hover:
    backgroundColor: "{colors.accent-negative}"
    textColor: "{colors.on-primary}"
  button-segmented-active:
    backgroundColor: "{colors.surface-container}"
    textColor: "{colors.primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: 8px 16px
  card-standard:
    backgroundColor: "{colors.surface-container-low}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
  card-standard-hover:
    backgroundColor: "{colors.surface-container}"
  card-create:
    backgroundColor: transparent
    textColor: "{colors.secondary}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
  modal:
    backgroundColor: "rgba(255, 255, 255, 0.04)"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.sm}"
    padding: "{spacing.2xl}"
  slide-panel:
    backgroundColor: "rgba(255, 255, 255, 0.04)"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.sm}"
    padding: "{spacing.xl}"
    width: 560px
  status-bar-loading:
    backgroundColor: "{colors.surface-container-low}"
    textColor: "{colors.secondary}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
  status-bar-success:
    backgroundColor: "{colors.surface-container}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
  status-bar-error:
    backgroundColor: "{colors.surface-container-low}"
    textColor: "{colors.accent-negative}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
  sidebar-item:
    backgroundColor: transparent
    textColor: "{colors.secondary}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: 8px 24px
  sidebar-item-hover:
    backgroundColor: "{colors.surface-container}"
    textColor: "{colors.primary}"
  table-row-hover:
    backgroundColor: "rgba(255, 255, 255, 0.02)"
  table-row-highlighted:
    backgroundColor: "rgba(255, 255, 255, 0.03)"
  category-badge:
    typography: "{typography.label-sm}"
    rounded: "{rounded.md}"
    padding: 2px 8px
  data-pill:
    rounded: "{rounded.md}"
    padding: 4px 12px
---

## Brand & Style

This design system targets **professional tool interfaces** that happen to run in a browser. The aesthetic is "Terminal Authority" — borrowing from Bloomberg Terminal (information density, monochrome data, zero decorative chrome), Dieter Rams / Braun ("less but better"; every element earns its place), and Swiss International Style (grid discipline, asymmetric balance, uppercase micro-labels).

The emotional register is **cold authority**. Users come here to make decisions with data. Warmth, playfulness, or "delight" would undermine trust. Every element must earn its place; when in doubt, remove.

### Core Principles

1. **Data first, chrome never.** No decorative illustrations, no gradient backgrounds on cards, no shadows for elevation.
2. **Sharp geometry.** Interactive elements are rectangular with zero border-radius. The only exceptions are category badges and heatmap pills, which use `{rounded.md}` (6px) for legibility.
3. **Controlled color.** The UI is predominantly dark/monochrome. Green (`{colors.accent-positive}`) is used sparingly for positive states and action signals. Category badges use muted, opacity-controlled color derived from a single hex input.
4. **Density is a feature.** 50+ data points visible without scrolling on a 1080p screen.
5. **Motion is information.** Animations only for state changes (loading, transitions), never for decoration. No number counting, no parallax, no page transitions.

## Colors

The palette is anchored in pure black and transparency-based surfaces. There are no colored backgrounds — only white at varying alpha levels layered on `#000000`. This creates a unified, monochrome depth without the visual noise of colored elevation.

- **Primary ({colors.primary}):** Headlines, active controls, primary actions, positive data values. White is the "loudest" element in the system.
- **Secondary ({colors.secondary}):** Body text, descriptions, inactive navigation. The default text color for non-primary content.
- **Tertiary ({colors.tertiary}):** Micro-labels, timestamps, metadata. The quietest level of text hierarchy.
- **Accent Positive ({colors.accent-positive}):** Green — the only chromatic accent in default views. Used for positive return percentages, active action signals (buy dots), and highlighted badge borders.
- **Accent Negative ({colors.accent-negative}):** A grey that signals inactivity or negative state, deliberately avoiding red to prevent emotional trigger.

The body background uses a nearly-imperceptible radial gradient (`rgba(75,40,150,0.18)` at top-right, `rgba(15,110,140,0.15)` at bottom-left) layered on `#000000`. At these opacities, it reads as atmospheric texture rather than explicit color.

### Category Badge System

Category badges auto-generate a subtle color treatment from a single hex input: `background: hex(12%)`, `text: hex`, `border: hex(30%)`. This ensures even vivid user-chosen colors remain muted within the monochrome environment.

### Heatmap Scale

For data-dense grid views requiring chromatic encoding, a six-step diverging scale is used — ranging from deep green (`#38a169`) through light green (`#9ae6b4`) for positive, and salmon (`#fc8181`) through dark red (`#9b2c2c`) for negative. The palette is muted and earthy. This is the only place a full chromatic range appears.

## Typography

The design system uses a dual-font strategy: **Google Sans** for all UI text and **Google Sans Code** for numeric data, codes, and timestamps.

- **Display/Headline sizes** use light weight (400) with negative letter-spacing (-0.02em to -0.01em) for a clean, editorial look at large sizes.
- **Labels** (`{typography.label-md}`) are the backbone of the UI. They are always uppercase with 0.1em letter-spacing and appear above every control group. This convention eliminates placeholder text, creates consistent vertical rhythm, and makes the interface scannable at a glance.
- **Data typography** uses `{typography.data-md}` and `{typography.data-sm}` for prices, percentages, ranks, tickers, and timestamps — ensuring columnar alignment in tables.

Font weight is deliberately restrained. Weight 400 dominates; 500 and 600 are reserved for emphasis (modal headings, active states). Heavy weights (700) are avoided to maintain the understated terminal aesthetic.

## Layout & Spacing

The layout follows a **sidebar + main content** model, governed by an 8px base grid.

- **Desktop (>1200px):** Fixed 240px sidebar on the left; main content area is fluid with a 1400px max-width, centered. Controls appear in a horizontal row.
- **Tablet (832–1200px):** Sidebar remains; controls reflow to a 2×2 grid.
- **Mobile (<832px):** Sidebar becomes a right-side slide-out drawer (right, not left — optimized for thumb reach on large phones). Hamburger button fixed top-right. Single-column layout with stacked controls.

Spacing tokens scale from 4px (`xs`) to 48px (`4xl`). Internal component padding uses `md` (12px); section-level gaps use `xl` (24px) or `2xl` (32px). Generous negative space between major page sections (40–48px) prevents the dense data tables from feeling claustrophobic.

### Z-Index Stack

The z-index system uses clear separation: base content at 0–1, backdrop at 999, overlays/modals at 1000–1001, mobile navigation at 1050, and the hamburger toggle at 1100.

## Elevation & Depth

Depth in this design system is **not** achieved through shadows or colored elevation. Instead, surfaces are differentiated by white alpha transparency layered on a pure black base.

- **Level 0 (Base):** `#000000` background with subtle atmospheric radial gradients.
- **Level 1 (Surface):** `{colors.surface-container-low}` — sidebar, cards, banners, status bars.
- **Level 2 (Elevated):** `{colors.surface-container}` — hover states, active sidebar items.
- **Level 3 (Interaction):** `{colors.surface-container-high}` — button hover fills.

Borders provide additional edge definition: `{colors.border-subtle}` (subtle), `{colors.border-strong}` (strong), `{colors.border-hover}` (hover). Shadows are used in exactly one place — modals (`0 30px 80px rgba(0,0,0,0.8)`) — combined with `backdrop-filter: blur(16px)` for a glass effect. This is the only "elevation" that breaks the flat surface model.

## Shapes

The shape language is **zero-radius terminal geometry**. All buttons, cards, inputs, sidebar items, table cells, and status bars use `border-radius: 0`. Sharp corners signal "tool" rather than "consumer app."

Two exceptions exist:
- **Category badges** use `{rounded.md}` (6px) to create readable colored label chips within data tables.
- **Heatmap data pills** also use `{rounded.md}` (6px) so the color fill reads as a distinct swatch rather than a table cell background.

## Components

### Action Elements

Buttons are rectangular, uppercase, `{typography.label-md}`, with 0.1em letter-spacing. Default state: transparent background + 1px border. Hover state: inverts to solid white fill with black text. Segmented controls (for mutually exclusive choices like filters and view modes) collapse borders between adjacent buttons using `margin-left: -1px`; the active button gets `z-index: 2` to render its border above neighbors.

### Containers & Surfaces

Cards use `{colors.surface-container-low}` background with a 1px `{colors.border-subtle}` border. No shadows. "Create new" cards use a dashed border to distinguish their function. Modals use glass treatment: `{components.modal.backgroundColor}` background + `backdrop-filter: blur(16px)` + deep shadow. Slide-out panels share the modal glass treatment but anchor to the right edge with `border-left` only.

### Inputs & Interaction

Status bars communicate system state through border color variation: `{colors.border-strong}` for loading, `{colors.primary}` for success, `{colors.accent-negative}` for error. Data table rows use subtle background changes on hover (`{components.table-row-hover.backgroundColor}`) and for highlighted/selected items (`{components.table-row-highlighted.backgroundColor}`). Inline bar charts render as 4px-height CSS elements with no border-radius.

### Typography Application

Uppercase `{typography.label-md}` labels appear above every control group. Navigation items use `{typography.body-sm}`. Numeric data in tables uses `{typography.data-md}` for prices and percentages, ensuring columnar alignment. Action indicators use Unicode symbols (`●`/`○`) that inherit text color and scale with font-size — zero icon library dependencies.

## Do's and Don'ts

- **Don't** use hero illustrations or empty-state graphics — the app must be functional from first load.
- **Don't** use emoji — replaced with Unicode geometric symbols (`+`, `✕`, `✎`, `●`, `○`, `←`, `✓`, `↻`).
- **Don't** use decorative icons next to labels — uppercase letter-spaced labels provide sufficient hierarchy.
- **Don't** use rounded corners on buttons, cards, or interactive elements (category badges and heatmap pills are the sole exception).
