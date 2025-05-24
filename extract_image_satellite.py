import os

# Directory structure and file content definitions
files = {
    "terrain-web/package.json": """{
  "name": "terrain-web",
  "version": "1.0.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "latest",
    "react": "latest",
    "react-dom": "latest",
    "file-saver": "^2.0.5"
  }
}""",
    "terrain-web/tsconfig.json": """{
  "compilerOptions": {
    "target": "es5",
    "lib": ["dom", "esnext"],
    "jsx": "preserve",
    "module": "esnext",
    "moduleResolution": "node",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"]
}""",
    "terrain-web/next-env.d.ts": "/// <reference types=\"next\" />\n/// <reference types=\"next/types/global\" />\n",
    "terrain-web/pages/index.tsx": """import ImageCanvas from '../components/ImageCanvas';
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
""",
    "terrain-web/components/ImageCanvas.tsx": """import { useRef, useEffect, useState } from 'react';

export default function ImageCanvas({ imageSrc, onColorPick, onBoundsDraw }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [start, setStart] = useState<[number, number] | null>(null);

  useEffect(() => {
    const image = new Image();
    image.src = imageSrc;
    image.onload = () => setImg(image);
  }, [imageSrc]);

  useEffect(() => {
    if (!img || !canvasRef.current) return;
    const ctx = canvasRef.current.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(img, 0, 0, img.width, img.height);
  }, [img]);

  const handleClick = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas || !img) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor(e.clientX - rect.left);
    const y = Math.floor(e.clientY - rect.top);
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const [r, g, b] = ctx.getImageData(x, y, 1, 1).data;
    onColorPick([r, g, b]);
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    setStart([e.clientX - rect.left, e.clientY - rect.top]);
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    if (!start) return;
    const rect = canvasRef.current!.getBoundingClientRect();
    const end = [e.clientX - rect.left, e.clientY - rect.top];
    onBoundsDraw(start, end);
    setStart(null);
  };

  return (
    <canvas
      ref={canvasRef}
      width={img?.width || 600}
      height={img?.height || 400}
      onClick={handleClick}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      style={{ border: '1px solid gray', cursor: 'crosshair' }}
    />
  );
}
""",
    "terrain-web/lib/export.ts": """import { saveAs } from 'file-saver';

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
"""
}

# Write all files to the current directory
for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

print("✅ Web app files generated under ./terrain-web/")
