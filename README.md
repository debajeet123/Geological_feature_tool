# 🗺️ Real-Time Map Contour Extractor

A Python-based tool to interactively extract map features by color, using OpenCV and scikit-image. Automatically converts bounding boxes and contours into georeferenced coordinates and exports to KML.

![screenshot](docs/demo.png)

---


## ✨ Features

- 🖱️ Draw bounding boxes interactively
- 🎨 Click to pick colors and extract contours
- 🌍 Converts pixel positions to **lat/lon** using geo bounds
- 📍 Auto-export selected features to **KML**
- 🧭 Displays real-time lat/lon on image
- 🐍 Pure Python (OpenCV, skimage, NumPy, matplotlib)

---

## 🚀 Quickstart

### 1. Install dependencies

```bash
pip install opencv-python numpy scikit-image matplotlib
```

### 2. Run the app

```bash
python app.py
```

Replace `app.py` with your actual filename.

---

## 🖼️ Instructions

- **Left-drag** to select a rectangular region (bounding box).
- **Right-click** inside the box to pick a color and extract contours.
- The contours matching the color (within a tolerance) are drawn.
- A `.kml` file is **automatically saved** in the current folder.
- Lat/Lon labels appear in real time on the image window.

---

## 🌐 Coordinate Handling

You define your map’s geographical extent:

```python
geo_bounds = {
  "west": 88.3,
  "east": 88.6,
  "north": 22.7,
  "south": 22.5
}
```

Pixel coordinates are automatically converted to geographic coordinates using this bounding box.

---

## 🗂️ Output

- `picked_contours.kml`: Georeferenced contours viewable in Google Earth.
- Bounding box corners appear in `NW` and `SE` labels.
- Contours are red lines with extracted points as red dots.

---

## 📸 Screenshot

<p align="center">
  <img src="Topographic Map with Contour Box.png" width="800"/>
</p>

---

## 🛠️ Customization

- Change `tol` in code to increase/decrease color matching tolerance.
- Replace `save_kml()` to export to GeoJSON if needed.
- Add `timestamp` or `uuid` to filenames for batch work.

---

## 📎 To Do

- [ ] Add GUI-based file selector
- [ ] Optional shapefile export
- [ ] Batch processing from directory

---

## 📜 License

MIT © 2025 Debajeet Barman