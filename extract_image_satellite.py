# terrain_extractor_app.py

import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from PIL import Image, ImageTk
import numpy as np
import json
from skimage import measure
import folium
from pathlib import Path

class TerrainExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Map Terrain Extractor")

        self.picked = []

        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.main_frame, cursor="cross", bg='gray')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.image = None
        self.tk_image = None
        self.geo_bounds = None

        self.canvas.bind("<ButtonPress-1>", self.on_click)

        menu = tk.Menu(root)
        menu.add_command(label="Open Image", command=self.load_image)
        menu.add_command(label="Export GeoJSON", command=self.export_geojson)
        menu.add_command(label="Plot on Satellite Map", command=self.plot_on_map)
        menu.add_command(label="Export KML", command=self.export_kml)
        root.config(menu=menu)

    def load_image(self):
        path = filedialog.askopenfilename(title="Open Map Image")
        if not path:
            path = "test.jpg"
            if not Path(path).exists():
                messagebox.showwarning("Missing Image", "No image selected and test.jpg not found.")
                return
        img = Image.open(path)
        self.image = img.convert("RGB")
        self.tk_image = ImageTk.PhotoImage(img)
        self.canvas.config(width=img.width, height=img.height)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        print(f"Image loaded: size={{img.size}}, mode={{img.mode}}")
        print(f"Canvas: {{self.canvas.winfo_width()}}x{{self.canvas.winfo_height()}}")
        self.canvas.image = self.tk_image
        self.canvas.image = self.tk_image

    def on_click(self, event):
        if not self.image:
            return
        x, y = event.x, event.y
        rgb = self.image.getpixel((x, y))
        tol = 30
        lower = np.maximum(np.array(rgb) - tol, 0)
        upper = np.minimum(np.array(rgb) + tol, 255)
        mask = self.mask_by_color(lower, upper)
        contours = measure.find_contours(mask, 0.5)
        label = simpledialog.askstring("Label", f"Enter label for {rgb}:") or "unnamed"
        self.picked.append({"color": rgb, "label": label, "contours": contours})

    def mask_by_color(self, lower, upper):
        data = np.array(self.image)
        return np.all((data >= lower) & (data <= upper), axis=-1)

    def export_geojson(self):
        if not self.geo_bounds:
            self.ask_bounds()
        h, w = self.image.size[::-1]
        features = []
        for item in self.picked:
            for contour in item['contours']:
                coords = [self.pixel_to_latlon(x, y, w, h) for y, x in contour]
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {"label": item['label'], "color": item['color']}
                })
        geojson = {"type": "FeatureCollection", "features": features}
        path = filedialog.asksaveasfilename(defaultextension=".geojson")
        if path:
            with open(path, "w") as f:
                json.dump(geojson, f, indent=2)
            messagebox.showinfo("Saved", f"GeoJSON saved to {path}")

    def ask_bounds(self):
        north = simpledialog.askfloat("Bound", "North Latitude")
        south = simpledialog.askfloat("Bound", "South Latitude")
        east = simpledialog.askfloat("Bound", "East Longitude")
        west = simpledialog.askfloat("Bound", "West Longitude")
        self.geo_bounds = {"north": north, "south": south, "east": east, "west": west}

    def pixel_to_latlon(self, x, y, w, h):
        b = self.geo_bounds
        lon = b['west'] + (x / w) * (b['east'] - b['west'])
        lat = b['north'] - (y / h) * (b['north'] - b['south'])
        return [lon, lat]

    def export_kml(self):
        if not self.geo_bounds:
            self.ask_bounds()
        h, w = self.image.size[::-1]
        kml = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<kml xmlns="http://www.opengis.net/kml/2.2">',
               '<Document>']
        for item in self.picked:
            color = ''.join(f"{c:02x}" for c in reversed(item['color'])) + 'ff'
            label = item.get('label', 'unknown')
            for contour in item['contours']:
                if len(contour) > 5:
                    coords = [self.pixel_to_latlon(x, y, w, h) for y, x in contour]
                    coord_str = ' '.join(f"{lon},{lat},0" for lon, lat in coords)
                    kml.extend([
                        '<Placemark>',
                        f'<name>{label}</name>',
                        '<Style><LineStyle>',
                        f'<color>{color}</color><width>2</width>',
                        '</LineStyle></Style>',
                        '<LineString><tessellate>1</tessellate><coordinates>',
                        coord_str,
                        '</coordinates></LineString>',
                        '</Placemark>'
                    ])
        kml.append('</Document></kml>')
        path = filedialog.asksaveasfilename(defaultextension=".kml", filetypes=[("KML files", "*.kml")])
        if path:
            with open(path, "w") as f:
                f.write('\n'.join(kml))
            messagebox.showinfo("Saved", f"KML saved to {path}")

    def plot_on_map(self):
        if not self.geo_bounds:
            self.ask_bounds()
        h, w = self.image.size[::-1]
        features = []
        for item in self.picked:
            for contour in item['contours']:
                coords = [self.pixel_to_latlon(x, y, w, h) for y, x in contour]
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {"label": item['label'], "color": item['color']}
                })

        geojson = {"type": "FeatureCollection", "features": features}
        lat_center = (self.geo_bounds['north'] + self.geo_bounds['south']) / 2
        lon_center = (self.geo_bounds['east'] + self.geo_bounds['west']) / 2

        m = folium.Map(location=[lat_center, lon_center], zoom_start=13,
                       tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                       attr="Esri")
        folium.GeoJson(geojson, name="Extracted").add_to(m)
        m.save("satellite_geojson_map.html")
        messagebox.showinfo("Map Saved", "Satellite map with GeoJSON saved as satellite_geojson_map.html")

if __name__ == '__main__':
    root = tk.Tk()
    app = TerrainExtractorApp(root)
    root.mainloop()
