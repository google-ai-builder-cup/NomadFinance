import { CORRIDOR_IDS, type CorridorId, type HomeCountry, type HostCountry } from "@/types/enums";
import type { EntityType, RadarEntityProfile } from "@/types/radar";

export type LatLng = readonly [number, number];

// Rough centres of the eleven countries in scope. The data has corridors and countries but no
// addresses, so this is as precise as the map can honestly be.
export const COUNTRY_COORDS: Readonly<Record<HostCountry | HomeCountry, LatLng>> = {
  SG: [1.35, 103.82],
  KR: [36.5, 127.8],
  MY: [4.21, 101.98],
  JP: [36.2, 138.25],
  HK: [22.32, 114.17],
  AU: [-25.27, 133.77],
  PH: [12.88, 121.77],
  IN: [20.59, 78.96],
  ID: [-0.79, 113.92],
  NP: [28.39, 84.12],
  BD: [23.68, 90.36],
};

export const MAP_CENTER: LatLng = [12, 108];

/** 0 = no reports; 1 to 3 = share of the busiest corridor (a third each). */
export type HeatLevel = 0 | 1 | 2 | 3;

export interface CorridorHeat {
  id: CorridorId;
  from: LatLng;
  to: LatLng;
  reportCount: number;
  entityCount: number;
  level: HeatLevel;
}

/**
 * Totals per corridor. An entity's `report_count` is not split by corridor, so a business
 * seen on two corridors counts in full on both; fine while most businesses work one route.
 */
export function corridorHeat(entities: readonly RadarEntityProfile[]): CorridorHeat[] {
  const totals = CORRIDOR_IDS.map((id) => {
    const here = entities.filter((entity) => entity.corridors?.includes(id));
    return {
      id,
      reportCount: here.reduce((sum, entity) => sum + entity.report_count, 0),
      entityCount: here.length,
    };
  });
  const busiest = Math.max(0, ...totals.map((corridor) => corridor.reportCount));
  return totals.map(({ id, reportCount, entityCount }) => {
    const [host, home] = id.split("-") as [HostCountry, HomeCountry];
    return {
      id,
      from: COUNTRY_COORDS[host],
      to: COUNTRY_COORDS[home],
      reportCount,
      entityCount,
      level:
        reportCount === 0 ? 0 : (Math.min(3, Math.ceil((reportCount / busiest) * 3)) as HeatLevel),
    };
  });
}

/**
 * The businesses reported on one route, most reports first (ties by name). The same list the
 * route's report total in `corridorHeat` adds up, so the numbers on screen agree.
 */
export function entitiesOnCorridor(
  entities: readonly RadarEntityProfile[],
  corridorId: CorridorId
): RadarEntityProfile[] {
  return entities
    .filter((entity) => entity.corridors?.includes(corridorId))
    .sort((a, b) => b.report_count - a.report_count || a.name.localeCompare(b.name));
}

/** Line colour and width per level, shared by the map and its legend. */
export const HEAT_STYLE: Readonly<Record<HeatLevel, { color: string; weight: number }>> = {
  0: { color: "#94a3b8", weight: 2 },
  1: { color: "#f59e0b", weight: 4 },
  2: { color: "#ea580c", weight: 7 },
  3: { color: "#dc2626", weight: 10 },
};

export const RISK_COLOR: Readonly<Record<RadarEntityProfile["risk_level"], string>> = {
  low: "#f59e0b",
  medium: "#ea580c",
  high: "#dc2626",
};

export type EntityFilter = EntityType | "all";

export function filterEntities(
  entities: readonly RadarEntityProfile[],
  filter: EntityFilter
): RadarEntityProfile[] {
  return filter === "all" ? [...entities] : entities.filter((e) => e.entity_type === filter);
}

export interface EntityMarker {
  entity: RadarEntityProfile;
  position: LatLng;
}

/**
 * One marker per flagged business, on its host country. Businesses of the same country are
 * fanned out in a small fixed spiral so they do not sit exactly on top of each other; the
 * cluster layer then groups them when zoomed out.
 */
export function entityMarkers(entities: readonly RadarEntityProfile[]): EntityMarker[] {
  const seen = new Map<HostCountry, number>();
  return entities
    .filter((entity) => entity.flagged)
    .sort((a, b) => a.slug.localeCompare(b.slug))
    .flatMap((entity) => {
      const host =
        entity.host_countries?.[0] ?? (entity.corridors?.[0]?.split("-")[0] as HostCountry);
      if (!(host in COUNTRY_COORDS)) {
        return [];
      }
      const index = seen.get(host) ?? 0;
      seen.set(host, index + 1);
      const angle = index * 2.4;
      const radius = index === 0 ? 0 : 0.5 + 0.25 * index;
      const [lat, lng] = COUNTRY_COORDS[host];
      return [
        {
          entity,
          position: [lat + radius * Math.sin(angle), lng + radius * Math.cos(angle)] as LatLng,
        },
      ];
    });
}
