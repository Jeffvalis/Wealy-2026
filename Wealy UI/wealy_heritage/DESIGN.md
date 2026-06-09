# Design System Specification: The Digital Private Office

This design system is a comprehensive framework for a premium wealth management experience. It is designed to move beyond the "app" aesthetic into the realm of high-end digital editorial. By prioritizing tonal depth over structural lines, it creates a secure, sophisticated environment that reflects the exclusivity of private banking.

---

## 1. Overview & Creative North Star

### Creative North Star: "The Digital Private Office"
This system follows the philosophy of **Quiet Luxury**. Much like a physical private office in Mayfair or Manhattan, the interface relies on premium materials (gradients and glass), silence (whitespace), and craftsmanship (typography) rather than loud decorative elements.

**Breaking the Template:**
To avoid a "generic fintech" look, this system utilizes **Intentional Asymmetry**. We favor large-scale `display-lg` typography offset against wide `spacing-24` margins. By avoiding traditional 1px borders and rigid grids, we create a layout that feels curated and fluid, rather than boxed-in.

---

## 2. Color & Tonal Depth

The palette is rooted in a deep, authoritative foundation, accented by "Metals" (Gold) and "Botanicals" (Emerald).

### The "No-Line" Rule
**Explicit Instruction:** Do not use 1px solid borders to section content. Boundaries must be defined solely through background color shifts. Use `surface-container-low` for secondary sections sitting on a `surface` background. If you feel the need for a line, increase your `spacing` scale instead.

### Surface Hierarchy & Nesting
Treat the UI as a series of stacked, fine-paper sheets. 
- **Base Layer:** `surface` (#f8f9fa)
- **Secondary Sectioning:** `surface-container-low` (#f3f4f5)
- **Primary Interaction Cards:** `surface-container-lowest` (#ffffff)
- **High-Emphasis Overlays:** `surface-bright` (#f8f9fa)

### The "Glass & Gradient" Rule
To achieve a signature feel, use Glassmorphism for floating navigation or header elements.
- **Glass Effect:** Apply `surface-container-lowest` at 80% opacity with a `backdrop-filter: blur(20px)`.
- **Signature Textures:** Use a subtle linear gradient for primary CTAs: `primary` (#000000) to `primary-container` (#101b30) at a 135-degree angle. This prevents buttons from looking "flat" and adds a polished, metallic depth.

---

## 3. Typography

The typographic system is a dialogue between the authority of a Serif and the precision of a Sans-Serif.

- **The Editorial Voice (Noto Serif):** Used for `display` and `headline` scales. This conveys heritage and trustworthiness. Use `display-lg` (3.5rem) for portfolio totals and high-level welcomes to create a "magazine" feel.
- **The Functional Voice (Inter):** Used for `title`, `body`, and `label` scales. Inter provides the technical clarity required for complex financial data.
- **Visual Hierarchy:** Maintain a high contrast between headings and body text. A `headline-lg` should feel significantly more "weighty" than the `body-lg` beneath it to guide the eye through the wealth narrative.

---

## 4. Elevation & Depth

We reject the "drop shadow" of the early web. Elevation in this system is achieved through **Tonal Layering**.

- **The Layering Principle:** Place a `surface-container-lowest` card on top of a `surface-container-low` background. The subtle shift from #ffffff to #f3f4f5 creates a natural "lift" without the need for heavy shadows.
- **Ambient Shadows:** For floating modals, use a "Low-Visibility Shadow": `y: 20px, blur: 40px, color: rgba(25, 28, 29, 0.04)`. The shadow must feel like ambient light hitting a surface, never like a dark glow.
- **The Ghost Border Fallback:** If a border is required for accessibility in data tables, use the `outline-variant` token at **15% opacity**. Total opacity borders are strictly forbidden.
- **Glassmorphism:** Use semi-transparent `surface-variant` layers over gradients to create "frosted" information panels that feel integrated into the background environment.

---

## 5. Components

### Buttons
- **Primary:** High-contrast `primary` to `primary-container` gradient. Text is `on-primary`. Shape is `xl` (0.75rem/12px) roundedness.
- **Secondary:** Transparent background with a `Ghost Border` (`outline-variant` @ 20%).
- **Tertiary:** Pure text using `label-md`, adding a subtle underline on hover for affordance.

### Cards & Data Lists
- **Rule:** Forbid the use of divider lines.
- **Execution:** Use `spacing-4` (1.4rem) of vertical whitespace to separate list items. Use a `surface-container-low` background on hover to indicate interactivity.
- **Wealth Metric Cards:** Use `surface-container-lowest` with an `xl` corner radius. Place the metric in `display-sm` (Noto Serif) to emphasize the value of the assets.

### Input Fields
- **Styling:** Minimalist. No bottom line or box. Use a `surface-container-high` background with `spacing-3` internal padding. 
- **States:** On focus, the background shifts to `surface-container-highest` with a 1px `secondary` (Gold) ghost-border to signify the "Premium" interaction.

### Context-Specific Components
- **The "Portfolio Ribbon":** A horizontally scrolling list of assets using glassmorphism, allowing the primary brand gradient to peek through from the background.
- **The "Growth Path" Sparkline:** Use `tertiary-fixed` (Emerald) for positive trends, rendered with a 2px stroke and a soft glow effect, avoiding sharp jagged edges for a smoother "premium" feel.

---

## 6. Do's and Don'ts

### Do
- **Do** use `spacing-16` and `spacing-20` for page margins to create "breathe-room" that signals luxury.
- **Do** mix Noto Serif and Inter within the same component (e.g., a Serif title with a Sans-Serif subtitle).
- **Do** use `secondary` (Gold) and `tertiary` (Emerald) sparingly as "jewel" accents—never as background colors.

### Don't
- **Don't** use 100% black (#000000) for body text; use `on-surface-variant` (#44474c) to reduce eye strain and maintain a soft aesthetic.
- **Don't** use `DEFAULT` or `sm` roundedness. Wealth is "soft"; stick to `lg` (8px) and `xl` (12px).
- **Don't** use standard "Success Green." Only use the `tertiary` emerald tones defined in the palette to maintain the sophisticated brand identity.