export function Glow({
  id,
  color,
  cy,
  rx,
  ry,
}: {
  id: string;
  color: string;
  cy: number;
  rx: number;
  ry: number;
}) {
  return (
    <>
      <defs>
        <radialGradient id={id} cx=".5" cy=".5" r=".5">
          <stop offset="0" stopColor={color} />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx="120" cy={cy} rx={rx} ry={ry} fill={`url(#${id})`} />
    </>
  );
}
