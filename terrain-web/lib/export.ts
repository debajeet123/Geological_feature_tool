import { saveAs } from 'file-saver';

export function exportGeoJSON(polygons: number[][][], color: [number, number, number]) {
  const features = polygons.map((ring, i) => ({
    type: "Feature",
    geometry: {
      type: "Polygon",
      coordinates: [ring.map(([x, y]) => [x, y])]
    },
    properties: {
      id: i,
      color: `rgb(${color.join(",")})`
    }
  }));
  const geojson = {
    type: "FeatureCollection",
    features
  };
  const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: "application/json" });
  saveAs(blob, "features.geojson");
}
