import cv2
import numpy as np
from skimage import measure

# globals for mouse callback
drawing = False
ix, iy = -1, -1
bbox = None
target_rgb = None
tol = 30

# load & clone
img = cv2.imread("test.jpg")
if img is None:
    raise FileNotFoundError("map.png not found")
orig = img.copy()

# Assume full image spans this geo extent (you can change this)
geo_bounds = {
    "west": -71,
    "east": -66.8,
    "north": -15,
    "south": -17.5
}
def pixel_to_latlon(x, y, img_shape, geo_bounds):
    h, w = img_shape[:2]
    rx = x / w
    ry = y / h
    lon = geo_bounds["west"] + rx * (geo_bounds["east"] - geo_bounds["west"])
    lat = geo_bounds["north"] - ry * (geo_bounds["north"] - geo_bounds["south"])
    return lon, lat

def get_avg_rgb(x, y, sz=5):
    half = sz // 2
    patch = orig[max(0,y-half):min(orig.shape[0],y+half+1),
                 max(0,x-half):min(orig.shape[1],x+half+1)]
    return tuple(np.mean(patch.reshape(-1,3), axis=0).astype(int))

def extract_and_draw(event=None):
    global img
    img = orig.copy()
    if bbox:
        x1, y1, x2, y2 = bbox
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Convert pixel coords to lat/lon
        lon_nw, lat_nw = pixel_to_latlon(x1, y1, img.shape, geo_bounds)
        lon_se, lat_se = pixel_to_latlon(x2, y2, img.shape, geo_bounds)

        # Format labels
        label_nw = f"NW: {lon_nw:.5f}, {lat_nw:.5f}"
        label_se = f"SE: {lon_se:.5f}, {lat_se:.5f}"

        # ✅ Use black color for text (0, 0, 0) with larger font and proper placement
        text_size_nw = cv2.getTextSize(label_nw, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0]
        text_size_se = cv2.getTextSize(label_se, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0]

        nw_x = max(x1 + 4, 10)
        nw_y = max(y1 - 20, text_size_nw[1] + 10)
        cv2.putText(img, label_nw, (nw_x, nw_y),
            cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 0), 2, cv2.LINE_AA)

        se_x = max(x2 - text_size_se[0] - 10, 10)
        se_y = min(y2 + 25, img.shape[0] - 10)
        cv2.putText(img, label_se, (se_x, se_y),
            cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 0), 2, cv2.LINE_AA)

    if bbox and target_rgb is not None:
        x1, y1, x2, y2 = bbox
        region = orig[y1:y2, x1:x2]
        dist = np.linalg.norm(region.astype(float) - target_rgb, axis=2)
        mask = (dist <= tol).astype(np.uint8) * 255
        contours = measure.find_contours(mask, 0.5)
        for cnt in contours:
            pts = np.round(np.fliplr(cnt) + [x1, y1]).astype(int)
            cv2.polylines(img, [pts], isClosed=True, color=(0, 0, 255), thickness=1)
            for (px, py) in pts:
                cv2.circle(img, (px, py), radius=2, color=(0, 0, 255), thickness=-1)
        save_kml(contours, bbox, filename="picked_contours.kml")

    cv2.imshow("Real-Time Contour Extractor", img)




from pathlib import Path

def save_kml(contours, bbox, filename="picked_contours.kml"):
    x1, y1, x2, y2 = bbox
    kml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>']
    for i, cnt in enumerate(contours):
        pts = np.round(np.fliplr(cnt) + [x1, y1]).astype(int)
        coords = [
            f"{lon},{lat},0"
            for px, py in pts
            for lon, lat in [pixel_to_latlon(px, py, orig.shape, geo_bounds)]
        ]
        kml += [
            f"<Placemark><name>feature_{i}</name>",
            "<Style><LineStyle><color>ff0000ff</color><width>2</width></LineStyle></Style>",
            "<LineString><tessellate>1</tessellate><coordinates>",
            " ".join(coords),
            "</coordinates></LineString></Placemark>"
        ]
    kml.append("</Document></kml>")
    Path(filename).write_text("\n".join(kml))
    print(f"[✔] Saved Geo-referenced KML → {filename}")


def mouse_cb(event, x, y, flags, param):
    global ix, iy, drawing, bbox, target_rgb
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y
        bbox = None
    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        # update live rectangle
        img[:] = orig.copy()
        cv2.rectangle(img, (ix,iy), (x,y), (0,255,0), 2)
        cv2.imshow("Real-Time Contour Extractor", img)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        # finalize bbox
        x1, x2 = sorted([ix, x])
        y1, y2 = sorted([iy, y])
        bbox = (x1, y1, x2, y2)
        extract_and_draw()
    elif event == cv2.EVENT_RBUTTONDOWN:
        # pick color inside bbox
        if bbox:
            target_rgb = get_avg_rgb(x, y, sz=7)
            print(f"[INFO] Picked RGB: {target_rgb}")
            extract_and_draw()

# set up window
cv2.namedWindow("Real-Time Contour Extractor", cv2.WINDOW_NORMAL)
cv2.setMouseCallback("Real-Time Contour Extractor", mouse_cb)
extract_and_draw()

print("Instructions:")
print(" • Left-drag to draw/update bounding box")
print(" • Right-click inside box to pick contour color")
print(" • Hit ESC to exit")

# main loop
while True:
    key = cv2.waitKey(1) & 0xFF
    if key == 27:  # ESC
        break

cv2.destroyAllWindows()
