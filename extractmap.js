// terrain_extractor_app.js

let canvas, ctx, image = null, geoBounds = null, picked = [], map;

window.onload = () => {
  initMap();
  canvas = document.getElementById("canvas");
  if (!canvas) return;
  ctx = canvas.getContext("2d");
  const imageLoader = document.getElementById("imageLoader");
  if (imageLoader) imageLoader.addEventListener("change", loadImage);
  const exportBtn = document.getElementById("exportGeoJSON");
  if (exportBtn) exportBtn.addEventListener("click", exportGeoJSON);
  canvas.addEventListener("click", onImageClick);
};

function initMap() {
  map = new ol.Map({
    target: 'map',
    layers: [
      new ol.layer.Tile({
        source: new ol.source.XYZ({
          url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
        })
      })
    ],
    view: new ol.View({
      center: ol.proj.fromLonLat([0, 0]),
      zoom: 2
    })
  });
}

function plotGeoJSONOnMap() {
  if (!geoBounds || !Array.isArray(picked)) return;

  const features = picked.flatMap(item => {
    if (!Array.isArray(item.contours)) return [];
    return item.contours.map(c => {
      const coordinates = c.map(([x, y]) => pixelToLatLon(x, y));
      return new ol.Feature({
        geometry: new ol.geom.LineString(coordinates.map(coord => ol.proj.fromLonLat(coord)))
      });
    });
  });

  if (!features.length) return;

  const vectorSource = new ol.source.Vector({ features });
  const vectorLayer = new ol.layer.Vector({
    source: vectorSource,
    style: new ol.style.Style({
      stroke: new ol.style.Stroke({ color: '#ffcc33', width: 2 })
    })
  });

  map.addLayer(vectorLayer);
}

function pixelToLatLon(x, y) {
  const { west, east, north, south } = geoBounds;
  const lon = west + (x / canvas.width) * (east - west);
  const lat = north - (y / canvas.height) * (north - south);
  return [lon, lat];
}

function loadImage(event) {
  const file = event.target.files[0];
  const reader = new FileReader();
  reader.onload = (e) => {
    const img = new Image();
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
      image = img;
    };
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
}

function onImageClick(e) {
  if (!image || !geoBounds) return;
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  const pixel = ctx.getImageData(x, y, 1, 1).data;
  const rgb = [pixel[0], pixel[1], pixel[2]];
  const label = prompt(`Label for RGB(${rgb.join(", ")}):`, "unnamed");
  if (!label) return;
  const tolerance = 30;
  const lower = rgb.map(v => Math.max(0, v - tolerance));
  const upper = rgb.map(v => Math.min(255, v + tolerance));
  const mask = maskByColor(lower, upper);
  const contours = dummyFindContours(mask);
  picked.push({ color: rgb, label, contours });
  alert("Picked color and contours.");
}

function maskByColor(lower, upper) {
  const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const mask = new Uint8Array(canvas.width * canvas.height);
  for (let i = 0; i < mask.length; i++) {
    const j = i * 4;
    const r = imgData.data[j], g = imgData.data[j + 1], b = imgData.data[j + 2];
    mask[i] = (r >= lower[0] && r <= upper[0] &&
              g >= lower[1] && g <= upper[1] &&
              b >= lower[2] && b <= upper[2]) ? 1 : 0;
  }
  return mask;
}

function dummyFindContours(mask) {
  return [];
}

function setGeoBounds(north, south, east, west) {
  geoBounds = { north, south, east, west };
}
