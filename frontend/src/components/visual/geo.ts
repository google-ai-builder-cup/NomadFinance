// Coarse Asia-Pacific land outlines, enough to read as a dotted map. Not survey data: they only
// decide where decorative dots go, so they stay deliberately rough and tiny in the bundle.
type LonLat = readonly [number, number];

const LAND: readonly (readonly LonLat[])[] = [
  [
    [68, 24],
    [72, 21],
    [73, 16],
    [77, 8],
    [80, 13],
    [80, 16],
    [87, 21],
    [92, 22],
    [94, 17],
    [98, 16],
    [98, 8],
    [101, 3],
    [104, 1.3],
    [103, 10],
    [105, 9],
    [107, 11],
    [109, 13],
    [109, 21],
    [114, 22],
    [120, 28],
    [122, 31],
    [121, 37],
    [118, 39],
    [122, 40],
    [125, 40],
    [129, 35],
    [129, 38],
    [130, 43],
    [135, 43],
    [131, 48],
    [120, 53],
    [110, 53],
    [90, 50],
    [75, 43],
    [68, 38],
    [62, 30],
  ],
  [
    [44, 38],
    [48, 30],
    [56, 27],
    [62, 26],
    [62, 30],
    [68, 38],
    [60, 42],
    [50, 40],
  ],
  [
    [35, 28],
    [43, 13],
    [52, 16],
    [59, 22],
    [56, 26],
    [50, 30],
    [40, 32],
  ],
  [
    [130.5, 31],
    [132, 33.5],
    [135, 34],
    [139, 35],
    [141, 38],
    [142, 41.5],
    [140, 41],
    [139.5, 38],
    [136.5, 36.5],
    [133, 35.5],
    [131, 34],
    [130, 33],
  ],
  [
    [140, 42],
    [142, 43],
    [145, 43.5],
    [142, 45.5],
    [141, 45],
  ],
  [
    [120, 18],
    [122, 18.3],
    [122, 14],
    [124, 13],
    [120.5, 14],
  ],
  [
    [122, 8],
    [126, 9.5],
    [126, 6.5],
    [124, 6.3],
  ],
  [
    [122, 11],
    [125, 11],
    [125, 10],
    [123, 10],
  ],
  [
    [95, 5.5],
    [98, 4],
    [104, -2],
    [106, -6],
    [102, -4],
    [97, 0],
  ],
  [
    [105.5, -6],
    [114, -7],
    [114, -8.5],
    [106, -7.5],
  ],
  [
    [109, 1.5],
    [113, 3],
    [117, 7],
    [119, 5],
    [116, -3.5],
    [110, -3],
  ],
  [
    [119.5, -1],
    [121, 1.2],
    [125, 1.5],
    [123, -1],
    [122.5, -4.5],
    [120, -5.5],
    [119.3, -3],
  ],
  [
    [131, -1],
    [141, -3],
    [150, -10],
    [142, -9],
    [135, -4],
  ],
  [
    [120, 22],
    [121.8, 25],
    [122, 24],
    [121, 22],
  ],
  [
    [114, -22],
    [114, -34],
    [118, -35],
    [124, -33],
    [131, -31.5],
    [138, -35.5],
    [141, -38],
    [147, -39],
    [150, -37],
    [153, -30],
    [153, -25],
    [146, -19],
    [142, -11],
    [141, -17],
    [136, -12],
    [130, -12],
    [126, -14],
    [122, -18],
  ],
];

function inside(lon: number, lat: number, poly: readonly LonLat[]): boolean {
  let hit = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) {
      hit = !hit;
    }
  }
  return hit;
}

export function isLand(lon: number, lat: number): boolean {
  return LAND.some((poly) => inside(lon, lat, poly));
}

/** The six corridor cities (the sending and receiving ends of the six corridors in scope). */
export const CITIES = {
  SG: [103.8, 1.35],
  MY: [101.7, 3.1],
  JP: [139.7, 35.7],
  AU: [151.2, -33.9],
  PH: [121, 14.6],
  IN: [72.9, 19.1],
  ID: [106.8, -6.2],
} as const satisfies Record<string, LonLat>;
export type CityCode = keyof typeof CITIES;

/** The six corridors as sending → receiving city codes. */
export const ARC_CORRIDORS: readonly (readonly [CityCode, CityCode])[] = [
  ["SG", "PH"],
  ["SG", "IN"],
  ["AU", "IN"],
  ["MY", "ID"],
  ["JP", "PH"],
  ["AU", "PH"],
];

const rad = (deg: number) => (deg * Math.PI) / 180;

export interface Projected {
  x: number;
  y: number;
  /** Depth towards the viewer, 1 at the centre of the disc and below 0 on the far side. */
  depth: number;
}

/** Orthographic projection of a point on a unit sphere centred on (lon0, lat0). */
export function project(lon: number, lat: number, lon0: number, lat0: number): Projected {
  const dl = rad(lon - lon0);
  const phi = rad(lat);
  const phi0 = rad(lat0);
  return {
    x: Math.cos(phi) * Math.sin(dl),
    y: Math.cos(phi0) * Math.sin(phi) - Math.sin(phi0) * Math.cos(phi) * Math.cos(dl),
    depth: Math.sin(phi0) * Math.sin(phi) + Math.cos(phi0) * Math.cos(phi) * Math.cos(dl),
  };
}

/** Land points on a roughly even grid: the dots both the SVG poster and the canvas globe draw. */
export const LAND_DOTS: readonly LonLat[] = (() => {
  const dots: LonLat[] = [];
  for (let lat = -50; lat <= 70; lat += 2.2) {
    const step = 2.2 / Math.max(0.35, Math.cos(rad(lat)));
    for (let lon = 10; lon <= 200; lon += step) {
      if (isLand(lon, lat)) {
        dots.push([lon, lat]);
      }
    }
  }
  return dots;
})();

export interface GlobeShape {
  /** One path of zero-length segments; round caps turn them into dots. */
  dots: string;
  graticule: string;
  cities: { code: CityCode; x: number; y: number; receiving: boolean }[];
  arcs: { d: string; code: string }[];
}

const RECEIVING: readonly CityCode[] = ["PH", "IN", "ID"];
const f = (n: number) => n.toFixed(1);

/** The static globe the poster draws, in a 520x520 box (sphere radius 215, centre 260,262). */
export function buildGlobeShape(): GlobeShape {
  const R = 215;
  const cx = 260;
  const cy = 262;
  const lon0 = 108;
  const lat0 = 14;
  const at = (lon: number, lat: number) => {
    const p = project(lon, lat, lon0, lat0);
    return { x: cx + p.x * R, y: cy - p.y * R, visible: p.depth > 0.02 };
  };

  let dots = "";
  for (const [lon, lat] of LAND_DOTS) {
    const p = at(lon, lat);
    if (p.visible) {
      dots += `M${f(p.x)} ${f(p.y)}h0`;
    }
  }

  let graticule = "";
  const line = (points: LonLat[]) => {
    let pen = false;
    for (const [lon, lat] of points) {
      const p = at(lon, lat);
      if (p.visible) {
        graticule += `${pen ? "L" : "M"}${f(p.x)} ${f(p.y)}`;
        pen = true;
      } else {
        pen = false;
      }
    }
  };
  for (let lon = -20; lon <= 220; lon += 20) {
    const pts: LonLat[] = [];
    for (let lat = -80; lat <= 80; lat += 4) pts.push([lon, lat]);
    line(pts);
  }
  for (let lat = -60; lat <= 80; lat += 20) {
    const pts: LonLat[] = [];
    for (let lon = -40; lon <= 260; lon += 4) pts.push([lon, lat]);
    line(pts);
  }

  const cities = (Object.keys(CITIES) as CityCode[]).map((code) => {
    const [lon, lat] = CITIES[code];
    const p = at(lon, lat);
    return { code, x: p.x, y: p.y, receiving: RECEIVING.includes(code) };
  });
  const place = (code: CityCode) => cities.find((c) => c.code === code) as (typeof cities)[number];

  const arcs = ARC_CORRIDORS.map(([from, to]) => {
    const a = place(from);
    const b = place(to);
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const dist = Math.hypot(a.x - b.x, a.y - b.y);
    let dx = mx - cx;
    let dy = my - cy;
    const len = Math.hypot(dx, dy) || 1;
    dx /= len;
    dy /= len;
    const lift = 22 + dist * 0.28;
    return {
      code: `${from}-${to}`,
      d: `M${f(a.x)},${f(a.y)} Q${f(mx + dx * lift)},${f(my + dy * lift - 8)} ${f(b.x)},${f(b.y)}`,
    };
  });

  return { dots, graticule, cities, arcs };
}

/** Dots for a flat equirectangular map of the region, for AnimatedBackground and the radar map. */
export function buildFlatMapDots(
  width: number,
  height: number,
  bounds: { lon0: number; lon1: number; lat0: number; lat1: number },
  step: number
): string {
  let d = "";
  for (let lat = bounds.lat1; lat <= bounds.lat0; lat += step) {
    for (let lon = bounds.lon0; lon <= bounds.lon1; lon += step) {
      if (isLand(lon, lat)) {
        const x = ((lon - bounds.lon0) / (bounds.lon1 - bounds.lon0)) * width;
        const y = ((bounds.lat0 - lat) / (bounds.lat0 - bounds.lat1)) * height;
        d += `M${x.toFixed(0)} ${y.toFixed(0)}h0`;
      }
    }
  }
  return d;
}

export function flatPoint(
  lon: number,
  lat: number,
  width: number,
  height: number,
  bounds: { lon0: number; lon1: number; lat0: number; lat1: number }
): { x: number; y: number } {
  return {
    x: ((lon - bounds.lon0) / (bounds.lon1 - bounds.lon0)) * width,
    y: ((bounds.lat0 - lat) / (bounds.lat0 - bounds.lat1)) * height,
  };
}
