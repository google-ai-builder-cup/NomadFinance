import { ArrowLeftRight, Fingerprint, LayoutDashboard, Radar, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  icon: LucideIcon;
  /** Short label for the sidebar and the phone tab bar. */
  labelKey: string;
}

export interface PillarItem extends NavItem {
  /** Full pillar name and one-line pitch, used on the dashboard cards. */
  nameKey: string;
  descriptionKey: string;
}

export const HOME_ITEM: NavItem = {
  to: "/dashboard",
  icon: LayoutDashboard,
  labelKey: "nav.dashboard",
};

// One list feeds the sidebar, the tab bar, the dashboard cards and the router, so a new
// pillar page only needs its route element swapped in router.tsx.
export const PILLAR_ITEMS: readonly PillarItem[] = [
  {
    to: "/remittance",
    icon: ArrowLeftRight,
    labelKey: "nav.remittance",
    nameKey: "pillars.remittance.name",
    descriptionKey: "pillars.remittance.description",
  },
  {
    to: "/contract",
    icon: ShieldCheck,
    labelKey: "nav.contract",
    nameKey: "pillars.contract.name",
    descriptionKey: "pillars.contract.description",
  },
  {
    to: "/radar",
    icon: Radar,
    labelKey: "nav.radar",
    nameKey: "pillars.radar.name",
    descriptionKey: "pillars.radar.description",
  },
  {
    to: "/identity",
    icon: Fingerprint,
    labelKey: "nav.identity",
    nameKey: "pillars.identity.name",
    descriptionKey: "pillars.identity.description",
  },
];

export const NAV_ITEMS: readonly NavItem[] = [HOME_ITEM, ...PILLAR_ITEMS];
