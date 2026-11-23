const URLS = window.SOIL_VIZ_URLS;

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? m[1] : '';
}

function jsonHeaders() {
  return { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() };
}

// A non-2xx response isn't always JSON (e.g. Django's CSRF-failure or 500
// pages are HTML) — parsing those with res.json() throws and used to get
// mislabeled as "Network error" by the outer catch. This always resolves to
// a usable message instead.
async function errorMessageFromResponse(res) {
  try {
    const d = await res.json();
    if (d && d.error) return d.error;
  } catch (e) { /* not JSON — fall through */ }
  if (res.status === 403) return 'Session expired or CSRF check failed — please refresh the page and try again.';
  return `Request failed (HTTP ${res.status}).`;
}

const colormaps = {
  'ph'            : [{ max: 4.5, hex: '#D32F2F' }, { max: 5.5, hex: '#E67E22' }, { max: 6.5, hex: '#F1C40F' }, { max: 7.5, hex: '#27AE60' }, { max: 8.5, hex: '#2980B9' }, { max: Infinity, hex: '#17202A' }],
  'ec'            : [{ max: 0.2, hex: '#0B2545' }, { max: 0.8, hex: '#134074' }, { max: 1.6, hex: '#8DA9C4' }, { max: 3.2, hex: '#EEB902' }, { max: 6.4, hex: '#D05A02' }, { max: Infinity, hex: '#4A0000' }],
  'n'             : [{ max: 50, hex: '#E8F5E9' }, { max: 100, hex: '#A5D6A7' }, { max: 200, hex: '#4CAF50' }, { max: 300, hex: '#2E7D32' }, { max: 400, hex: '#1B5E20' }, { max: Infinity, hex: '#08250A' }],
  'p'             : [{ max: 5, hex: '#FCE4EC' }, { max: 10, hex: '#F8BBD0' }, { max: 20, hex: '#EC407A' }, { max: 40, hex: '#C2185B' }, { max: 60, hex: '#880E4F' }, { max: Infinity, hex: '#4A0025' }],
  'k'             : [{ max: 80, hex: '#FFF8E1' }, { max: 120, hex: '#FFE082' }, { max: 200, hex: '#FFB74D' }, { max: 300, hex: '#E65100' }, { max: 500, hex: '#9E2A2B' }, { max: Infinity, hex: '#3E0F05' }],
  'organic_carbon': [{ max: 0.25, hex: '#F5EBE6' }, { max: 0.5, hex: '#D7CCC8' }, { max: 0.75, hex: '#BCAAA4' }, { max: 1.5, hex: '#6D4C41' }, { max: 3.0, hex: '#3E2723' }, { max: Infinity, hex: '#1A0B05' }],
  's'             : [{ max: 5, hex: '#FFFDE7' }, { max: 10, hex: '#FFF59D' }, { max: 20, hex: '#FBC02D' }, { max: 40, hex: '#F57F17' }, { max: 80, hex: '#827717' }, { max: Infinity, hex: '#333008' }],
  'ca'            : [{ max: 0.75, hex: '#E0F7FA' }, { max: 1.5, hex: '#80DEEA' }, { max: 3.0, hex: '#26C6DA' }, { max: 5.0, hex: '#00838F' }, { max: 10.0, hex: '#005662' }, { max: Infinity, hex: '#00262B' }],
  'mg'            : [{ max: 0.5, hex: '#F1F8E9' }, { max: 1.0, hex: '#C5E1A5' }, { max: 2.0, hex: '#9CCC65' }, { max: 3.0, hex: '#689F38' }, { max: 6.0, hex: '#33691E' }, { max: Infinity, hex: '#142A0C' }],
  'fe'            : [{ max: 2, hex: '#FFEBEE' }, { max: 4.5, hex: '#FF8A80' }, { max: 9, hex: '#D32F2F' }, { max: 20, hex: '#B71C1C' }, { max: 50, hex: '#7F0000' }, { max: Infinity, hex: '#3B0000' }],
  'zn'            : [{ max: 0.5, hex: '#ECEFF1' }, { max: 1.0, hex: '#B0BEC5' }, { max: 2.0, hex: '#78909C' }, { max: 5.0, hex: '#455A64' }, { max: 10.0, hex: '#263238' }, { max: Infinity, hex: '#0D1417' }],
  'cu'            : [{ max: 0.2, hex: '#E0F2F1' }, { max: 1.0, hex: '#80CBC4' }, { max: 2.5, hex: '#26A69A' }, { max: 5.0, hex: '#00695C' }, { max: 10.0, hex: '#004D40' }, { max: Infinity, hex: '#00251E' }],
  'b'             : [{ max: 0.25, hex: '#E8EAF6' }, { max: 0.5, hex: '#9FA8DA' }, { max: 1.0, hex: '#5C6BC0' }, { max: 2.0, hex: '#3F51B5' }, { max: 4.0, hex: '#1A237E' }, { max: Infinity, hex: '#0B0C24' }],
  'mn'            : [{ max: 2.0, hex: '#F5F5F5' }, { max: 5.0, hex: '#E0E0E0' }, { max: 10.0, hex: '#BDBDBD' }, { max: 25.0, hex: '#757575' }, { max: 50.0, hex: '#424242' }, { max: Infinity, hex: '#111111' }],
};

function makeGetColor(key) {
  return (val) => {
    const cmap = colormaps[key];
    for (const step of cmap) { if (val <= step.max) return step.hex; }
    return cmap[cmap.length - 1].hex;
  };
}

const PARAMETERS = {
  ph:             { name: 'ph', label: 'Soil pH', unit: '', getColor: makeGetColor('ph'), legendGradient: 'linear-gradient(to right, #D32F2F, #E67E22, #F1C40F, #27AE60, #2980B9, #17202A)' },
  ec:             { name: 'ec', label: 'Electrical Conductivity', unit: 'dS/m', getColor: makeGetColor('ec'), legendGradient: 'linear-gradient(to right, #0B2545, #134074, #8DA9C4, #EEB902, #D05A02, #4A0000)' },
  n:              { name: 'n', label: 'Nitrogen', unit: 'kg/ha', getColor: makeGetColor('n'), legendGradient: 'linear-gradient(to right, #E8F5E9, #A5D6A7, #4CAF50, #2E7D32, #1B5E20, #08250A)' },
  p:              { name: 'p', label: 'Phosphorus', unit: 'kg/ha', getColor: makeGetColor('p'), legendGradient: 'linear-gradient(to right, #FCE4EC, #F8BBD0, #EC407A, #C2185B, #880E4F, #4A0025)' },
  k:              { name: 'k', label: 'Potassium', unit: 'kg/ha', getColor: makeGetColor('k'), legendGradient: 'linear-gradient(to right, #FFF8E1, #FFE082, #FFB74D, #E65100, #9E2A2B, #3E0F05)' },
  organic_carbon: { name: 'organic_carbon', label: 'Organic Carbon', unit: '%', getColor: makeGetColor('organic_carbon'), legendGradient: 'linear-gradient(to right, #F5EBE6, #D7CCC8, #BCAAA4, #6D4C41, #3E2723, #1A0B05)' },
  s:              { name: 's', label: 'Sulphur', unit: 'ppm', getColor: makeGetColor('s'), legendGradient: 'linear-gradient(to right, #FFFDE7, #FFF59D, #FBC02D, #F57F17, #827717, #333008)' },
  ca:             { name: 'ca', label: 'Calcium', unit: 'meq/100g', getColor: makeGetColor('ca'), legendGradient: 'linear-gradient(to right, #E0F7FA, #80DEEA, #26C6DA, #00838F, #005662, #00262B)' },
  mg:             { name: 'mg', label: 'Magnesium', unit: 'meq/100g', getColor: makeGetColor('mg'), legendGradient: 'linear-gradient(to right, #F1F8E9, #C5E1A5, #9CCC65, #689F38, #33691E, #142A0C)' },
  fe:             { name: 'fe', label: 'Iron', unit: 'ppm', getColor: makeGetColor('fe'), legendGradient: 'linear-gradient(to right, #FFEBEE, #FF8A80, #D32F2F, #B71C1C, #7F0000, #3B0000)' },
  zn:             { name: 'zn', label: 'Zinc', unit: 'ppm', getColor: makeGetColor('zn'), legendGradient: 'linear-gradient(to right, #ECEFF1, #B0BEC5, #78909C, #455A64, #263238, #0D1417)' },
  cu:             { name: 'cu', label: 'Copper', unit: 'ppm', getColor: makeGetColor('cu'), legendGradient: 'linear-gradient(to right, #E0F2F1, #80CBC4, #26A69A, #00695C, #004D40, #00251E)' },
  b:              { name: 'b', label: 'Boron', unit: 'ppm', getColor: makeGetColor('b'), legendGradient: 'linear-gradient(to right, #E8EAF6, #9FA8DA, #5C6BC0, #3F51B5, #1A237E, #0B0C24)' },
  mn:             { name: 'mn', label: 'Manganese', unit: 'ppm', getColor: makeGetColor('mn'), legendGradient: 'linear-gradient(to right, #F5F5F5, #E0E0E0, #BDBDBD, #757575, #424242, #111111)' },
};

const getShortLabel = (p) => {
  const map = { ph: 'pH', ec: 'EC', n: 'N', p: 'P', k: 'K', organic_carbon: 'Org C', s: 'S', ca: 'Ca', mg: 'Mg', fe: 'Fe', zn: 'Zn', cu: 'Cu', b: 'B', mn: 'Mn' };
  return map[p.name] || p.label;
};

// ── Geo Lenz layer metadata (same grouping / class wording as SoilMap) ─────
const LAYER_META = {
  n:  { sym: 'N',  desc: 'Available nitrogen',          grp: 'macro' },
  p:  { sym: 'P',  desc: 'Plant-available phosphorus',  grp: 'macro' },
  k:  { sym: 'K',  desc: 'Exchangeable potassium',      grp: 'macro' },
  s:  { sym: 'S',  desc: 'Available sulphur',           grp: 'micro' },
  ca: { sym: 'Ca', desc: 'Exchangeable calcium',        grp: 'micro' },
  mg: { sym: 'Mg', desc: 'Exchangeable magnesium',      grp: 'micro' },
  fe: { sym: 'Fe', desc: 'DTPA iron',                   grp: 'micro' },
  zn: { sym: 'Zn', desc: 'DTPA zinc',                   grp: 'micro' },
  cu: { sym: 'Cu', desc: 'DTPA copper',                 grp: 'micro' },
  b:  { sym: 'B',  desc: 'Hot-water boron',             grp: 'micro' },
  mn: { sym: 'Mn', desc: 'DTPA manganese',              grp: 'micro' },
  ph: { sym: 'pH', desc: 'Acidity / alkalinity',        grp: 'soil' },
  ec: { sym: 'EC', desc: 'Soluble salts / salinity',    grp: 'soil' },
  organic_carbon: { sym: 'OC', desc: 'Total organic carbon', grp: 'soil' },
};
const LAYER_GROUPS = [['macro', 'Macronutrients', 'N-P-K'], ['micro', 'Secondary', '& Micro'], ['soil', 'Soil', 'Properties']];
const QUICK_LAYERS = ['n', 'p', 'k', 'ph', 'organic_carbon'];
const CLASS_NAMES = {
  ph:   ['Strongly Acidic', 'Acidic', 'Slightly Acidic', 'Neutral', 'Alkaline', 'Strongly Alkaline'],
  ec:   ['Very Low', 'Low', 'Normal', 'Moderate', 'High', 'Very High'],
  _def: ['Very Low', 'Low', 'Medium', 'Optimal', 'High', 'Very High'],
};
const BAD_CLASSES = { ph: [0, 1, 5], ec: [4, 5], _def: [0, 1] };
let lyrGroup = 'macro';
let lmMin = null;          // metrics card collapsed? null → auto (collapsed on small screens)
let rasterStates = [];     // per-plot value grids used by the hover readout
let rasterFetchToken = 0;  // drops stale raster responses after a fast layer switch

const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const classNames = (param) => CLASS_NAMES[param] || CLASS_NAMES._def;
const badClasses = (param) => BAD_CLASSES[param] || BAD_CLASSES._def;
function classIdx(v, scale) { for (let i = 0; i < scale.length; i++) if (v <= scale[i].max) return i; return scale.length - 1; }
function scaleLo(param) { return param === 'ph' ? 3.5 : 0; }
function scaleBounds(scale, i, param) {
  const lo = i === 0 ? scaleLo(param) : scale[i - 1].max;
  const hi = scale[i].max === Infinity ? lo + (lo - (i > 1 ? scale[i - 2].max : scaleLo(param))) : scale[i].max;
  return [lo, hi];
}
function hexToRgb(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
// Smooth colour: interpolate between class-centre stops so the raster reads as a continuous surface.
function smoothRgb(v, scale, param) {
  const stops = scale.map((st, i) => { const [lo, hi] = scaleBounds(scale, i, param); return [(lo + hi) / 2, hexToRgb(st.hex)]; });
  if (v <= stops[0][0]) return stops[0][1];
  for (let i = 1; i < stops.length; i++) {
    if (v <= stops[i][0]) {
      const t = (v - stops[i - 1][0]) / (stops[i][0] - stops[i - 1][0]), a = stops[i - 1][1], b = stops[i][1];
      return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
    }
  }
  return stops[stops.length - 1][1];
}
function rangeTxt(param) {
  const sc = colormaps[param]; if (!sc) return '';
  const fin = sc.filter(x => x.max !== Infinity);
  return `${param === 'ph' ? sc[0].max : 0}–${fin[fin.length - 1].max}+ ${PARAMETERS[param].unit}`.trim();
}
function fmtV(v) { return (v === null || v === undefined || isNaN(v)) ? '—' : (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2)); }
// Average of the sample points' values for a parameter (what the layer card shows).
function sampleStats(param) {
  const vals = points.map(pt => pt.parameters && pt.parameters[param]).filter(v => typeof v === 'number' && !isNaN(v));
  if (!vals.length) return { n: 0, avg: NaN };
  return { n: vals.length, avg: vals.reduce((a, b) => a + b, 0) / vals.length };
}

// Compact color-coded stat grid, used anywhere a full parameter set needs
// to be previewed (reading detail expand, point map popup, add-form preview).
function buildParamGrid(parameters) {
  const order = Object.keys(PARAMETERS);
  const keys  = Object.keys(parameters).sort((a, b) => order.indexOf(a) - order.indexOf(b));
  const chips = keys.map(key => {
    const config  = PARAMETERS[key] || { label: key, unit: '' };
    const val     = parameters[key];
    const color   = (val !== undefined && val !== null && config.getColor) ? config.getColor(val) : '#9ca3af';
    const display = (typeof val === 'number') ? (Number.isInteger(val) ? val : val.toFixed(2)) : val;
    return `
      <div class="param-chip">
        <span class="param-chip-label"><span class="param-chip-dot" style="background:${color};"></span>${getShortLabel(config)}</span>
        <span class="param-chip-value">${display}<span class="param-chip-unit">${config.unit || ''}</span></span>
      </div>`;
  }).join('');
  return `<div class="param-grid">${chips}</div>`;
}

// ── Global App State ─────────────────────────────────────────────────────────
let points          = [];    // every point for this device (flat list)
let plots           = [];    // every plot (boundary) for this device
let plotsById       = {};
let activeParameter = 'ph';
let rasterCache     = {};
let allRasters      = {};

let readingsQuery = '';
let readingsPage = 1;
let readingsData = { results: [], num_pages: 1, count: 0 };

// pendingAddMode: null | 'linking' | 'manual'
let pendingAddMode  = null;
let pendingReading  = null;
let pendingGeometry = null;
let multiAddCount   = 0;

// pointFormMode (for edit only now): 'editing-linked' | 'editing-manual'
let pointFormMode = null;
let pointFormContext = {};

let   mapInstance      = null;
const plotsLayerGroup  = L.featureGroup();
const pointsLayerGroup = L.featureGroup();
const rasterLayerGroup = L.featureGroup();
let   canvasRenderer   = null;
let   hasLocated       = false;
let   pointMarkersById = {};

let pointsListContainer, pointFormCard;
let readingsListContainer, readingsSearchInput, readingsPager;
let parameterTabsContainer, pointForm, pointFormErrorBanner;

// When embedded from a specific reading's detail page (?highlight_reading=<id>),
// filter the readings list to it and point out its sample point on the map (or
// prompt to add one) so it's obvious which point corresponds to "this" reading.
const highlightReadingId = new URLSearchParams(window.location.search).get('highlight_reading');

document.addEventListener('DOMContentLoaded', async () => {
  cacheDOM();
  initMap();
  initParameterTabs();
  bindGlobalEvents();
  initCoordSearch();
  if (highlightReadingId) {
    readingsQuery = highlightReadingId;
    if (readingsSearchInput) readingsSearchInput.value = highlightReadingId;
  }
  await Promise.all([fetchPlots(), fetchPoints(), fetchReadings()]);
  if (highlightReadingId) applyReadingHighlight();
  else fitToAllPlots();
});

function applyReadingHighlight() {
  const rid    = parseInt(highlightReadingId, 10);
  const point  = points.find(p => p.reading_id === rid);
  const banner = document.createElement('div');
  banner.style.cssText = 'background:var(--accent-soft, #e3f2fd);border:1px solid var(--accent, #90caf9);border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:13px;line-height:1.5;';
  if (point && point.coordinates) {
    banner.innerHTML = `<i class="fas fa-map-marker-alt me-1"></i> Showing the map for <strong>Reading #${rid}</strong> — its sample point is highlighted below.`;
    flyToLocation(point.coordinates.lat, point.coordinates.lon);
    const marker = pointMarkersById[point.id];
    if (marker) setTimeout(() => marker.openPopup(), 400);
  } else {
    banner.innerHTML = `<i class="fas fa-info-circle me-1"></i> Showing the map for <strong>Reading #${rid}</strong> — it hasn't been added to this map yet. Find it in "All Readings" below and click "+ Add to Map".`;
  }
  const sidebarContent = document.querySelector('.sidebar-content');
  if (sidebarContent) sidebarContent.insertBefore(banner, sidebarContent.firstChild);
}

function cacheDOM() {
  pointsListContainer    = document.getElementById('points-list');
  readingsListContainer  = document.getElementById('readings-list');
  readingsSearchInput    = document.getElementById('readings-search-input');
  readingsPager          = document.getElementById('readings-pager');
  pointFormCard          = document.getElementById('point-form-card');
  parameterTabsContainer = document.getElementById('parameter-tabs');
  pointForm              = document.getElementById('point-form');
  pointFormErrorBanner   = document.getElementById('point-form-error-banner');
}

function initMap() {
  mapInstance = L.map('map', { center: [20.5, 78.9], zoom: 5, zoomControl: false });
  canvasRenderer = L.canvas();

  const fetchIPLocationFallback = () => {
    fetch('https://ipapi.co/json/')
      .then(res => { if (!res.ok) throw new Error('bad status'); return res.json(); })
      .then(data => {
        if (data && data.latitude && data.longitude && !hasLocated) {
          hasLocated = true;
          mapInstance.setView([data.latitude, data.longitude], 12);
        }
      })
      .catch(() => {});
  };

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (position) => { if (hasLocated) return; hasLocated = true; mapInstance.setView([position.coords.latitude, position.coords.longitude], 14); },
      () => fetchIPLocationFallback(),
      { enableHighAccuracy: false, timeout: 5000, maximumAge: 30000 }
    );
  } else {
    fetchIPLocationFallback();
  }

  L.control.zoom({ position: 'topright' }).addTo(mapInstance);

  // Free, keyless Esri tiles (Google tile URLs are not permitted without an API key)
  const googleRoadmap = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', { attribution: 'Tiles &copy; Esri', maxNativeZoom: 19, maxZoom: 20 });
  const googleHybrid = L.layerGroup([
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Tiles &copy; Esri', maxNativeZoom: 18, maxZoom: 20 }),
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', { maxNativeZoom: 18, maxZoom: 20 })
  ]);
  googleHybrid.addTo(mapInstance);
  L.control.layers({ 'Satellite (Hybrid)': googleHybrid, 'Street Map': googleRoadmap }, null, { position: 'topright' }).addTo(mapInstance);

  plotsLayerGroup.addTo(mapInstance);
  pointsLayerGroup.addTo(mapInstance);
  rasterLayerGroup.addTo(mapInstance);

  // No always-on toolbar — drawing only starts when "+ Add to Map" / "+ Manual Point" is clicked.
  mapInstance.pm.addControls({
    position: 'topleft', drawMarker: false, drawCircleMarker: false, drawPolyline: false,
    drawRectangle: false, drawCircle: false, drawText: false, drawPolygon: false,
    editMode: false, dragMode: false, cutPolygon: false, removalMode: false,
  });

  mapInstance.pm.setGlobalOptions({ pathOptions: { color: '#2d6a4f', weight: 3, fillOpacity: 0.1 } });

  mapInstance.on('pm:create', (e) => {
    const layer = e.layer;
    pendingGeometry = layer.toGeoJSON().geometry;
    layer.remove();
    mapInstance.pm.disableDraw('Polygon');
    document.getElementById('draw-hint').style.display = 'none';
    openConfirmForm();
  });
}

function initParameterTabs() {
  lyrGroup = LAYER_META[activeParameter].grp;
  const tabs = document.getElementById('lyr-tabs');
  tabs.innerHTML = LAYER_GROUPS.map(([g, a, b]) =>
    `<button type="button" class="lyr-tab${g === lyrGroup ? ' active' : ''}" data-g="${g}">${a}<small>${b}</small></button>`).join('');
  tabs.querySelectorAll('.lyr-tab').forEach(btn => btn.addEventListener('click', () => setLyrGroup(btn.dataset.g)));
  parameterTabsContainer.addEventListener('click', (e) => {
    const card = e.target.closest('.lyr-card');
    if (card) setActiveParameter(card.dataset.k);
  });
  renderLayerCards();
}

function setLyrGroup(g) {
  lyrGroup = g;
  document.querySelectorAll('.lyr-tab').forEach(b => b.classList.toggle('active', b.dataset.g === g));
  renderLayerCards();
}

function renderLayerCards() {
  parameterTabsContainer.innerHTML = Object.keys(PARAMETERS).filter(k => LAYER_META[k].grp === lyrGroup).map((k, i) => {
    const p = PARAMETERS[k], sc = colormaps[k], st = sampleStats(k), active = k === activeParameter;
    const ci = st.n ? classIdx(st.avg, sc) : -1;
    const rating = ci < 0 ? '' : `<span class="lyr-rate" style="--c:${sc[ci].hex}">${classNames(k)[ci]}</span>`;
    const val = st.n ? `<b>${fmtV(st.avg)}</b> ${p.unit} ${rating}` : `<span style="opacity:.8">No samples yet</span>`;
    return `<button type="button" class="lyr-card${active ? ' active' : ''}${st.n ? '' : ' no-data'}" data-k="${k}" style="animation-delay:${i * 0.04}s" title="${esc(p.label)}">
        <span class="lyr-radio"></span>
        <span class="lyr-sym" style="--c:${sc[Math.min(3, sc.length - 1)].hex}">${LAYER_META[k].sym}</span>
        <span class="lyr-main">
          <span class="lyr-name" style="display:block">${p.label}</span>
          <span class="lyr-desc" style="display:block">${LAYER_META[k].desc}${p.unit ? ' (' + p.unit + ')' : ''}${st.n ? ' · ' + st.n + ' sample' + (st.n === 1 ? '' : 's') : ''}</span>
          <span class="lyr-val" style="display:block">${val}</span>
        </span>
        <span class="lyr-side">
          <span class="lyr-tag" style="display:block">${active ? '<i class="fas fa-eye"></i> VIEWING' : '<i class="fas fa-rotate"></i> Click to view'}</span>
          <span class="lyr-grad" style="display:block;background:${p.legendGradient.replace('to right', '90deg')}"></span>
          <span class="lyr-range" style="display:block">${rangeTxt(k)}</span>
        </span>
      </button>`;
  }).join('');
}

function setActiveParameter(param) {
  if (!PARAMETERS[param]) return;
  activeParameter = param;
  if (LAYER_META[param].grp !== lyrGroup) setLyrGroup(LAYER_META[param].grp); else renderLayerCards();
  renderPointsOnMap();
  fetchAllRasters();
}

// ── Sidebar collapse (hiding the panel never clears map data) ──────────────
function setSidebarCollapsed(collapsed) {
  document.getElementById('root').classList.toggle('sb-collapsed', collapsed);
  setTimeout(() => mapInstance && mapInstance.invalidateSize({ pan: false }), 80);
  // after the slide finishes: re-measure the map and let theme.js reposition its scroll hints
  setTimeout(() => window.dispatchEvent(new Event('resize')), 400);
}

// ── Minimize buttons (Soil Layers, Added to Map, All Readings, legend) ───
// Remembered per browser; a minimized Soil Layers card still shows the active layer.
function initMinimizers() {
  document.querySelectorAll('.gl-min-btn').forEach(btn => {
    const box = btn.closest('.card, .legend-panel'), key = 'geolenz-min-' + btn.dataset.minKey;
    const apply = (min) => {
      box.classList.toggle('min', min);
      btn.setAttribute('aria-expanded', String(!min));
      btn.title = min ? 'Expand' : 'Minimize';
      btn.setAttribute('aria-label', btn.title);
    };
    let saved = null;
    try { saved = localStorage.getItem(key); } catch (e) { /* storage blocked — just don't remember */ }
    apply(saved === '1');
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const min = !box.classList.contains('min');
      apply(min);
      try { localStorage.setItem(key, min ? '1' : '0'); } catch (err) { /* ignore */ }
    });
  });
}

function updateStats() {
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  set('stat-points', points.length);
  set('stat-plots', plots.length);
  set('stat-readings', readingsData.count || 0);
}

function bindGlobalEvents() {
  initMinimizers();
  document.getElementById('sidebar-collapse-btn').addEventListener('click', () => setSidebarCollapsed(true));
  document.getElementById('sidebar-reopen-btn').addEventListener('click', () => setSidebarCollapsed(false));
  if (window.innerWidth <= 900) setSidebarCollapsed(true);
  ['lyr-bar', 'lyr-metrics', 'legend-panel'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { L.DomEvent.disableClickPropagation(el); L.DomEvent.disableScrollPropagation(el); }
  });
  mapInstance.on('mousemove', onRasterHover);
  mapInstance.on('mouseout', () => document.getElementById('lyr-tip').classList.remove('show'));
  document.getElementById('cancel-point-btn').addEventListener('click', cancelDraw);
  pointForm.addEventListener('submit', handlePointFormSubmit);

  let searchDebounce = null;
  readingsSearchInput.addEventListener('input', function () {
    clearTimeout(searchDebounce);
    const val = this.value;
    searchDebounce = setTimeout(() => { readingsQuery = val.trim(); readingsPage = 1; fetchReadings(); }, 350);
  });
}

// ── Lat/long search ──────────────────────────────────────────────────────────
// Accepts "lat, lon" / "lat lon" (as copied from Google Maps or a reading's
// Location field), flies there and drops a marker; ✕ removes it.
let coordSearchMarker = null;

function initCoordSearch() {
  const form     = document.getElementById('coord-search');
  const input    = document.getElementById('coord-search-input');
  const clearBtn = document.getElementById('coord-search-clear');
  const errorEl  = document.getElementById('coord-search-error');
  if (!form) return;

  // Keep map drag/zoom from firing while typing or clicking in the box.
  L.DomEvent.disableClickPropagation(form);
  L.DomEvent.disableScrollPropagation(form);

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const parts = input.value.trim().split(/[\s,]+/).filter(Boolean).map(Number);
    const [lat, lon] = parts;
    if (parts.length !== 2 || !Number.isFinite(lat) || !Number.isFinite(lon)) {
      errorEl.textContent = 'Enter latitude and longitude, e.g. 16.1667, 74.6167';
      return;
    }
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      errorEl.textContent = 'Latitude must be -90 to 90 and longitude -180 to 180.';
      return;
    }
    errorEl.textContent = '';
    if (coordSearchMarker) coordSearchMarker.remove();
    coordSearchMarker = L.marker([lat, lon]).addTo(mapInstance)
      .bindPopup(`<strong>${lat.toFixed(6)}, ${lon.toFixed(6)}</strong>`).openPopup();
    clearBtn.style.display = '';
    mapInstance.flyTo([lat, lon], 17, { duration: 1.2 });
  });

  clearBtn.addEventListener('click', () => {
    if (coordSearchMarker) { coordSearchMarker.remove(); coordSearchMarker = null; }
    input.value = '';
    errorEl.textContent = '';
    clearBtn.style.display = 'none';
  });
}

function flyToLocation(lat, lon) {
  if (!lat || !lon) return;
  mapInstance.flyTo([lat, lon], 17, { duration: 1.2 });
}

// Open on the mapped fields (not wherever the browser's GPS happens to be),
// so the layers are visible straight away.
function fitToAllPlots() {
  const b = plotsLayerGroup.getBounds();
  if (b.isValid()) { hasLocated = true; mapInstance.fitBounds(b, { padding: [60, 60], maxZoom: 18 }); }
  else if (points.length) {
    const pt = points.find(p => p.coordinates);
    if (pt) mapInstance.setView([pt.coordinates.lat, pt.coordinates.lon], 16);
  }
}

function flyToPlot(plotId) {
  const plot = plotsById[plotId];
  if (!plot) return;
  const layer = L.geoJSON(plot.geometry);
  mapInstance.fitBounds(layer.getBounds(), { padding: [50, 50] });
}

// ── Plots (boundaries — created automatically alongside each point) ────────

async function fetchPlots() {
  try {
    const res = await fetch(URLS.plots);
    if (res.ok) {
      plots = await res.json();
      plotsById = {};
      plots.forEach(p => { plotsById[p.id] = p; });
      updateStats();
      renderPlotsOnMap();
      fetchAllRasters();
    }
  } catch (e) { console.error('Error fetching plots:', e); }
}

function renderPlotsOnMap() {
  plotsLayerGroup.clearLayers();
  plots.forEach(plot => {
    const layer = L.geoJSON(plot.geometry, { style: { color: '#ffffff', weight: 2.5, opacity: 0.95, dashArray: '6,5', fillOpacity: 0 } });
    // Label each boundary with its name so overlapping/nearby boxes for
    // different readings can be told apart at a glance on the map itself.
    layer.bindTooltip(plot.name, { permanent: true, direction: 'center', className: 'plot-label-tooltip' });
    plotsLayerGroup.addLayer(layer);
  });
}

async function deletePlotSilently(plotId) {
  try {
    await fetch(URLS.plotDetail(plotId), { method: 'DELETE', headers: { 'X-CSRFToken': getCsrf() } });
  } catch (e) { console.error('Error deleting plot:', e); }
}

// ── Readings search list ("All Readings") ───────────────────────────────────

async function fetchReadings() {
  try {
    const params = new URLSearchParams({ page: readingsPage, page_size: 20 });
    if (readingsQuery) params.set('q', readingsQuery);
    const res = await fetch(`${URLS.readings}?${params.toString()}`);
    if (res.ok) {
      readingsData = await res.json();
      updateStats();
      renderReadingsList();
    }
  } catch (e) { console.error('Error fetching readings:', e); }
}

function renderReadingsList() {
  readingsListContainer.innerHTML = '';
  if (readingsData.results.length === 0) {
    readingsListContainer.innerHTML = `<div style="color: var(--text-muted); font-size: 13px; text-align: center; margin-top: 12px;">No readings match.</div>`;
    readingsPager.innerHTML = '';
    return;
  }
  readingsData.results.forEach(r => {
    const wrap = document.createElement('div');

    const item = document.createElement('div');
    item.className = 'list-item';
    const hasCoords = r.latitude && r.longitude;
    const pointIds = r.point_ids || [];
    item.innerHTML = `
      <div style="min-width:0;">
        <div class="list-item-title" style="font-size: 13px;">
          <span class="reading-expand-arrow">&#9654;</span> #${r.id} — ${r.crop_type || 'Reading'}
          ${pointIds.length ? `<span class="badge-linked" style="margin-left:4px;">${pointIds.length} on map</span>` : ''}
        </div>
        <div class="list-item-subtitle">${r.area_name || ''} ${hasCoords ? `&middot; ${r.latitude.toFixed(4)}, ${r.longitude.toFixed(4)}` : '&middot; no GPS'}</div>
      </div>
      <div class="list-item-actions">
        <button class="btn btn-sm btn-primary reading-action-btn" data-reading-id="${r.id}">+ Add to Map</button>
      </div>`;

    const detail = document.createElement('div');
    detail.className = 'reading-detail-panel';
    detail.style.display = 'none';
    let detailHtml = buildParamGrid(r.parameters);
    if (pointIds.length) {
      detailHtml += `<div style="margin-top:8px;padding-top:6px;border-top:1px solid var(--border-color);font-size:11px;color:var(--text-secondary);">
        Positions on map: ${pointIds.map(pid => `<a href="#" class="edit-existing-position-link" data-point-id="${pid}" style="color:var(--accent);">#${pid}</a>`).join(', ')}
      </div>`;
    }
    detail.innerHTML = detailHtml;
    detail.querySelectorAll('.edit-existing-position-link').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        openEditPosition(parseInt(link.getAttribute('data-point-id'), 10));
      });
    });

    item.addEventListener('click', (e) => {
      if (e.target.closest('button')) return;
      const arrow = item.querySelector('.reading-expand-arrow');
      const open = detail.style.display !== 'none';
      detail.style.display = open ? 'none' : 'block';
      arrow.classList.toggle('open', !open);
      if (!open && hasCoords) flyToLocation(r.latitude, r.longitude);
    });
    item.querySelector('.reading-action-btn').addEventListener('click', () => startLinkedPointDraw(r));

    wrap.appendChild(item);
    wrap.appendChild(detail);
    readingsListContainer.appendChild(wrap);
  });

  readingsPager.innerHTML = `
    <span>Page ${readingsData.page} of ${readingsData.num_pages} (${readingsData.count} total)</span>
    <span>
      <button id="readings-prev" ${readingsData.page <= 1 ? 'disabled' : ''}>&lsaquo; Prev</button>
      <button id="readings-next" ${readingsData.page >= readingsData.num_pages ? 'disabled' : ''}>Next &rsaquo;</button>
    </span>`;
  const prevBtn = document.getElementById('readings-prev');
  const nextBtn = document.getElementById('readings-next');
  if (prevBtn) prevBtn.addEventListener('click', () => { readingsPage--; fetchReadings(); });
  if (nextBtn) nextBtn.addEventListener('click', () => { readingsPage++; fetchReadings(); });
}

// ── Points ("Added to Map") ──────────────────────────────────────────────────

async function fetchPoints() {
  try {
    const res = await fetch(URLS.allPoints);
    if (res.ok) {
      points = await res.json();
      updateStats();
      renderPointsList();
      renderPointsOnMap();
      renderLayerCards();
    }
  } catch (e) { console.error('Error fetching points:', e); }
}

function renderPointsList() {
  pointsListContainer.innerHTML = '';
  if (points.length === 0) {
    pointsListContainer.innerHTML = `<div style="color: var(--text-muted); font-size: 13px; text-align: center; margin-top: 12px;">
      Nothing added yet. Click "+ Add to Map" on a reading, or "+ Manual Point" below, then draw a boundary on the map.
    </div>`;
    return;
  }
  points.forEach(point => {
    const item = document.createElement('div');
    item.className = 'list-item';
    const badge = point.reading_id ? '<span class="badge-linked">Linked</span>' : '<span class="badge-manual">Manual</span>';
    item.innerHTML = `
      <div>
        <div class="list-item-title" style="font-size: 13px;">${badge} ${point.sample_date}</div>
        <div class="list-item-subtitle">${point.plot_name || 'Unnamed area'}${point.reading_id ? ' &middot; reading #' + point.reading_id : ''}</div>
      </div>
      <div class="list-item-actions">
        <button class="btn btn-secondary btn-sm edit-point-btn" style="padding: 4px 8px;">Edit</button>
        <button class="btn btn-danger btn-sm delete-point-btn" style="padding: 4px 8px;">Delete</button>
      </div>`;
    item.addEventListener('click', (e) => {
      if (e.target.closest('button')) return;
      if (point.plot) flyToPlot(point.plot);
      else if (point.coordinates) flyToLocation(point.coordinates.lat, point.coordinates.lon);
    });
    item.querySelector('.edit-point-btn').addEventListener('click', () => openEditPosition(point.id));
    item.querySelector('.delete-point-btn').addEventListener('click', () => handleDeletePoint(point));
    pointsListContainer.appendChild(item);
  });
}

function renderPointsOnMap() {
  pointsLayerGroup.clearLayers();
  pointMarkersById = {};
  const paramConfig = PARAMETERS[activeParameter];
  if (!paramConfig) return;

  points.forEach(point => {
    if (!point.coordinates) return;
    const lat = point.coordinates.lat, lon = point.coordinates.lon;
    const val = point.parameters[activeParameter];
    const formattedVal = (val !== undefined && val !== null) ? val.toFixed(2) : 'N/A';

    const hasVal = val !== undefined && val !== null;
    const dotColor = hasVal ? paramConfig.getColor(val) : '#9ca3af';
    const marker = L.circleMarker([lat, lon], {
      radius: 7, color: '#fff', weight: 2.5, fillColor: dotColor, fillOpacity: 1, className: 'soil-sample-pt',
    });
    const ci = hasVal ? classIdx(val, colormaps[activeParameter]) : -1;
    marker.bindTooltip(`<div class="sp-tip"><b>${formattedVal} ${paramConfig.unit || ''}</b>${ci >= 0 ? ` · <span style="color:${dotColor}">${classNames(activeParameter)[ci]}</span>` : ''}</div>`, {
      direction: 'top', offset: [0, -8],
    });

    marker.bindPopup(`
      <div class="ticket-popup">
        <h4 style="margin:0 0 6px 0;font-size:13px;font-weight:600;border-bottom:1px solid var(--border-color);padding-bottom:4px;">
          ${point.plot_name || 'Soil Sample'} ${point.reading_id ? '(reading #' + point.reading_id + ')' : '(manual)'}
        </h4>
        <div style="font-size:11px;color:var(--text-secondary);margin-bottom:8px;">Date: ${point.sample_date}</div>
        ${buildParamGrid(point.parameters)}
        ${point.notes ? `<div style="margin-top:8px;font-size:11px;font-style:italic;color:var(--text-secondary)">Notes: ${point.notes}</div>` : ''}
      </div>`, { maxWidth: 320, minWidth: 260 });

    pointsLayerGroup.addLayer(marker);
    pointMarkersById[point.id] = marker;
  });
}

async function handleDeletePoint(point) {
  if (!confirm('Delete this point (and its boundary)?')) return;
  try {
    const res = await fetch(URLS.pointDetail(point.id), { method: 'DELETE', headers: { 'X-CSRFToken': getCsrf() } });
    if (res.ok) {
      if (point.plot) await deletePlotSilently(point.plot);
      points = points.filter(p => p.id !== point.id);
      updateStats();
      renderLayerCards();
      renderPointsList();
      renderPointsOnMap();
      fetchPlots();
      fetchReadings();
    }
  } catch (e) { console.error('Error deleting point:', e); }
}

// ── Rasters ──────────────────────────────────────────────────────────────────

async function fetchAllRasters() {
  const token = ++rasterFetchToken, param = activeParameter;
  if (plots.length === 0) { allRasters = {}; renderRastersOnMap(); return; }
  const loading = document.getElementById('raster-loading');
  const needsFetch = plots.some(pl => !rasterCache[`${pl.id}-${param}`]);
  if (needsFetch) loading.classList.add('show');
  const newRasters = {};
  await Promise.all(plots.map(async (plot) => {
    const cacheKey = `${plot.id}-${param}`;
    if (rasterCache[cacheKey]) { newRasters[plot.id] = rasterCache[cacheKey]; return; }
    try {
      const res = await fetch(`${URLS.raster(plot.id)}?parameter=${param}&resolution=60`);
      if (res.ok) {
        const data = await res.json();
        rasterCache[cacheKey] = data;
        newRasters[plot.id] = data;
      }
    } catch (e) { console.error(`Error fetching raster for plot ${plot.id}:`, e); }
  }));
  if (token !== rasterFetchToken) return;   // the user already switched to another layer
  loading.classList.remove('show');
  allRasters = newRasters;
  renderRastersOnMap();
}

// Rebuild a server raster (list of grid cells inside the plot) into a regular grid.
function geomRings(geom) {
  if (!geom) return [];
  if (geom.type === 'Polygon') return geom.coordinates;
  if (geom.type === 'MultiPolygon') return geom.coordinates.flat();
  return [];
}

function rasterToGrid(raster, geom) {
  const cells = raster.cells;
  let S = Infinity, N = -Infinity, Wl = Infinity, E = -Infinity;
  cells.forEach(c => { S = Math.min(S, c.bounds[0][0]); N = Math.max(N, c.bounds[1][0]); Wl = Math.min(Wl, c.bounds[0][1]); E = Math.max(E, c.bounds[1][1]); });
  // The server grid spans the plot's bounding box — use it so edge cells line up with the polygon.
  geomRings(geom).forEach(r => r.forEach(([lng, lat]) => { S = Math.min(S, lat); N = Math.max(N, lat); Wl = Math.min(Wl, lng); E = Math.max(E, lng); }));
  const dLat = cells[0].bounds[1][0] - cells[0].bounds[0][0], dLng = cells[0].bounds[1][1] - cells[0].bounds[0][1];
  const H = Math.max(1, Math.round((N - S) / dLat)), W = Math.max(1, Math.round((E - Wl) / dLng));
  const grid = new Float32Array(W * H).fill(NaN);
  cells.forEach(c => {
    const x = Math.min(W - 1, Math.floor((c.bounds[0][1] - Wl) / dLng + 0.5));
    const y = Math.min(H - 1, Math.floor((N - c.bounds[1][0]) / dLat + 0.5));   // row 0 = north
    grid[y * W + x] = c.value;
  });
  return { S, N, Wl, E, W, H, grid, rings: geomRings(geom) };
}

// Paint one plot as a smooth surface: bilinear upsampling, class contour lines, soft relief.
function paintRaster(g, param, scale, counts) {
  const F = Math.max(2, Math.min(10, Math.floor(640 / Math.max(g.W, g.H))));
  const PW = g.W * F, PH = g.H * F;
  const at = (x, y) => (x < 0 || y < 0 || x >= g.W || y >= g.H) ? NaN : g.grid[y * g.W + x];
  const val = new Float32Array(PW * PH).fill(NaN), cls = new Int8Array(PW * PH).fill(-1);
  for (let py = 0; py < PH; py++) {
    for (let px = 0; px < PW; px++) {
      const cx = Math.floor(px / F), cy = Math.floor(py / F);
      let base = at(cx, cy);
      if (isNaN(base)) {
        // Edge cell whose centre fell outside the polygon: borrow the nearest value so the
        // surface reaches the real boundary (the polygon clip below trims it exactly).
        if (!g.rings.length) continue;
        for (let r = 1; r <= 2 && isNaN(base); r++)
          for (let dy = -r; dy <= r && isNaN(base); dy++)
            for (let dx = -r; dx <= r && isNaN(base); dx++) base = at(cx + dx, cy + dy);
        if (isNaN(base)) continue;
      }
      const gx = (px + 0.5) / F - 0.5, gy = (py + 0.5) / F - 0.5;
      const x0 = Math.floor(gx), y0 = Math.floor(gy), tx = gx - x0, ty = gy - y0;
      let sum = 0, wsum = 0;
      [[x0, y0, (1 - tx) * (1 - ty)], [x0 + 1, y0, tx * (1 - ty)], [x0, y0 + 1, (1 - tx) * ty], [x0 + 1, y0 + 1, tx * ty]].forEach(([x, y, w]) => {
        const v = at(x, y); if (!isNaN(v) && w > 0) { sum += v * w; wsum += w; }
      });
      const i = py * PW + px;
      val[i] = wsum ? sum / wsum : base;
      cls[i] = classIdx(val[i], scale);
    }
  }
  let fMin = Infinity, fMax = -Infinity;
  for (let i = 0; i < g.grid.length; i++) if (!isNaN(g.grid[i])) {
    counts[classIdx(g.grid[i], scale)]++; fMin = Math.min(fMin, g.grid[i]); fMax = Math.max(fMax, g.grid[i]);
  }
  // Isolines: 6 equal bands across this field's own measured range, so the shape of the
  // real interpolated surface reads as contours even when it all sits in one class.
  const fRange = fMax - fMin, BANDS = 6, hasIso = fRange > 1e-6;
  const iso = new Int8Array(PW * PH).fill(-1);
  if (hasIso) for (let i = 0; i < val.length; i++) if (cls[i] >= 0) iso[i] = Math.min(BANDS - 1, Math.floor((val[i] - fMin) / fRange * BANDS));
  const cv = document.createElement('canvas'); cv.width = PW; cv.height = PH;
  const ctx = cv.getContext('2d'), img = ctx.createImageData(PW, PH), px = img.data;
  for (let y = 0; y < PH; y++) for (let x = 0; x < PW; x++) {
    const i = y * PW + x; if (cls[i] < 0) continue;
    let [r, gr, b] = smoothRgb(val[i], scale, param), a = 215;
    const right = x < PW - 1 ? cls[i + 1] : cls[i], down = y < PH - 1 ? cls[i + PW] : cls[i];
    const isoR = x < PW - 1 ? iso[i + 1] : iso[i], isoD = y < PH - 1 ? iso[i + PW] : iso[i];
    if ((right >= 0 && right !== cls[i]) || (down >= 0 && down !== cls[i])) { r *= 0.45; gr *= 0.45; b *= 0.45; a = 235; }
    else if (hasIso && ((isoR >= 0 && isoR !== iso[i]) || (isoD >= 0 && isoD !== iso[i]))) { r *= 0.62; gr *= 0.62; b *= 0.62; a = 230; }
    else if (hasIso) {
      // relief shading from the field's own slope (light from the top-left) plus a gentle
      // tint from low → high within the field, so the surface reads in 3D like SoilMap's
      const t = (val[i] - fMin) / fRange - 0.5;
      let d = t * 34;
      if (x > 0 && y > 0 && cls[i - PW - 1] >= 0) d += Math.max(-26, Math.min(26, (val[i] - val[i - PW - 1]) / fRange * PW * 10));
      r += d; gr += d; b += d;
    }
    const o = i * 4;
    px[o] = Math.max(0, Math.min(255, r)); px[o + 1] = Math.max(0, Math.min(255, gr)); px[o + 2] = Math.max(0, Math.min(255, b)); px[o + 3] = a;
  }
  ctx.putImageData(img, 0, 0);
  if (g.rings.length) {
    // Clip to the exact drawn boundary for clean edges at any zoom.
    ctx.globalCompositeOperation = 'destination-in';
    ctx.beginPath();
    g.rings.forEach(ring => ring.forEach(([lng, lat], j) => {
      const x = (lng - g.Wl) / (g.E - g.Wl) * PW, y = (g.N - lat) / (g.N - g.S) * PH;
      if (j === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }));
    ctx.closePath();
    ctx.fill('evenodd');
    ctx.globalCompositeOperation = 'source-over';
  }
  return cv.toDataURL();
}

function renderRastersOnMap() {
  rasterLayerGroup.clearLayers();
  rasterStates = [];
  const paramConfig = PARAMETERS[activeParameter];
  if (!paramConfig) return;
  const scale = colormaps[activeParameter];
  const counts = new Array(scale.length).fill(0);
  let sum = 0, total = 0, vmin = Infinity, vmax = -Infinity, method = 'none';

  Object.entries(allRasters).forEach(([plotId, raster]) => {
    if (!raster || !raster.cells || !raster.cells.length || raster.parameter !== activeParameter) return;
    const g = rasterToGrid(raster, (plotsById[plotId] || {}).geometry);
    const url = paintRaster(g, activeParameter, scale, counts);
    L.imageOverlay(url, [[g.S, g.Wl], [g.N, g.E]], { opacity: 1, interactive: false, className: 'gl-raster-img' }).addTo(rasterLayerGroup);
    raster.cells.forEach(c => { sum += c.value; total++; vmin = Math.min(vmin, c.value); vmax = Math.max(vmax, c.value); });
    if (raster.method === 'idw') method = 'idw';
    else if (raster.method === 'single_sample_gradient' && method !== 'idw') method = 'single_sample_gradient';
    rasterStates.push({ ...g, method: raster.method, name: (plotsById[plotId] || {}).name || '' });
  });

  const stats = { counts, total, avg: total ? sum / total : NaN, min: total ? vmin : NaN, max: total ? vmax : NaN, method };
  updateLegendPanel(stats);
  renderLyrBar();
  renderLyrMetrics(stats);
}

function onRasterHover(e) {
  const tip = document.getElementById('lyr-tip');
  const { lat, lng } = e.latlng;
  for (const st of rasterStates) {
    if (lat < st.S || lat > st.N || lng < st.Wl || lng > st.E) continue;
    const x = Math.min(st.W - 1, Math.floor((lng - st.Wl) / (st.E - st.Wl) * st.W));
    const y = Math.min(st.H - 1, Math.floor((st.N - lat) / (st.N - st.S) * st.H));
    const v = st.grid[y * st.W + x];
    if (isNaN(v)) continue;
    const p = PARAMETERS[activeParameter], sc = colormaps[activeParameter], ci = classIdx(v, sc);
    tip.innerHTML = `<div class="t-h">${esc(p.label)}</div><div class="t-v">${fmtV(v)} <small>${p.unit}</small></div>
      <div class="t-r" style="--c:${sc[ci].hex}">${classNames(activeParameter)[ci]}</div>
      <div class="t-m">${st.method === 'single_sample_gradient' ? 'Estimated (1 point)' : 'Interpolated (IDW)'}${st.name ? ' · ' + esc(st.name) : ''}</div>`;
    tip.style.left = (e.containerPoint.x + 16) + 'px';
    tip.style.top = (e.containerPoint.y + 16) + 'px';
    tip.classList.add('show');
    return;
  }
  tip.classList.remove('show');
}

function renderLyrBar() {
  const bar = document.getElementById('lyr-bar');
  if (!points.length && !plots.length) { bar.classList.remove('show'); return; }
  const p = PARAMETERS[activeParameter];
  const chips = QUICK_LAYERS.map(k => {
    const lbl = k === 'ph' ? '<b>pH</b>' : `<b>${LAYER_META[k].sym}</b> ${PARAMETERS[k].label}`;
    return `<button type="button" class="lb-chip${k === activeParameter ? ' active' : ''}" data-k="${k}">${lbl}</button>`;
  }).join('');
  bar.innerHTML = `<div class="lb-title"><span class="gl-dot"></span>LAYER ACTIVE: ${esc(p.label).toUpperCase()} DISTRIBUTION</div>
    <div class="lb-row"><span class="lb-lbl">Switch to:</span>${chips}
    <button type="button" class="lb-chip lb-more" data-more="1">All layers <i class="fas fa-caret-right"></i></button></div>`;
  bar.querySelectorAll('.lb-chip').forEach(btn => btn.addEventListener('click', () => {
    if (btn.dataset.more) {
      setSidebarCollapsed(false);
      parameterTabsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else setActiveParameter(btn.dataset.k);
  }));
  bar.classList.remove('show'); void bar.offsetWidth; bar.classList.add('show');
}

function renderLyrMetrics(stats) {
  const met = document.getElementById('lyr-metrics');
  if (!points.length && !plots.length) { met.classList.remove('show'); return; }
  const k = activeParameter, p = PARAMETERS[k], sc = colormaps[k], names = classNames(k), bad = badClasses(k);
  const smp = sampleStats(k);
  const ref = !isNaN(stats.avg) ? stats.avg : smp.avg;
  const ci = isNaN(ref) ? -1 : classIdx(ref, sc);
  let body;
  if (!stats.total) {
    body = `<div class="lm-info"><i class="fas fa-circle-info"></i><div>${smp.n ? 'No boundary has this layer yet.' : 'No samples have a value for this layer yet.'} Add a reading with ${esc(p.label)} to see its field map.</div></div>`;
  } else {
    const badPct = bad.reduce((a, i) => a + (stats.counts[i] || 0), 0) / stats.total * 100;
    const warn = badPct > 0.5
      ? `<div class="lm-warn"><i class="fas fa-triangle-exclamation"></i><div><b>${badPct.toFixed(0)}% of mapped area</b> ${k === 'ph' ? 'is outside the optimal pH band' : k === 'ec' ? 'shows elevated salinity' : 'is deficient — needs attention'}</div></div>`
      : `<div class="lm-ok"><i class="fas fa-check"></i><div>No deficient zones detected</div></div>`;
    const bars = sc.map((x, i) => {
      const pct = (stats.counts[i] || 0) / stats.total * 100;
      return `<div class="lm-bar"><span class="lm-bl">${names[i]}</span><div class="lm-bt"><div class="lm-bf" data-w="${pct.toFixed(1)}" style="background:${x.hex}"></div></div><span class="lm-bp">${pct.toFixed(0)}%</span></div>`;
    }).join('');
    body = `<div class="lm-grid">
        <div><div class="lm-k">Field Avg</div><div class="lm-v">${fmtV(stats.avg)} <small>${p.unit}</small></div></div>
        <div><div class="lm-k">Samples Avg</div><div class="lm-v">${fmtV(smp.avg)} <small>${p.unit}</small></div></div>
        <div><div class="lm-k">Min</div><div class="lm-v">${fmtV(stats.min)}</div></div>
        <div><div class="lm-k">Max</div><div class="lm-v">${fmtV(stats.max)}</div></div>
      </div>
      ${ci >= 0 ? `<div class="lm-k">Rating</div><div class="lm-rate" style="--c:${sc[ci].hex}">${names[ci]}</div>` : ''}
      ${warn}
      <div class="lm-k" style="margin-top:8px">Field summary</div>${bars}`;
  }
  met.innerHTML = `<div class="lm-h"><span><i class="fas fa-chart-simple"></i>LIVE LAYER METRICS</span><button type="button" class="lm-x" title="Collapse / expand">&#9662;</button></div>
    <div class="lm-body">
      <div class="lm-k">Selected Layer</div><div class="lm-big">${esc(p.label)}</div>
      ${body}
      <div class="lm-k" style="margin-top:8px">${smp.n} sample${smp.n === 1 ? '' : 's'} · ${rasterStates.length} mapped boundar${rasterStates.length === 1 ? 'y' : 'ies'}</div>
    </div>`;
  met.querySelector('.lm-x').addEventListener('click', () => { lmMin = met.classList.toggle('min'); });
  if (lmMin === null) lmMin = window.innerWidth < 900;
  met.classList.toggle('min', lmMin);
  met.classList.remove('show'); void met.offsetWidth; met.classList.add('show');
  requestAnimationFrame(() => requestAnimationFrame(() => met.querySelectorAll('.lm-bf').forEach(b => { b.style.width = b.dataset.w + '%'; })));
}

function updateLegendPanel(stats) {
  const legendPanel = document.getElementById('legend-panel');
  if (!stats || !stats.total) { legendPanel.style.display = 'none'; return; }
  const k = activeParameter, p = PARAMETERS[k], sc = colormaps[k], names = classNames(k);
  legendPanel.style.display = 'block';
  legendPanel.style.animation = 'none'; void legendPanel.offsetWidth; legendPanel.style.animation = '';
  document.getElementById('legend-title').innerHTML = `${esc(p.label)} ${p.unit ? `<small>(${p.unit})</small>` : ''}`;
  document.getElementById('legend-bar').style.background = p.legendGradient;
  document.getElementById('legend-min').textContent = `min ${stats.min.toFixed(1)} ${p.unit}`;
  document.getElementById('legend-max').textContent = `max ${stats.max.toFixed(1)} ${p.unit}`;
  document.getElementById('legend-classes').innerHTML = [...sc].map((item, i) => {
    const lo = i === 0 ? null : sc[i - 1].max;
    const label = item.max === Infinity ? `> ${lo}` : (lo === null ? `< ${item.max}` : `${lo} – ${item.max}`);
    const pct = (stats.counts[i] / stats.total * 100).toFixed(0);
    return `<div class="lg-row"><span class="lg-sw" style="background:${item.hex}"></span><span class="lg-nm">${names[i]}</span><span class="lg-rg">${label}</span><span class="lg-pc">${pct}%</span></div>`;
  }).reverse().join('');
  document.getElementById('legend-method').innerHTML = stats.method === 'idw'
    ? '<i class="fas fa-wave-square"></i> IDW Interpolation'
    : stats.method === 'single_sample_gradient' ? '<i class="fas fa-bullseye"></i> Radial Gradient (1 point)' : 'No Overlays';
}

function invalidatePlotRasterCache(plotId) {
  Object.keys(rasterCache).forEach(key => { if (key.startsWith(`${plotId}-`)) delete rasterCache[key]; });
}

// ── Draw-to-add flow ─────────────────────────────────────────────────────────

function startLinkedPointDraw(reading) {
  pendingAddMode = 'linking';
  pendingReading = reading;
  multiAddCount = 0;
  if (reading.latitude && reading.longitude) flyToLocation(reading.latitude, reading.longitude);
  document.getElementById('draw-hint').style.display = 'block';
  mapInstance.pm.enableDraw('Polygon', { snappable: true, templineStyle: { color: '#2d6a4f' }, hintlineStyle: { color: '#2d6a4f', dashArray: [5, 5] } });
}

function startManualPointDraw() {
  pendingAddMode = 'manual';
  pendingReading = null;
  document.getElementById('draw-hint').style.display = 'block';
  mapInstance.pm.enableDraw('Polygon', { snappable: true, templineStyle: { color: '#2d6a4f' }, hintlineStyle: { color: '#2d6a4f', dashArray: [5, 5] } });
}

function cancelDraw() {
  mapInstance.pm.disableDraw('Polygon');
  document.getElementById('draw-hint').style.display = 'none';
  hidePointForm();
}

function openConfirmForm() {
  pointFormErrorBanner.style.display = 'none';
  pointFormCard.style.display = 'flex';
  document.getElementById('add-manual-point-btn-trigger').style.display = 'none';

  if (pendingAddMode === 'linking') {
    document.getElementById('point-form-title').textContent = `Add Position — Reading #${pendingReading.id}`;
    document.getElementById('manual-only-fields').style.display = 'none';
    document.getElementById('notes-only-field').style.display = 'block';
    document.getElementById('point-notes-linked').value = '';
    document.getElementById('linked-params-preview').innerHTML = buildParamGrid(pendingReading.parameters);
    document.getElementById('multi-add-toggle').checked = false;
    updateMultiAddCount();
  } else {
    document.getElementById('point-form-title').textContent = 'Add Manual Point';
    document.getElementById('manual-only-fields').style.display = 'block';
    document.getElementById('notes-only-field').style.display = 'none';
    document.getElementById('point-sample-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('point-notes').value = '';
    initPointFormParameters({});
  }
  scrollFormIntoView();
}

function scrollFormIntoView() {
  // The form can appear while the user is scrolled deep into "All Readings" —
  // without this, the sidebar shows no visible sign anything happened.
  pointFormCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function updateMultiAddCount() {
  const el = document.getElementById('multi-add-count');
  if (multiAddCount > 0) {
    el.style.display = 'block';
    el.textContent = `${multiAddCount} position${multiAddCount === 1 ? '' : 's'} added this session`;
  } else {
    el.style.display = 'none';
  }
}

function autoPlotName() {
  const dateStr = new Date().toLocaleDateString();
  if (pendingAddMode === 'linking') return `Reading #${pendingReading.id} — ${dateStr}`;
  return `Manual — ${dateStr}`;
}

// ── Edit flow ────────────────────────────────────────────────────────────────

function hidePointForm() {
  pointFormCard.style.display = 'none';
  document.getElementById('add-manual-point-btn-trigger').style.display = 'inline-flex';
  pendingAddMode = null;
  pendingReading = null;
  pendingGeometry = null;
  pointFormMode = null;
  pointFormContext = {};
}

async function openEditPosition(pointId) {
  try {
    const res = await fetch(URLS.pointDetail(pointId));
    if (!res.ok) { alert('Could not load this position.'); return; }
    const point = await res.json();

    if (point.plot) flyToPlot(point.plot);

    pointFormContext = { pointId: point.id, plotId: point.plot };
    pointFormErrorBanner.style.display = 'none';
    pointFormCard.style.display = 'flex';
    document.getElementById('add-manual-point-btn-trigger').style.display = 'none';

    if (point.reading_id) {
      pointFormMode = 'editing-linked';
      document.getElementById('point-form-title').textContent = `Edit Position — Reading #${point.reading_id}`;
      document.getElementById('manual-only-fields').style.display = 'none';
      document.getElementById('notes-only-field').style.display = 'block';
      document.getElementById('point-notes-linked').value = point.notes || '';
      document.getElementById('linked-params-preview').innerHTML = buildParamGrid(point.parameters);
      document.getElementById('multi-add-row').style.display = 'none';
      document.getElementById('multi-add-count').style.display = 'none';
    } else {
      pointFormMode = 'editing-manual';
      document.getElementById('point-form-title').textContent = 'Edit Manual Point';
      document.getElementById('manual-only-fields').style.display = 'block';
      document.getElementById('notes-only-field').style.display = 'none';
      document.getElementById('point-sample-date').value = point.sample_date;
      document.getElementById('point-notes').value = point.notes || '';
      initPointFormParameters(point.parameters);
    }
    scrollFormIntoView();
  } catch (e) { console.error('Error loading position:', e); }
}

function initPointFormParameters(existingParams) {
  const formParamsContainer = document.getElementById('form-params-container');
  formParamsContainer.innerHTML = '';
  const addParamsSelection = document.getElementById('add-params-selection');
  addParamsSelection.innerHTML = '';

  Object.values(PARAMETERS).forEach(p => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-sm btn-secondary';
    btn.setAttribute('data-form-param', p.name);
    btn.textContent = `+ ${getShortLabel(p)}`;
    btn.addEventListener('click', () => toggleFormParameter(p.name));
    addParamsSelection.appendChild(btn);
  });

  const keysToShow = Object.keys(existingParams || {});
  if (keysToShow.length === 0) keysToShow.push(activeParameter);
  keysToShow.forEach(key => { if (PARAMETERS[key]) toggleFormParameter(key, true, existingParams ? existingParams[key] : undefined); });
}

function toggleFormParameter(paramKey, forceAdd = false, existingValue) {
  const rowId = `form-param-row-${paramKey}`;
  const existingRow = document.getElementById(rowId);
  const addBtn = document.querySelector(`[data-form-param="${paramKey}"]`);

  if (existingRow && !forceAdd) {
    existingRow.remove();
    if (addBtn) { addBtn.classList.remove('btn-primary'); addBtn.classList.add('btn-secondary'); addBtn.textContent = `+ ${getShortLabel(PARAMETERS[paramKey])}`; }
  } else if (!existingRow) {
    const container = document.getElementById('form-params-container');
    const p = PARAMETERS[paramKey];
    const defaultVal = PARAM_NEUTRALS[paramKey] !== undefined ? PARAM_NEUTRALS[paramKey] : 0;
    const row = document.createElement('div');
    row.id = rowId;
    row.className = 'param-row';
    row.innerHTML = `
      <span class="param-row-label">${p.label}</span>
      <input type="number" step="any" class="form-control point-param-input" data-param-name="${p.name}" value="${existingValue !== undefined ? existingValue : defaultVal}" required />
      <span style="font-size:10px;color:var(--text-secondary);width:30px;">${p.unit}</span>`;
    container.appendChild(row);
    if (addBtn) { addBtn.classList.remove('btn-secondary'); addBtn.classList.add('btn-primary'); addBtn.textContent = `✓ ${getShortLabel(p)}`; }
  }
}

const PARAM_NEUTRALS = { ph: 7.0, ec: 2.0, n: 150.0, p: 50.0, k: 200.0, organic_carbon: 2.0, s: 15.0, ca: 3.0, mg: 2.0, fe: 10.0, zn: 2.0, cu: 1.0, b: 0.8, mn: 15.0 };

// ── Save handler ─────────────────────────────────────────────────────────────

async function handlePointFormSubmit(e) {
  e.preventDefault();
  pointFormErrorBanner.style.display = 'none';
  pointFormErrorBanner.innerHTML = '';

  try {
    if (pointFormMode === 'editing-linked') {
      const notes = document.getElementById('point-notes-linked').value.trim();
      const res = await fetch(URLS.pointDetail(pointFormContext.pointId), {
        method: 'PATCH', headers: jsonHeaders(), body: JSON.stringify({ notes: notes || null }),
      });
      if (res.ok) { afterEditSaved(); } else { const d = await res.json(); showPointFormError(d.error || 'Failed to save.'); }
      return;
    }

    if (pointFormMode === 'editing-manual') {
      const params = collectParamInputs();
      if (params.error) { showPointFormError(params.error); return; }
      const date = document.getElementById('point-sample-date').value;
      const notes = document.getElementById('point-notes').value.trim();
      if (!date) { showPointFormError('Sample date is required.'); return; }
      const res = await fetch(URLS.pointDetail(pointFormContext.pointId), {
        method: 'PATCH', headers: jsonHeaders(),
        body: JSON.stringify({ sample_date: date, notes: notes || null, parameters: params.values }),
      });
      if (res.ok) { afterEditSaved(); } else { const d = await res.json(); showPointFormError(d.error || 'Failed to save.'); }
      return;
    }

    // Creating: pendingAddMode is 'linking' or 'manual', pendingGeometry holds the drawn polygon.
    if (!pendingGeometry) { showPointFormError('No boundary drawn — draw one on the map first.'); return; }

    const plotRes = await fetch(URLS.plots, {
      method: 'POST', headers: jsonHeaders(),
      body: JSON.stringify({ name: autoPlotName(), geometry: pendingGeometry }),
    });
    if (!plotRes.ok) { const d = await plotRes.json(); showPointFormError(d.error || 'Failed to save boundary.'); return; }
    const plot = await plotRes.json();

    let pointBody;
    if (pendingAddMode === 'linking') {
      const notes = document.getElementById('point-notes-linked').value.trim();
      pointBody = { reading_id: pendingReading.id, notes: notes || null };
    } else {
      const params = collectParamInputs();
      if (params.error) { await deletePlotSilently(plot.id); showPointFormError(params.error); return; }
      const date = document.getElementById('point-sample-date').value;
      const notes = document.getElementById('point-notes').value.trim();
      if (!date) { await deletePlotSilently(plot.id); showPointFormError('Sample date is required.'); return; }
      pointBody = { sample_date: date, notes: notes || null, parameters: params.values };
    }

    const pointRes = await fetch(URLS.points(plot.id), { method: 'POST', headers: jsonHeaders(), body: JSON.stringify(pointBody) });
    if (!pointRes.ok) {
      await deletePlotSilently(plot.id);
      const d = await pointRes.json();
      showPointFormError(d.error || 'Failed to save.');
      return;
    }

    pendingGeometry = null;
    fetchPlots();
    fetchPoints();
    fetchReadings();

    const keepAdding = pendingAddMode === 'linking' && document.getElementById('multi-add-toggle').checked;
    if (keepAdding) {
      multiAddCount++;
      updateMultiAddCount();
      document.getElementById('draw-hint').style.display = 'block';
      mapInstance.pm.enableDraw('Polygon', { snappable: true, templineStyle: { color: '#2d6a4f' }, hintlineStyle: { color: '#2d6a4f', dashArray: [5, 5] } });
    } else {
      hidePointForm();
    }
  } catch (err) {
    console.error('Error saving point:', err);
    showPointFormError('Network error — could not reach the server.');
  }
}

function afterEditSaved() {
  hidePointForm();
  fetchPoints();
  fetchReadings();
  if (pointFormContext.plotId) invalidatePlotRasterCache(pointFormContext.plotId);
  fetchAllRasters();
}

function collectParamInputs() {
  const values = {};
  let error = null;
  document.querySelectorAll('.point-param-input').forEach(input => {
    const key = input.getAttribute('data-param-name');
    const val = parseFloat(input.value);
    if (isNaN(val)) { error = 'One or more parameter values are invalid.'; return; }
    values[key] = val;
  });
  if (!error && Object.keys(values).length === 0) error = 'Add at least one parameter reading.';
  return { values, error };
}

function showPointFormError(msg) {
  pointFormErrorBanner.style.display = 'block';
  pointFormErrorBanner.textContent = msg;
}
