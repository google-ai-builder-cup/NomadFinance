import "leaflet/dist/leaflet.css";

import L from "leaflet";
import {
  CircleMarker,
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
} from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";

import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import type { RadarEntityProfile, ViolationType } from "@/types/radar";
import { countryName } from "@/utils/format";
import {
  type CorridorHeat,
  type EntityMarker,
  HEAT_STYLE,
  MAP_CENTER,
  RISK_COLOR,
} from "@/utils/radarMap";

export interface HeatmapMapProps {
  corridors: readonly CorridorHeat[];
  markers: readonly EntityMarker[];
}

// A coloured dot instead of Leaflet's default pin: the pin's image paths break under a bundler.
function markerIcon(risk: RadarEntityProfile["risk_level"]): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<span style="display:block;width:18px;height:18px;border-radius:9999px;background:${RISK_COLOR[risk]};border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.4)"></span>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

function topViolation(entity: RadarEntityProfile): ViolationType | null {
  const ranked = Object.entries(entity.violation_counts ?? {}).sort((a, b) => b[1] - a[1]);
  return (ranked[0]?.[0] as ViolationType | undefined) ?? null;
}

/** Corridors as lines (thicker and redder with more reports) and flagged businesses as markers. */
export default function HeatmapMap({ corridors, markers }: HeatmapMapProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";

  return (
    <MapContainer
      center={[...MAP_CENTER]}
      zoom={3}
      minZoom={2}
      scrollWheelZoom={false}
      className="h-[60vh] min-h-72 w-full rounded-lg border"
      aria-label={t("radar.heatmap.mapLabel")}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {corridors.map((corridor) => {
        const style = HEAT_STYLE[corridor.level];
        const [host, home] = corridor.id.split("-");
        return (
          <Polyline
            key={corridor.id}
            positions={[[...corridor.from], [...corridor.to]]}
            pathOptions={{ color: style.color, weight: style.weight, opacity: 0.85 }}
          >
            <Tooltip sticky>
              {countryName(host, language)} → {countryName(home, language)}:{" "}
              {t("radar.heatmap.reports", { n: corridor.reportCount })}
            </Tooltip>
          </Polyline>
        );
      })}

      {corridors
        .filter((corridor) => corridor.level > 0)
        .map((corridor) => (
          <CircleMarker
            key={`end-${corridor.id}`}
            center={[...corridor.from]}
            radius={4 + corridor.level * 2}
            pathOptions={{ color: HEAT_STYLE[corridor.level].color, fillOpacity: 0.7 }}
          />
        ))}

      <MarkerClusterGroup chunkedLoading>
        {markers.map(({ entity, position }) => {
          const violation = topViolation(entity);
          return (
            <Marker
              key={entity.slug}
              position={[...position]}
              icon={markerIcon(entity.risk_level)}
              title={entity.name}
            >
              <Popup>
                <div className="space-y-1 text-sm">
                  <p className="font-semibold">{entity.name}</p>
                  <p>{t(`radar.report.who.types.${entity.entity_type}`)}</p>
                  <p>{t("radar.heatmap.reports", { n: entity.report_count })}</p>
                  {entity.community_rating !== null && (
                    <p>{t("radar.heatmap.rating", { rating: entity.community_rating })}</p>
                  )}
                  {violation && <p>{t(`radar.violation.${violation}`)}</p>}
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MarkerClusterGroup>
    </MapContainer>
  );
}
