import { CORRIDOR_IDS, type CorridorId } from "@/types/enums";
import type { UserProfile } from "@/types/user";

/**
 * The routes whose alerts the worker sees on the Alerts page. The same rule the alert job
 * notifies by (backend `notify._subscribed_profiles`, users.md): the routes chosen in the
 * profile, else their own host → home route. A worker whose home country has no surveyed
 * route (Nepal, Bangladesh) gets every route from their host country instead of nothing:
 * reports about employers there count on each of those routes.
 */
export function alertRoutes(profile: UserProfile | null | undefined): CorridorId[] {
  const chosen = profile?.notification_prefs?.radar_corridors ?? [];
  const valid = CORRIDOR_IDS.filter((id) => chosen.includes(id));
  if (valid.length > 0) {
    return valid;
  }
  const own = `${profile?.host_country ?? ""}-${profile?.home_country ?? ""}`;
  const ownRoute = CORRIDOR_IDS.find((id) => id === own);
  if (ownRoute) {
    return [ownRoute];
  }
  return CORRIDOR_IDS.filter((id) => id.startsWith(`${profile?.host_country ?? "-"}-`));
}
