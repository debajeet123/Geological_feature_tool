import ImageCanvas from '../components/ImageCanvas';
import { useState } from 'react';
import { exportGeoJSON } from '../lib/export';

export default function Home() {
  const [color, setColor] = useState<[number, number, number] | null>(null);
  const [bounds, setBounds] = useState<[[number, number], [number, number]] | null>(null);

  const handleExport = () => {
    if (!color || !bounds) return;
    const [start, end] = bounds;
    const dummyPolygon = [
      [start[0], start[1]],
      [end[0], start[1]],
      [end[0], end[1]],
      [start[0], end[1]],
      [start[0], start[1]]
    ];
    exportGeoJSON([dummyPolygon], color);
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>🗺️ Terrain Extractor Web</h2>
      <ImageCanvas
        imageSrc="/test.jpg"
        onColorPick={setColor}
        onBoundsDraw={(start, end) => setBounds([start, end])}
      />
      <div style={{ marginTop: 10 }}>
        {color && <div>🎨 Picked Color: rgb({color.join(', ')})</div>}
        {bounds && <div>📦 Bounds: {JSON.stringify(bounds)}</div>}
      </div>
      <button onClick={handleExport} style={{ marginTop: 10, padding: 8 }}>
        💾 Export GeoJSON
      </button>
    </div>
  );
}
