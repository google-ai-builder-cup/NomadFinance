import {
  ArrowLeftRight,
  Fingerprint,
  GraduationCap,
  LayoutDashboard,
  Radar,
  ScanSearch,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { FeatureFlag, FeatureFlags } from "@/types/flags";
import type { PillarKey } from "@/utils/pillars";

export interface NavItem {
  to: string;
  icon: LucideIcon;
  /** Short label for the sidebar and the phone tab bar. */
  labelKey: string;
}

export interface PillarItem extends NavItem {
  /** Which accent colour the pillar wears everywhere (see utils/pillars.ts). */
  pillar: PillarKey;
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
    pillar: "remit",
    icon: ArrowLeftRight,
    labelKey: "nav.remittance",
    nameKey: "pillars.remittance.name",
    descriptionKey: "pillars.remittance.description",
  },
  {
    to: "/contract",
    pillar: "contract",
    icon: ShieldCheck,
    labelKey: "nav.contract",
    nameKey: "pillars.contract.name",
    descriptionKey: "pillars.contract.description",
  },
  {
    to: "/radar",
    pillar: "radar",
    icon: Radar,
    labelKey: "nav.radar",
    nameKey: "pillars.radar.name",
    descriptionKey: "pillars.radar.description",
  },
  {
    to: "/identity",
    pillar: "identity",
    icon: Fingerprint,
    labelKey: "nav.identity",
    nameKey: "pillars.identity.name",
    descriptionKey: "pillars.identity.description",
  },
];

export const NAV_ITEMS: readonly NavItem[] = [HOME_ITEM, ...PILLAR_ITEMS];

export interface ModuleItem extends NavItem {
  /** The module is in the navigation only while this flag is on for the signed-in user. */
  flag: FeatureFlag;
}

// Kept apart from PILLAR_ITEMS on purpose: that list also feeds the landing page, the dashboard
// cards and analytics, which must stay exactly as v1.0 while a module ships dark (NF-F0-006).
export const MODULE_ITEMS: readonly ModuleItem[] = [
  { to: "/coach", icon: GraduationCap, labelKey: "nav.coach", flag: "coach" },
  { to: "/scam-check", icon: ScanSearch, labelKey: "nav.scamCheck", flag: "scam" },
];

/** The sidebar and tab bar entries for this user: the v1.0 five, then each module that is on. */
export function visibleNavItems(flags: FeatureFlags): readonly NavItem[] {
  return [...NAV_ITEMS, ...MODULE_ITEMS.filter(({ flag }) => flags[flag])];
}

/** The pillar a path belongs to (`/radar/entity/x` is Radar), or null outside the four pillars. */
export function pillarForPath(pathname: string): PillarItem | null {
  return PILLAR_ITEMS.find(({ to }) => pathname === to || pathname.startsWith(`${to}/`)) ?? null;
}
