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

export interface ModuleItem extends PillarItem {
  /** The module is in the navigation only while this flag is on for the signed-in user. */
  flag: FeatureFlag;
}

// The two Future Scope pillars. Kept apart from PILLAR_ITEMS: the navigation and the signed-in
// dashboard show a module only while its flag is on for the worker (NF-F0-006), and the page
// headers and analytics still know four pillars. The landing page shows all six, below.
export const MODULE_ITEMS: readonly ModuleItem[] = [
  {
    to: "/coach",
    pillar: "coach",
    icon: GraduationCap,
    labelKey: "nav.coach",
    nameKey: "pillars.coach.name",
    descriptionKey: "pillars.coach.description",
    flag: "coach",
  },
  {
    to: "/scam-check",
    pillar: "scam",
    icon: ScanSearch,
    labelKey: "nav.scamCheck",
    nameKey: "pillars.scam.name",
    descriptionKey: "pillars.scam.description",
    flag: "scam",
  },
];

/** All six pillars, for the landing page: it is marketing, shown signed out to everyone. */
export const ALL_PILLAR_ITEMS: readonly PillarItem[] = [...PILLAR_ITEMS, ...MODULE_ITEMS];

/** The pillars a signed-in worker has: the four, then each module that is on for them. */
export function visiblePillarItems(flags: FeatureFlags): readonly PillarItem[] {
  return [...PILLAR_ITEMS, ...MODULE_ITEMS.filter(({ flag }) => flags[flag])];
}

/** The sidebar and tab bar entries for this user: the v1.0 five, then each module that is on. */
export function visibleNavItems(flags: FeatureFlags): readonly NavItem[] {
  return [...NAV_ITEMS, ...MODULE_ITEMS.filter(({ flag }) => flags[flag])];
}

/** The pillar a path belongs to (`/radar/entity/x` is Radar), or null outside the four pillars. */
export function pillarForPath(pathname: string): PillarItem | null {
  return PILLAR_ITEMS.find(({ to }) => pathname === to || pathname.startsWith(`${to}/`)) ?? null;
}
