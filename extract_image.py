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

class TerrainExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🗺️ Map Terrain Extractor v2")
        self.root.geometry("1200x800")
        self.root.minsize(800,600)

        # State
        self.original_image = None
        self.image = None
        self.tk_image = None
        self.bounds = None            # dict with pixel_box + geo_box
        self.picked = []              # list of dicts: {color, contours, label}
        self.extracted_colormap = None

        # --- UI Layout ---
        self.main_pane = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        # Left: Canvas
        self.canvas_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(self.canvas_frame, weight=3)
        self.canvas = tk.Canvas(self.canvas_frame, bg="gray", cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release_or_pick)
        self.canvas.bind("<Motion>", self.on_mouse_move)

        # Scrollbars
        self.hbar = ttk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.vbar = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right: Controls & Feature List
        self.ctrl_frame = ttk.Frame(self.main_pane, width=300)
        self.main_pane.add(self.ctrl_frame, weight=1)
        ttk.Label(self.ctrl_frame, text="Extracted Features", font=("Segoe UI", 12, "bold")).pack(pady=4)
        self.feature_list = tk.Listbox(self.ctrl_frame, height=15)
        self.feature_list.pack(fill=tk.X, padx=5)
        self.feature_list.bind("<Delete>", self.delete_selected_feature)

        btn_frame = ttk.Frame(self.ctrl_frame)
        btn_frame.pack(fill=tk.X, pady=6)
        ttk.Button(btn_frame, text="Pick Color  🖌️", command=self.pick_color_from_palette).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Rebuild Colormap 🔄", command=self.rebuild_colormap).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Classify ▶️", command=self.classify_by_colormap).pack(side=tk.LEFT, padx=2)

        ttk.Separator(self.ctrl_frame).pack(fill=tk.X, pady=8)
        ttk.Button(self.ctrl_frame, text="Export GeoJSON", command=self.export_geojson).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(self.ctrl_frame, text="Export KML",     command=self.export_kml)    .pack(fill=tk.X, padx=5, pady=2)

        # Status Bar
        self.status = ttk.Label(root, text="Ready", anchor="w")
        self.status.pack(fill=tk.X)

        # Menus & Shortcuts
        self.root.bind_all("<Control-o>", lambda e: self.load_image())
        menu = tk.Menu(root)
        menu.add_command(label="Open Image…    Ctrl+O", command=self.load_image)
        menu.add_separator()
        menu.add_command(label="Exit", command=root.quit)
        root.config(menu=menu)

        # Start
        self.load_image()

    # --- Image Loading & Display ---
    def load_image(self):
        path = filedialog.askopenfilename(
            title="Open Map Image",
            filetypes=[("Images","*.png *.jpg *.jpeg *.tif *.bmp"),("All","*.*")]
        )
        if not path:
            return
        img = Image.open(path)
        self.original_image = img.copy()
        self.image = img.convert("RGB")
        self.tk_image = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0,0,anchor="nw",image=self.tk_image)
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        self.bounds = None
        self.picked.clear()
        self.refresh_feature_list()
        self.status.config(text=f"Loaded {Path(path).name}")

    # --- Rectangle for Georeferencing ---
    def on_press(self, event):
        self.start_x, self.start_y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if hasattr(self, 'rect'): self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y,
                                                 outline="red", width=2)

    def on_drag(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, x, y)

    def on_release_or_pick(self, event):
        x1, y1 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if abs(x1-self.start_x)>3 and abs(y1-self.start_y)>3:
            self.finish_rectangle(self.start_x, self.start_y, x1, y1)
        else:
            self.pick_color(event)

    def finish_rectangle(self, x0,y0,x1,y1):
        # normalize
        xa,xb = sorted([int(x0),int(x1)])
        ya,yb = sorted([int(y0),int(y1)])
        # ask geocoords
        lat_top    = simpledialog.askfloat("Top Latitude",    "Latitude of top edge:")
        lat_bottom = simpledialog.askfloat("Bottom Latitude", "Latitude of bottom edge:")
        lon_left   = simpledialog.askfloat("Left Longitude",  "Longitude of left edge:")
        lon_right  = simpledialog.askfloat("Right Longitude", "Longitude of right edge:")
        if None in (lat_top,lat_bottom,lon_left,lon_right):
            messagebox.showwarning("Need all four", "Bounding box requires four coordinates.")
            return
        self.bounds = {
            "pixel_box": [xa, ya, xb, yb],
            "geo_box":   {"north":lat_top,"south":lat_bottom,"west":lon_left,"east":lon_right}
        }
        # redraw
        self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(xa,ya,xb,yb,outline="green",width=2)
        self.status.config(text="Geo‐bounds set.")
        self.extract_initial_features()

    # --- Mouse coords display ---
    def on_mouse_move(self, event):
        if not self.bounds: return
        x,y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        lon,lat = self.pixel_to_latlon(x,y)
        self.status.config(text=f"Lon: {lon:.5f}   Lat: {lat:.5f}")

    def pixel_to_latlon(self, x, y):
        xa,ya,xb,yb = self.bounds["pixel_box"]
        geo = self.bounds["geo_box"]
        # relative
        rx = (x - xa)/(xb-xa)
        ry = (y - ya)/(yb-ya)
        lon = geo['west'] + rx*(geo['east']-geo['west'])
        lat = geo['north'] - ry*(geo['north']-geo['south'])
        return lon,lat

    # --- Color‐based feature extraction ---
    def get_avg_rgb(self, x,y,sz=5):
        half = sz//2
        pixels=[]
        for dx in range(-half,half+1):
            for dy in range(-half,half+1):
                xx,yy=int(x+dx),int(y+dy)
                if 0<=xx<self.image.width and 0<=yy<self.image.height:
                    pixels.append(self.image.getpixel((xx,yy)))
        return tuple(np.mean(pixels,axis=0).astype(int))

    def pick_color(self, event):
        if not self.bounds: return
        x,y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        rgb = self.get_avg_rgb(x,y)
        self.extract_and_store_color(rgb)

    def pick_color_from_palette(self):
        if not self.bounds:
            messagebox.showwarning("First…","Select bounds from the map.")
            return
        color,_ = colorchooser.askcolor(title="Pick terrain color")
        if color:
            rgb = tuple(int(c) for c in color)
            self.extract_and_store_color(rgb)

    def extract_and_store_color(self, rgb, tol=30):
        lo = np.array(rgb)-tol; hi = np.array(rgb)+tol
        data = np.array(self.image)
        # Euclidean mask
        dist = np.linalg.norm(data.astype(float)-rgb,axis=-1)
        mask = dist <= tol
        contours = measure.find_contours(mask, 0.5)
        lbl = simpledialog.askstring("Label","Name for this feature:") or f"{rgb}"
        self.picked.append({"color":rgb,"contours":contours,"label":lbl})
        self.status.config(text=f"Picked {lbl} ({len(contours)} contours)")
        self.refresh_feature_list()
        self.plot_all_picked()

    def extract_initial_features(self):
        # example presets
        presets = [
            ((80,50,20), "soil"),
            ((0,0,200), "water"),
            ((0,150,0), "forest"),
        ]
        self.picked.clear()
        for rgb,lbl in presets:
            self.extract_and_store_color(rgb, tol=40)
            self.picked[-1]['label']=lbl
        self.refresh_feature_list()

    # --- Plotting contours in small axes ---
    def smooth_contour(self, contour, s=2.0, pts=200):
        if len(contour)<5: return contour
        y,x = contour[:,0], contour[:,1]
        try:
            tck,_ = splprep([x,y],s=s)
            u = np.linspace(0,1,pts)
            x2,y2 = splev(u,tck)
            return np.column_stack([y2,x2])
        except:
            return contour

    def plot_all_picked(self):
        # clear old
        for w in self.ctrl_frame.pack_slaves():
            if isinstance(w,FigureCanvasTkAgg):
                w.get_tk_widget().destroy()

        fig,ax = plt.subplots(figsize=(3,3),dpi=100)
        xa,ya,xb,yb = self.bounds["pixel_box"]
        w_px, h_px = xb-xa, yb-ya

        for item in self.picked:
            col = np.array(item['color'])/255
            for c in item['contours']:
                arr = np.array(c)
                sm = self.smooth_contour(arr)
                # map to lat/lon
                lons,lats=[],[]
                for yy,xx in sm:
                    lon,lat = self.pixel_to_latlon(xa+xx, ya+yy)
                    lons.append(lon); lats.append(lat)
                ax.plot(lons,lats, color=col, linewidth=0.8)
        geo = self.bounds["geo_box"]
        ax.set_title("Extracted Layers"); ax.grid(True)
        ax.set_xlim(geo['west'],geo['east']); ax.set_ylim(geo['south'],geo['north'])
        c = FigureCanvasTkAgg(fig, master=self.ctrl_frame)
        c.draw(); c.get_tk_widget().pack(fill=tk.BOTH,expand=True,padx=5,pady=5)

    # --- Feature List UI ---
    def refresh_feature_list(self):
        self.feature_list.delete(0,tk.END)
        for i,item in enumerate(self.picked):
            self.feature_list.insert(tk.END, f"{i}: {item['label']}  {item['color']}")

    def delete_selected_feature(self, event=None):
        sel = self.feature_list.curselection()
        if not sel: return
        idx = sel[0]
        item = self.picked.pop(idx)
        self.status.config(text=f"Deleted {item['label']}")
        self.refresh_feature_list()
        if self.bounds:
            self.plot_all_picked()

    # --- Colormap rebuild & classify ---
    def rebuild_colormap(self):
        if self.image is None: return
        n = simpledialog.askinteger("Clusters","How many clusters?",initialvalue=12,minvalue=2,maxvalue=50)
        if not n: return
        data = np.array(self.image).reshape(-1,3)
        self.status.config(text="Clustering…")
        kmeans = KMeans(n_clusters=n,random_state=0).fit(data)
        cols = kmeans.cluster_centers_.astype(int)
        # sort by brightness
        sort_idx = np.argsort(np.sum(cols,axis=1))
        self.extracted_colormap = cols[sort_idx]
        # show gradient
        cmap = LinearSegmentedColormap.from_list("cm", self.extracted_colormap/255.)
        grad = np.linspace(0,1,256).reshape(1,-1)
        plt.figure(figsize=(6,1)); plt.imshow(grad,aspect='auto',cmap=cmap)
        plt.axis('off'); plt.show()
        self.status.config(text=f"Built {n} colors")

    def classify_by_colormap(self):
        if self.extracted_colormap is None:
            messagebox.showwarning("First…","Run Rebuild Colormap")
            return
        if self.bounds is None:
            messagebox.showwarning("First…","Select bounds")
            return
        self.picked.clear()
        img = np.array(self.image)
        tol = simpledialog.askinteger("Tolerance","Color tolerance?",initialvalue=30,minvalue=1,maxvalue=100)
        for idx,color in enumerate(self.extracted_colormap):
            dist = np.linalg.norm(img.astype(float)-color,axis=-1)
            mask = dist<=tol
            contours = measure.find_contours(mask,0.5)
            self.picked.append({"color":tuple(color),"contours":contours,"label":f"class_{idx}"})
        self.refresh_feature_list()
        self.plot_all_picked()
        self.status.config(text="Classification done")

    # --- Exporters ---
    def export_geojson(self):
        if not self.bounds or not self.picked:
            messagebox.showwarning("Nothing to export","Select bounds & extract features first.")
            return
        features=[]
        xa,ya,xb,yb = self.bounds["pixel_box"]
        for item in self.picked:
            for cnt in item['contours']:
                arr = np.array(cnt)
                if len(arr)<6: continue
                coords = []
                for yy,xx in self.smooth_contour(arr):
                    lon,lat = self.pixel_to_latlon(xa+xx,ya+yy)
                    coords.append([lon,lat])
                features.append({
                    "type":"Feature",
                    "properties":{"label":item['label'],"color":item['color']},
                    "geometry":{"type":"LineString","coordinates":coords}
                })
        out = {"type":"FeatureCollection","features":features}
        path = filedialog.asksaveasfilename(defaultextension=".geojson")
        if path:
            with open(path,"w") as f: json.dump(out,f,indent=2)
            messagebox.showinfo("Saved",f"GeoJSON → {path}")

    def export_kml(self):
        if not self.bounds or not self.picked:
            messagebox.showwarning("Nothing to export","Select bounds & extract features first.")
            return
        xa,ya,xb,yb = self.bounds["pixel_box"]
        kml = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>']
        for item in self.picked:
            col = ''.join(f"{c:02x}" for c in item['color'][::-1]) + "ff"
            for cnt in item['contours']:
                arr = np.array(cnt)
                if len(arr)<6: continue
                coords=[]
                for yy,xx in self.smooth_contour(arr):
                    lon,lat = self.pixel_to_latlon(xa+xx,ya+yy)
                    coords.append(f"{lon},{lat},0")
                kml += [f"<Placemark><name>{item['label']}</name>",
                        "<Style><LineStyle><color>"+col+"</color><width>2</width></LineStyle></Style>",
                        "<LineString><tessellate>1</tessellate><coordinates>",
                        " ".join(coords),
                        "</coordinates></LineString></Placemark>"]
        kml.append("</Document></kml>")
        path = filedialog.asksaveasfilename(defaultextension=".kml")
        if path:
            with open(path,"w") as f: f.write("\n".join(kml))
            messagebox.showinfo("Saved",f"KML → {path}")

if __name__=="__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use("clam")
    app = TerrainExtractorApp(root)
    root.mainloop()