/** Isometric projection helpers for the pillar illustrations: a unit cube maps to a hexagon,
 * so boxes are drawn as three faces (top, left, right) shaded from one accent. */
export interface Iso {
  u: number;
  ox: number;
  oy: number;
  /** Screen point of grid point (x, y) at height z. */
  pt: (x: number, y: number, z: number) => [number, number];
  /** SVG `transform` that lays a flat drawing onto the ground plane at height z. */
  plane: (z: number) => string;
}

export function makeIso(u: number, ox: number, oy: number): Iso {
  const c = 0.866 * u;
  const s = 0.5 * u;
  return {
    u,
    ox,
    oy,
    pt: (x, y, z) => [ox + (x - y) * c, oy + (x + y) * s - z * u],
    plane: (z) => `matrix(${c} ${s} ${-c} ${s} ${ox} ${oy - z * u})`,
  };
}

export interface FaceFills {
  top: string;
  left: string;
  right: string;
}
