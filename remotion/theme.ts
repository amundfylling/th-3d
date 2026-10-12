// Visual theme of the analysis videos (remotion/AnalysisVideo.tsx): overlay colours, typography, panels and branding.
// Presentation only: a theme never touches the trace, the camera track, the rink or the figures.
//
//   nbhf    - Norges Bordhockeyforbund (puck.no), the default. Palette and fonts from the site's own source
//             (github.com/amundfylling/puck.no, src/styles/global.css @theme, commit 7ac88cab, 2026-10-05): brand red
//             #c8102e, navy #0e2a57, ice #f4f7fb, Bricolage Grotesque (display) + Geist (body). The NBHF shield is
//             public/media/images/nbhf-logo.png of the same commit (public/brand/nbhf-logo.png). Following the site's design
//             rules: light panels, navy type, ONE accent (brand red), thin dividers, status as a small dot + text,
//             solid panels instead of gradients over the picture.
//   classic - the original dark broadcast look (Barlow, amber/cyan on dark panels), kept for comparison.
import type { CSSProperties } from "react";

export type AccentName = "amber" | "cyan" | "red" | "green";

export interface Theme {
  id: "nbhf" | "classic";
  /** graphic accents by role: amber = primary, cyan = secondary, red = blocked/danger, green = open/success */
  accent: Record<AccentName, string>;
  /** text on panels */
  ink: string;
  /** secondary text on panels */
  inkSoft: string;
  /** text on an accent block */
  onAccent: string;
  /** label/caption panel */
  panel: string;
  /** strong panel (goal banner, bug title) and its text */
  panelStrong: string;
  inkStrong: string;
  /** dark outline under arrows and trails so they read on the white ice */
  outline: string;
  /** ghost puck fill (lanes) */
  ghost: string;
  /** behind the 3D canvas */
  background: string;
  /** corner radius of panels (px) */
  radius: number;
  shadow: string;
  /** display (titles, tags) and body fonts */
  display: string;
  body: string;
  /** weights: heavy = titles, label = tags/bug/badge */
  heavy: number;
  label: number;
  /** uppercase tracking of labels (px at 30 px) */
  tracking: number;
  /** extra style for display text (e.g. narrower width axis) */
  displayStyle: CSSProperties;
  /** title card backdrop (left side) */
  titleBackdrop: string;
  /** brand mark shown on the bug, title and end cards (static file path), null = none */
  logo: string | null;
  /** short organisation name next to the logo */
  orgShort: string | null;
  orgName: string | null;
  fonts: { family: string; file: string; weight: string; stretch?: string }[];
  /** minimal text (user, 2026-10-12): no kicker (e.g. "SHOT ENCYCLOPEDIA") anywhere, nothing under the name on the title card */
  minimal: boolean;
}

const NAVY = "#0e2a57";
const BRAND = "#c8102e";

export const THEMES: Record<Theme["id"], Theme> = {
  nbhf: {
    id: "nbhf",
    accent: { amber: BRAND, cyan: "#1f5fbf", red: "#d1495b", green: "#16a34a" },
    ink: NAVY,
    inkSoft: "#334155",
    onAccent: "#ffffff",
    panel: "rgba(255, 255, 255, 0.95)",
    panelStrong: NAVY,
    inkStrong: "#ffffff",
    outline: "rgba(10, 31, 66, 0.55)",
    ghost: NAVY,
    background: `radial-gradient(ellipse at 50% 40%, #1b3a6e 0%, #0a1f42 75%)`,
    radius: 6,
    shadow: "0 8px 24px rgba(10, 31, 66, 0.28)",
    display: "'Bricolage Grotesque', 'DejaVu Sans', sans-serif",
    body: "'Geist', 'DejaVu Sans', sans-serif",
    heavy: 800,
    label: 700,
    tracking: 0.5,
    displayStyle: { fontStretch: "88%", letterSpacing: "-0.01em" },
    titleBackdrop: `rgba(244, 247, 251, 0.96)`,
    logo: "brand/nbhf-logo.png",
    orgShort: "NBHF",
    orgName: "Norges Bordhockeyforbund",
    minimal: true,
    fonts: [
      { family: "Bricolage Grotesque", file: "BricolageGrotesque-Variable-latin.woff2", weight: "200 800", stretch: "75% 100%" },
      { family: "Geist", file: "Geist-Variable-latin.woff2", weight: "100 900" },
    ],
  },
  classic: {
    id: "classic",
    accent: { amber: "#FFB21E", cyan: "#2FD6FF", red: "#FF4D4D", green: "#3BE07A" },
    ink: "#F4F6FA",
    inkSoft: "#F4F6FA",
    onAccent: "#0A0F18",
    panel: "rgba(9, 14, 24, 0.84)",
    panelStrong: "rgba(255,255,255,0.92)",
    inkStrong: "#0A0F18",
    outline: "rgba(0,0,0,0.45)",
    ghost: "#10141c",
    background: "radial-gradient(ellipse at 50% 40%, #3a4250 0%, #161b24 75%)",
    radius: 0,
    shadow: "0 10px 30px rgba(0,0,0,0.35)",
    display: "'Barlow Condensed', 'DejaVu Sans', sans-serif",
    body: "'Barlow', 'DejaVu Sans', sans-serif",
    heavy: 800,
    label: 600,
    tracking: 1.5,
    displayStyle: {},
    titleBackdrop: "linear-gradient(90deg, rgba(8,12,20,0.78) 0%, rgba(8,12,20,0.55) 55%, rgba(8,12,20,0) 100%)",
    logo: null,
    orgShort: null,
    orgName: null,
    minimal: false,
    fonts: [
      { family: "Barlow Condensed", file: "BarlowCondensed-ExtraBold.ttf", weight: "800" },
      { family: "Barlow Condensed", file: "BarlowCondensed-SemiBold.ttf", weight: "600" },
      { family: "Barlow", file: "Barlow-SemiBold.ttf", weight: "600" },
      { family: "Barlow", file: "Barlow-Medium.ttf", weight: "500" },
    ],
  },
};

export const DEFAULT_THEME: Theme["id"] = "nbhf";
