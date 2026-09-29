# Design System & UI/UX Principles

## 1. Visual Identity
The visual identity of HealthTechWebsite is rooted in **trust, cleanliness, and modernity**. We utilize a hybrid aesthetic combining "Glassmorphism" (frosted glass overlays) and "Claymorphism" (soft, inflated 3D elements) to create a tactile, premium, and friendly environment that actively reduces patient anxiety.

## 2. Color Palette
- **Primary (Trust Blue):** `#0ea5e9` - Used for primary actions, active states, and brand identity.
- **Secondary (Health Accent):** `#10b981` - Used for success states, confirmed appointments, and positive reinforcement.
- **Background (Soft Pearl):** `#f8fafc` or soft gradients - A warm, off-white background to prevent eye strain.
- **Surface (Frosted Glass):** `rgba(255, 255, 255, 0.6)` with `backdrop-filter: blur(12px)` for overlapping containers and modals.
- **Danger/Alert:** `#ef4444` - Used sparingly for destructive actions (e.g., cancelling appointments, deleting slots).

## 3. Typography
- **Primary Font:** `Inter` or `Outfit` (Sans-serif) for high legibility on digital screens.
- **Scale:** 
  - H1/Hero: 2.5rem to 3rem, Extra Bold.
  - Headings: 1.5rem, Bold.
  - Body: 1rem, Medium (Color: `#475569`).
  - Muted/Helper: 0.85rem, Regular (Color: `#94a3b8`).

## 4. UI/UX Principles
- **Micro-interactions:** Elements should feel alive. Apply subtle levitation (`transform: translateY(-2px)`) and responsive box-shadows on hover for interactive elements like cards and buttons.
- **Whitespace:** Prioritize breathing room. Health applications can feel overwhelming; generous padding (e.g., `24px` to `32px` on main cards, `15px` on slots) is mandatory.
- **Accessibility:** Ensure a minimum contrast ratio of 4.5:1 for all text elements. Interactive targets (buttons, links) must have a minimum touch size of `44x44px` on mobile screens.
- **Modals over Popups:** Keep users in context by using beautifully styled frosted-glass modals for secondary actions (e.g., viewing a calendar, setting capacities) rather than navigating to entirely new pages.
