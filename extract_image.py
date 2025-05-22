import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from PIL import Image, ImageTk
import numpy as np
import json
from skimage import measure
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
"""
A tkinter-based application to select and extract terrain features from images.

Usage:
    - Left-click and drag to select a rectangular region to set geographic bounds.
    - Right-click on areas of the image to select regions based on color similarity.
    - Export extracted regions to GeoJSON.

The application utilizes color thresholds to determine features and allows setting geographical
bounds for coordinate mapping. Extracted features are displayed and can be exported
in GeoJSON format for further geographic analysis.
"""
class TerrainExtractorApp:
    """
    GUI application to extract terrain features from a map image by selecting
    regions based on color similarity. Features are converted to GeoJSON format
    with geographic coordinates based on user-defined bounds.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Map Terrain Extractor")

        self.picked = []  # list of dicts: {"color": (r,g,b), "contours": [...], "label": str}

        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas_frame = tk.Frame(self.main_frame)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.plot_frame = tk.Frame(self.main_frame, width=300)
        self.plot_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(self.canvas_frame, cursor="cross", bg='gray')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.image = None
        self.original_image = None
        self.tk_image = None
        self.rect = None
        self.start_x = self.start_y = None
        self.bounds = None
        self.img_path = "test.jpg"

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        root.bind("<Configure>", self.on_resize)

        menu = tk.Menu(root)
        menu.add_command(label="Open Map Image", command=self.load_image)
        menu.add_command(label="Export GeoJSON", command=self.export_geojson)
        root.config(menu=menu)

        self.load_image()

    def load_image(self):
        try:
            self.original_image = Image.open(self.img_path)
            self.resize_and_display_image()
            self.root.title(f"Map Terrain Extractor - {self.img_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {self.img_path}\n{e}")

    def resize_and_display_image(self):
        if not self.original_image:
            return
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            return
        img = self.original_image.copy()
        img.thumbnail((w, h), Image.ANTIALIAS)
        self.image = img
        self.tk_image = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        self.canvas.image = self.tk_image

    def on_resize(self, event):
        self.resize_and_display_image()

    def on_press(self, event):
        if self.tk_image is None:
            return
        self.start_x, self.start_y = event.x, event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="red", width=2
        )

    def on_drag(self, event):
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        if not self.rect:
            return
        x0, y0, x1, y1 = map(int, self.canvas.coords(self.rect))
        lat_top = simpledialog.askfloat("Latitude", "Latitude of top-left corner:")
        lon_left = simpledialog.askfloat("Longitude", "Longitude of top-left corner:")
        lat_bottom = simpledialog.askfloat("Latitude", "Latitude of bottom-right corner:")
        lon_right = simpledialog.askfloat("Longitude", "Longitude of bottom-right corner:")
        if None in (lat_top, lon_left, lat_bottom, lon_right):
            messagebox.showwarning("Missing Input", "You must enter all four geographic values.")
            return
        self.bounds = {
            "pixel_box": [x0, y0, x1, y1],
            "geo_box": {"west": lon_left, "east": lon_right, "north": lat_top, "south": lat_bottom}
        }
        self.canvas.create_rectangle(x0, y0, x1, y1, outline="green", width=2)
        self.extract_initial_features()
        messagebox.showinfo("Info", "Bounds captured and initial extraction done.")

    def on_right_click(self, event):
        if not self.image or not self.bounds:
            return
        x, y = event.x, event.y
        if x >= self.image.width or y >= self.image.height:
            messagebox.showwarning("Out of Bounds", "Clicked outside image bounds.")
            return
        rgb = self.image.convert("RGB").getpixel((x, y))
        tol = 30
        lower = np.maximum(np.array(rgb) - tol, 0)
        upper = np.minimum(np.array(rgb) + tol, 255)

        # Show suggested mask bounds
        suggestion = f"Suggested mask:Lower: {lower.tolist()} Upper: {upper.tolist()}"
        messagebox.showinfo("Suggested RGB Range", suggestion)

        mask = self.mask_by_color(self.image.convert("RGB"), lower, upper)
        contours = measure.find_contours(mask, 0.5)
        label = simpledialog.askstring("Feature Label", f"Enter label for RGB {rgb}:")
        if label is None:
            label = "unnamed"
        self.picked.append({"color": rgb, "contours": contours, "label": label})
        self.plot_all_picked()
        swatches = [f"■ {p['label']} - {p['color']}" for p in self.picked]
        msg = "\n".join(swatches)
        messagebox.showinfo("Picked Features", msg)

    def mask_by_color(self, img_rgb, lower, upper):
        data = np.array(img_rgb)
        return np.all((data >= lower) & (data <= upper), axis=-1)

    def pixel_to_latlon(self, x, y, w, h):
        west, east, south, north = self.bounds["geo_box"].values()
        lon = west + (x / w) * (east - west)
        lat = north - (y / h) * (north - south)  # Re-inverted latitude
        return [lon, lat]

    def plot_all_picked(self):
        if not self.bounds or 'pixel_box' not in self.bounds:
            return
        contours_all = []
        features = []
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        for item in self.picked:
            color = item['color']
            for contour in item['contours']:
                pts = np.array(contour)
                if len(pts) > 5:
                    ll = np.array([self.pixel_to_latlon(x, y, w, h) for y, x in pts])
                    contours_all.append((ll, color))
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": ll.tolist()},
                        "properties": {"color": color}
                    })

        for widget in self.plot_frame.winfo_children():
            widget.destroy()
        fig, ax = plt.subplots(figsize=(4, 5), dpi=100)
        for ll, color in contours_all:
            ax.plot(ll[:, 0], ll[:, 1], color=np.array(color) / 255.0, linewidth=0.5)

        corners = self.bounds['pixel_box']
        if len(corners) == 4:
            pts = [(corners[0], corners[1]), (corners[2], corners[1]),
                   (corners[2], corners[3]), (corners[0], corners[3]), (corners[0], corners[1])]
            llb = np.array([self.pixel_to_latlon(x, y, w, h) for x, y in pts])
            ax.plot(llb[:, 0], llb[:, 1], 'r--')

        geo = self.bounds["geo_box"]
        ax.set_xlim(geo["west"], geo["east"])
        ax.set_ylim(geo["north"], geo["south"])
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title("Picked Contours")
        ax.grid(True)

        canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def extract_initial_features(self):
        if not self.bounds or not self.image:
            return
        self.picked = []
        img_rgb = self.image.convert("RGB")
        arr = np.array(img_rgb.convert("L"))
        h, w = arr.shape
        masks = [
            ([80, 50, 20], [150, 100, 70], 'brown'),
            ([0, 0, 100], [100, 100, 255], 'water'),
            ([0, 80, 0], [100, 200, 100], 'forest')
        ]
        for lo, hi, label in masks:
            mask = self.mask_by_color(img_rgb, np.array(lo), np.array(hi))
            cont = measure.find_contours(mask, 0.5)
            self.picked.append({
                "color": tuple(lo),
                "contours": cont,
                "label": label
            })
        self.plot_all_picked()

    def export_geojson(self):
        if not self.bounds:
            messagebox.showwarning("No Bounds", "Please select bounds and extract features first.")
            return
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        features = []
        for item in self.picked:
            color = item['color']
            label = item.get('label', 'unknown')
            for contour in item['contours']:
                if len(contour) > 5:
                    ll = [self.pixel_to_latlon(x, y, w, h) for y, x in contour]
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": ll},
                        "properties": {"color": color, "label": label}
                    })
        path = filedialog.asksaveasfilename(defaultextension=".geojson", filetypes=[("GeoJSON", "*.geojson")])
        if path:
            geojson = {"type": "FeatureCollection", "features": features}
            with open(path, 'w') as f:
                json.dump(geojson, f, indent=2)
            messagebox.showinfo("Saved", f"GeoJSON saved to {path}")

if __name__ == '__main__':
    root = tk.Tk()
    app = TerrainExtractorApp(root)
    root.mainloop()
