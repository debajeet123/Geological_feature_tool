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

def get_avg_rgb(x, y, sz=5):
    half = sz // 2
    patch = orig[max(0,y-half):min(orig.shape[0],y+half+1),
                 max(0,x-half):min(orig.shape[1],x+half+1)]
    return tuple(np.mean(patch.reshape(-1,3), axis=0).astype(int))

def extract_and_draw(event=None):
    global img
    img = orig.copy()
    # draw bbox
    if bbox:
        x1,y1,x2,y2 = bbox
        cv2.rectangle(img, (x1,y1), (x2,y2), (0,255,0), 2)
    # extract contours
    if bbox and target_rgb is not None:
        x1,y1,x2,y2 = bbox
        region = orig[y1:y2, x1:x2]
        # compute mask
        dist = np.linalg.norm(region.astype(float)-target_rgb, axis=2)
        mask = (dist <= tol).astype(np.uint8)*255
        # find contours via skimage
        contours = measure.find_contours(mask, 0.5)
        for cnt in contours:
            # cnt is in (row,col) of mask coords
            pts = np.round(np.fliplr(cnt) + [x1,y1]).astype(int)
            cv2.polylines(img, [pts], isClosed=True, color=(0,0,255), thickness=1)
    cv2.imshow("Real-Time Contour Extractor", img)

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
