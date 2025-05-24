import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox, colorchooser
from PIL import Image, ImageTk
import numpy as np
import json
from skimage import measure
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from scipy.interpolate import splprep, splev
from matplotlib.colors import LinearSegmentedColormap
from sklearn.cluster import KMeans
from pathlib import Path
from staticmap import StaticMap, CircleMarker

class TerrainExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🗺️ Map Terrain Extractor v2")
        self.root.geometry("1200x800")
        self.root.minsize(800,600)
        self.original_image = None
        self.image = None
        self.tk_image = None
        self.bounds = None
        self.picked = []
        self.extracted_colormap = None
        self.mode = tk.StringVar(value="Bounds")

        self.main_pane = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        self.canvas_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(self.canvas_frame, weight=3)

        self.help_label = ttk.Label(self.canvas_frame,
            text="ℹ️ Select mode. Left-drag to draw bounds or pick color based on mode.",
            anchor="center")
        self.help_label.pack(fill=tk.X)

        self.canvas = tk.Canvas(self.canvas_frame, bg="gray", cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Configure>", self.resize_canvas_to_image)
        self.hbar = ttk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.vbar = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.ctrl_frame = ttk.Frame(self.main_pane, width=300)
        self.main_pane.add(self.ctrl_frame, weight=1)

        mode_frame = ttk.LabelFrame(self.ctrl_frame, text="Mode", padding=5)
        mode_frame.pack(fill=tk.X, padx=5, pady=4)
        ttk.Radiobutton(mode_frame, text="Draw Bounds", variable=self.mode, value="Bounds").pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(mode_frame, text="Pick Color", variable=self.mode, value="Color").pack(side=tk.LEFT, padx=4)

        ttk.Label(self.ctrl_frame, text="Extracted Features", font=("Segoe UI", 12, "bold")).pack(pady=4)
        self.feature_list = tk.Listbox(self.ctrl_frame, height=15)
        self.feature_list.pack(fill=tk.X, padx=5)
        self.feature_list.bind("<Delete>", self.delete_selected_feature)

        btn_frame = ttk.Frame(self.ctrl_frame)
        btn_frame.pack(fill=tk.X, pady=6)
        ttk.Button(btn_frame, text="Rebuild Colormap 🔄", command=self.rebuild_colormap).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Classify ▶️", command=self.classify_by_colormap).pack(side=tk.LEFT, padx=2)
        ttk.Separator(self.ctrl_frame).pack(fill=tk.X, pady=8)
        ttk.Button(self.ctrl_frame, text="Export GeoJSON", command=self.export_geojson).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(self.ctrl_frame, text="Export KML", command=self.export_kml).pack(fill=tk.X, padx=5, pady=2)

        self.status = ttk.Label(root, text="Ready", anchor="w")
        self.status.pack(fill=tk.X)

        menu = tk.Menu(root)
        menu.add_command(label="Open Image…", command=self.load_image)
        menu.add_command(label="Load OSM Satellite", command=self.load_osm_satellite)
        menu.add_separator()
        menu.add_command(label="Exit", command=root.quit)
        root.config(menu=menu)

        self.load_image()

    def on_left_click(self, event):
        if self.mode.get() == "Bounds":
            self.on_press(event)
        elif self.mode.get() == "Color":
            self.pick_color(event)

    def on_left_release(self, event):
        if self.mode.get() == "Bounds":
            self.on_release_rectangle(event)

    def _display_image_scaled(self):
        if self.original_image is None: return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.original_image.size
        scale = min(cw/iw, ch/ih, 1.0)
        nw, nh = int(iw*scale), int(ih*scale)
        resized = self.original_image.resize((nw, nh), Image.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)
        self.canvas.delete("all")
        self.canvas.create_image(0,0,anchor="nw",image=self.tk_image)
        self.canvas.config(scrollregion=(0,0,nw,nh))
        self.canvas.image = self.tk_image  # prevent garbage collection
    def resize_canvas_to_image(self, event):
        if self.tk_image:
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            img_width = self.original_image.width
            img_height = self.original_image.height

            scale = min(canvas_width/img_width, canvas_height/img_height)

            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            resized_img = self.original_image.resize((new_width, new_height), Image.ANTIALIAS)
        self.image = img.convert("RGB")
        iw, ih = self.original_image.size
        self.bounds = {"pixel_box":[0,0,iw,ih],"geo_box":{"west":-71,"east":-67,"north":-15,"south":-17}}
        self.picked.clear()
        self.feature_list.delete(0, tk.END)
        self.status.config(text=f"Loaded {Path(path).name}")
        self._display_image_scaled()

    def load_osm_satellite(self, geo_box=None, zoom=14, size=(600,600)):
        if geo_box:
            west, east, north, south = geo_box["west"], geo_box["east"], geo_box["north"], geo_box["south"]
            lon = (west + east) / 2
            lat = (north + south) / 2
        else:
            # fallback to default
            lat, lon = 28.61, 77.21
            west, east = lon - 0.05, lon + 0.05
            north, south = lat + 0.05, lat - 0.05

        m = StaticMap(size[0], size[1], url_template='http://a.tile.openstreetmap.org/{z}/{x}/{y}.png')
        m.add_marker(CircleMarker((lon, lat), 'red', 6))
        img = m.render(zoom=zoom).convert("RGB")

        self.original_image, self.image = img.copy(), img
        self.bounds = {
            "pixel_box": [0, 0, size[0], size[1]],
            "geo_box": {"west": west, "east": east, "north": north, "south": south}
        }
        self.picked.clear()
        self.feature_list.delete(0, tk.END)
        self.status.config(text="OSM satellite map loaded")
        self._display_image_scaled()


    def on_press(self, event):
        self.start_x, self.start_y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if hasattr(self, 'rect'): self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y,
                                                 self.start_x, self.start_y,
                                                 outline="red", width=2)

    def on_drag(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, x, y)

    def on_release_rectangle(self, event):
        x1, y1 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        xa, xb = sorted((int(self.start_x), int(x1)))
        ya, yb = sorted((int(self.start_y), int(y1)))

        # Automatically convert pixel bounds to geo bounds using existing geo mapping
        lon1, lat1 = self.pixel_to_latlon(xa, ya)
        lon2, lat2 = self.pixel_to_latlon(xb, yb)
        geo_box = {
            "north": max(lat1, lat2),
            "south": min(lat1, lat2),
            "west": min(lon1, lon2),
            "east": max(lon1, lon2)
        }

        self.bounds = {
            "pixel_box": [xa, ya, xb, yb],
            "geo_box": geo_box
        }

        self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(xa, ya, xb, yb, outline="green", width=2)
        self.status.config(text="Geo-bounds set.")


    def on_mouse_move(self, event):
        if not self.bounds: return
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        lon, lat = self.pixel_to_latlon(x, y)
        self.status.config(text=f"Lon: {lon:.5f}   Lat: {lat:.5f}")

    def pixel_to_latlon(self, x, y):
        xa, ya, xb, yb = self.bounds["pixel_box"]
        geo = self.bounds["geo_box"]
        rx, ry = (x-xa)/(xb-xa), (y-ya)/(yb-ya)
        lon = geo['west'] + rx*(geo['east']-geo['west'])
        lat = geo['north'] - ry*(geo['north']-geo['south'])
        return lon, lat

    def get_avg_rgb(self, x, y, sz=5):
        half = sz//2
        vals = [self.image.getpixel((int(x+dx), int(y+dy)))
                for dx in range(-half, half+1)
                for dy in range(-half, half+1)
                if 0 <= int(x+dx) < self.image.width and 0 <= int(y+dy) < self.image.height]
        return tuple(np.mean(vals, axis=0).astype(int))

    def pick_color(self, event):
        if self.image is None: return
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        rgb = self.get_avg_rgb(x, y)
        self.extract_and_store_color(rgb)

    def extract_and_store_color(self, rgb, tol=30):
        data = np.array(self.image)
        dist = np.linalg.norm(data.astype(float)-rgb, axis=-1)
        mask = dist <= tol
        contours = measure.find_contours(mask, 0.5)
        lbl = f"{rgb}"
        self.picked.append({"color": rgb, "contours": contours, "label": lbl})
        self.feature_list.insert(tk.END, f"{len(self.picked)-1}: {lbl}")
        self.plot_all_picked()

    def delete_selected_feature(self, event=None):
        sel = self.feature_list.curselection()
        if not sel: return
        idx = sel[0]
        self.picked.pop(idx)
        self.feature_list.delete(idx)
        self.plot_all_picked()

    def smooth_contour(self, contour, s=2.0, pts=200):
        if len(contour) < 5: return contour
        y, x = contour[:, 0], contour[:, 1]
        try:
            tck, _ = splprep([x, y], s=s)
            u = np.linspace(0, 1, pts)
            x2, y2 = splev(u, tck)
            return np.column_stack([y2, x2])
        except:
            return contour

    def plot_all_picked(self):
        for child in self.ctrl_frame.pack_slaves():
            if isinstance(child, FigureCanvasTkAgg):
                child.get_tk_widget().destroy()
        fig, ax = plt.subplots(figsize=(3, 3), dpi=100)
        xa, ya, xb, yb = self.bounds["pixel_box"]
        for item in self.picked:
            col = np.array(item['color'])/255.0
            for cnt in item['contours']:
                sm = self.smooth_contour(np.array(cnt))
                lons, lats = zip(*(self.pixel_to_latlon(xa + xx, ya + yy) for yy, xx in sm))
                ax.plot(lons, lats, color=col, linewidth=0.8)
        geo = self.bounds["geo_box"]
        ax.set_aspect('equal')
        ax.set_xlim(geo['west'], geo['east'])
        ax.set_ylim(geo['south'], geo['north'])
        ax.grid(True)
        canvas = FigureCanvasTkAgg(fig, master=self.ctrl_frame)
        canvas.draw(); canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def rebuild_colormap(self):
        n = simpledialog.askinteger("Clusters", "How many clusters?", initialvalue=12, minvalue=2, maxvalue=50)
        if not n: return
        data = np.array(self.image).reshape(-1, 3)
        kmeans = KMeans(n_clusters=n, random_state=0).fit(data)
        cols = kmeans.cluster_centers_.astype(int)
        idx = np.argsort(np.sum(cols, axis=1))
        self.extracted_colormap = cols[idx]
        fig, ax = plt.subplots(figsize=(6, 1), dpi=100)
        cmap = LinearSegmentedColormap.from_list("cm", self.extracted_colormap/255.0)
        grad = np.linspace(0, 1, 256).reshape(1, -1)
        ax.imshow(grad, aspect='auto', cmap=cmap)
        ax.axis('off')
        canvas = FigureCanvasTkAgg(fig, master=self.ctrl_frame)
        canvas.draw(); canvas.get_tk_widget().pack(fill=tk.X, padx=5, pady=5)

    def classify_by_colormap(self):
        tol = simpledialog.askinteger("Tolerance", "Color tolerance?", initialvalue=30, minvalue=1, maxvalue=100)
        self.picked.clear(); self.feature_list.delete(0, tk.END)
        img = np.array(self.image)
        for i, color in enumerate(self.extracted_colormap):
            dist = np.linalg.norm(img.astype(float)-color, axis=-1)
            mask = dist <= tol
            contours = measure.find_contours(mask, 0.5)
            lbl = f"class_{i}"
            self.picked.append({"color": tuple(color), "contours": contours, "label": lbl})
            self.feature_list.insert(tk.END, f"{i}: {lbl}")
        self.plot_all_picked()

    def export_geojson(self):
        if not self.picked: return
        features = []; xa, ya, xb, yb = self.bounds["pixel_box"]
        for item in self.picked:
            for cnt in item['contours']:
                sm = self.smooth_contour(np.array(cnt))
                coords = [[*self.pixel_to_latlon(xa + xx, ya + yy)] for yy, xx in sm]
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {"label": item['label'], "color": item['color']}
                })
        path = filedialog.asksaveasfilename(defaultextension=".geojson")
        if path:
            with open(path, "w") as f: json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)

    def export_kml(self):
        if not self.picked: return
        xa, ya, xb, yb = self.bounds["pixel_box"]
        kml = ['<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>']
        rgb, _ = colorchooser.askcolor(title="Pick KML Line Color")
        if not rgb: return
        color_hex = ''.join(f"{int(c):02x}" for c in reversed(rgb)) + "ff"
        for item in self.picked:
            for cnt in item['contours']:
                sm = self.smooth_contour(np.array(cnt))
                coords = [f"{lon},{lat},0" for lon, lat in (self.pixel_to_latlon(xa + xx, ya + yy) for yy, xx in sm)]
                kml += [f"<Placemark><name>{item['label']}</name>",
                        f"<Style><LineStyle><color>{color_hex}</color><width>2</width></LineStyle></Style>",
                        "<LineString><tessellate>1</tessellate><coordinates>",
                        " ".join(coords),
                        "</coordinates></LineString></Placemark>"]
        kml.append("</Document></kml>")
        path = filedialog.asksaveasfilename(defaultextension=".kml")
        if path:
            with open(path, "w") as f: f.write("\n".join(kml))
    
    def load_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff")])
        if not path:
            return
        img = Image.open(path)
        self.original_image = img.convert("RGB")
        self.image = self.original_image.copy()
        iw, ih = self.original_image.size
        self.bounds = {
            "pixel_box": [0, 0, iw, ih],
            "geo_box": {"west": -71, "east": -67, "north": -15, "south": -17}
        }
        self.picked.clear()
        self.feature_list.delete(0, tk.END)
        self.status.config(text=f"Loaded {Path(path).name}")
        self._display_image_scaled()


def main():
    root = tk.Tk()
    style = ttk.Style(root); style.theme_use("clam")
    app = TerrainExtractorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
