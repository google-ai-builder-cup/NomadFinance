import type { CSSProperties, ReactNode } from "react";

import type { FaceFills, Iso } from "@/components/visual/iso";

const join = (points: [number, number][]) => points.map(([x, y]) => `${x},${y}`).join(" ");

export function Box({
  iso,
  x,
  y,
  z,
  w,
  d,
  h,
  fills,
  className,
  style,
}: {
  iso: Iso;
  x: number;
  y: number;
  z: number;
  w: number;
  d: number;
  h: number;
  fills: FaceFills;
  className?: string;
  style?: CSSProperties;
}) {
  const p = iso.pt;
  return (
    <g className={className} style={style}>
      <polygon
        fill={fills.left}
        points={join([
          p(x, y + d, z),
          p(x + w, y + d, z),
          p(x + w, y + d, z + h),
          p(x, y + d, z + h),
        ])}
      />
      <polygon
        fill={fills.right}
        points={join([
          p(x + w, y, z),
          p(x + w, y + d, z),
          p(x + w, y + d, z + h),
          p(x + w, y, z + h),
        ])}
      />
      <polygon
        fill={fills.top}
        points={join([
          p(x, y, z + h),
          p(x + w, y, z + h),
          p(x + w, y + d, z + h),
          p(x, y + d, z + h),
        ])}
      />
    </g>
  );
}

/** A cylinder standing at grid point (cx, cy): `side` paints the wall, `top` the lid. */
export function Disc({
  iso,
  cx,
  cy,
  z,
  r,
  h,
  side,
  top,
}: {
  iso: Iso;
  cx: number;
  cy: number;
  z: number;
  r: number;
  h: number;
  side: string;
  top: string;
}) {
  const [x, y] = iso.pt(cx, cy, z);
  const rx = 1.2247 * iso.u * r;
  const ry = 0.7071 * iso.u * r;
  const hh = h * iso.u;
  return (
    <g>
      <path
        fill={side}
        d={`M${x - rx},${y - hh} L${x - rx},${y} A${rx},${ry} 0 0 0 ${x + rx},${y} L${x + rx},${y - hh} Z`}
      />
      <ellipse fill={top} cx={x} cy={y - hh} rx={rx} ry={ry} />
    </g>
  );
}

export function IllustrationFrame({ label, children }: { label: string; children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 240 200"
      role="img"
      aria-label={label}
      className="block h-auto w-full overflow-visible"
    >
      {children}
    </svg>
  );
}
