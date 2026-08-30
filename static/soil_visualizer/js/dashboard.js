const URLS = window.SOIL_VIZ_URLS;

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? m[1] : '';
}

function jsonHeaders() {
  return { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() };
}

const colormaps = {
  'ph': [{ max: 4.5, hex: '#D32F2F' }, { max: 5.5, hex: '#E67E22' }, { max: 6.5, hex: '#F1C40F' }, { max: 7.5, hex: '#27AE60' }, { max: 8.5, hex: '#2980B9' }, { max: Infinity, hex: '#17202A' }],
  'ec': [{ max: 0.2, hex: '#0B2545' }, { max: 0.8, hex: '#134074' }, { max: 1.6, hex: '#8DA9C4' }, { max: 3.2, hex: '#EEB902' }, { max: 6.4, hex: '#D05A02' }, { max: Infinity, hex: '#4A0000' }],
  'n': [{ max: 50, hex: '#E8F5E9' }, { max: 100, hex: '#A5D6A7' }, { max: 200, hex: '#4CAF50' }, { max: 300, hex: '#2E7D32' }, { max: 400, hex: '#1B5E20' }, { max: Infinity, hex: '#08250A' }],
  'p': [{ max: 5, hex: '#FCE4EC' }, { max: 10, hex: '#F8BBD0' }, { max: 20, hex: '#EC407A' }, { max: 40, hex: '#C2185B' }, { max: 60, hex: '#880E4F' }, { max: Infinity, hex: '#4A0025' }],
  'k': [{ max: 80, hex: '#FFF8E1' }, { max: 120, hex: '#FFE082' }, { max: 200, hex: '#FFB74D' }, { max: 300, hex: '#E65100' }, { max: 500, hex: '#9E2A2B' }, { max: Infinity, hex: '#3E0F05' }],
  'organic_carbon': [{ max: 0.25, hex: '#F5EBE6' }, { max: 0.5, hex: '#D7CCC8' }, { max: 0.75, hex: '#BCAAA4' }, { max: 1.5, hex: '#6D4C41' }, { max: 3.0, hex: '#3E2723' }, { max: Infinity, hex: '#1A0B05' }],
  's': [{ max: 5, hex: '#FFFDE7' }, { max: 10, hex: '#FFF59D' }, { max: 20, hex: '#FBC02D' }, { max: 40, hex: '#F57F17' }, { max: 80, hex: '#827717' }, { max: Infinity, hex: '#333008' }],
  'fe': [{ max: 2, hex: '#FFEBEE' }, { max: 4.5, hex: '#FF8A80' }, { max: 9, hex: '#D32F2F' }, { max: 20, hex: '#B71C1C' }, { max: 50, hex: '#7F0000' }, { max: Infinity, hex: '#3B0000' }],
  'zn': [{ max: 0.5, hex: '#ECEFF1' }, { max: 1.0, hex: '#B0BEC5' }, { max: 2.0, hex: '#78909C' }, { max: 5.0, hex: '#455A64' }, { max: 10.0, hex: '#263238' }, { max: Infinity, hex: '#0D1417' }],
  'cu': [{ max: 0.2, hex: '#E0F2F1' }, { max: 1.0, hex: '#80CBC4' }, { max: 2.5, hex: '#26A69A' }, { max: 5.0, hex: '#00695C' }, { max: 10.0, hex: '#004D40' }, { max: Infinity, hex: '#00251E' }],
  'b': [{ max: 0.25, hex: '#E8EAF6' }, { max: 0.5, hex: '#9FA8DA' }, { max: 1.0, hex: '#5C6BC0' }, { max: 2.0, hex: '#3F51B5' }, { max: 4.0, hex: '#1A237E' }, { max: Infinity, hex: '#0B0C24' }],
  'mn': [{ max: 2.0, hex: '#F5F5F5' }, { max: 5.0, hex: '#E0E0E0' }, { max: 10.0, hex: '#BDBDBD' }, { max: 25.0, hex: '#757575' }, { max: 50.0, hex: '#424242' }, { max: Infinity, hex: '#111111' }],
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
  fe:             { name: 'fe', label: 'Iron', unit: 'ppm', getColor: makeGetColor('fe'), legendGradient: 'linear-gradient(to right, #FFEBEE, #FF8A80, #D32F2F, #B71C1C, #7F0000, #3B0000)' },
  zn:             { name: 'zn', label: 'Zinc', unit: 'ppm', getColor: makeGetColor('zn'), legendGradient: 'linear-gradient(to right, #ECEFF1, #B0BEC5, #78909C, #455A64, #263238, #0D1417)' },
  cu:             { name: 'cu', label: 'Copper', unit: 'ppm', getColor: makeGetColor('cu'), legendGradient: 'linear-gradient(to right, #E0F2F1, #80CBC4, #26A69A, #00695C, #004D40, #00251E)' },
  b:              { name: 'b', label: 'Boron', unit: 'ppm', getColor: makeGetColor('b'), legendGradient: 'linear-gradient(to right, #E8EAF6, #9FA8DA, #5C6BC0, #3F51B5, #1A237E, #0B0C24)' },
  mn:             { name: 'mn', label: 'Manganese', unit: 'ppm', getColor: makeGetColor('mn'), legendGradient: 'linear-gradient(to right, #F5F5F5, #E0E0E0, #BDBDBD, #757575, #424242, #111111)' },
};

const getShortLabel = (p) => {
  const map = { ph: 'pH', ec: 'EC', n: 'N', p: 'P', k: 'K', organic_carbon: 'Org C', s: 'S', fe: 'Fe', zn: 'Zn', cu: 'Cu', b: 'B', mn: 'Mn' };
  return map[p.name] || p.label;
};

// Compact color-coded stat grid, used anywhere a full parameter set needs
// to be previewed (reading detail expand, point map popup, add-form preview).
function buildParamGrid(parameters) {
  const order = Object.keys(PARAMETERS);
  const keys = Object.keys(parameters).sort((a, b) => order.indexOf(a) - order.indexOf(b));
  const chips = keys.map(key => {
    const config = PARAMETERS[key] || { label: key, unit: '' };
    const val = parameters[key];
    const color = (val !== undefined && val !== null && config.getColor) ? config.getColor(val) : '#9ca3af';
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
let points = [];           // every point for this device (flat list)
let plots = [];            // every plot (boundary) for this device
let plotsById = {};
let activeParameter = 'ph';
let rasterCache = {};
let allRasters = {};

let readingsQuery = '';
let readingsPage = 1;
let readingsData = { results: [], num_pages: 1, count: 0 };

// pendingAddMode: null | 'linking' | 'manual'
let pendingAddMode = null;
let pendingReading = null;
let pendingGeometry = null;
let multiAddCount = 0;

// pointFormMode (for edit only now): 'editing-linked' | 'editing-manual'
let pointFormMode = null;
let pointFormContext = {};

let mapInstance = null;
const plotsLayerGroup = L.featureGroup();
const pointsLayerGroup = L.featureGroup();
const rasterLayerGroup = L.featureGroup();
let canvasRenderer = null;
let hasLocated = false;

let pointsListContainer, pointFormCard;
let readingsListContainer, readingsSearchInput, readingsPager;
let parameterTabsContainer, pointForm, pointFormErrorBanner;

document.addEventListener('DOMContentLoaded', () => {
  cacheDOM();
  initMap();
  initParameterTabs();
  bindGlobalEvents();
  fetchPlots();
  fetchPoints();
  fetchReadings();
});

function cacheDOM() {
  pointsListContainer = document.getElementById('points-list');
  readingsListContainer = document.getElementById('readings-list');
  readingsSearchInput = document.getElementById('readings-search-input');
  readingsPager = document.getElementById('readings-pager');
  pointFormCard = document.getElementById('point-form-card');
  parameterTabsContainer = document.getElementById('parameter-tabs');
  pointForm = document.getElementById('point-form');
  pointFormErrorBanner = document.getElementById('point-form-error-banner');
}

function initMap() {
  mapInstance = L.map('map', { center: [20.5, 78.9], zoom: 5, zoomControl: false });
  canvasRenderer = L.canvas();

  const fetchIPLocationFallback = () => {
    fetch('https://ipapi.co/json/')
      .then(res => { if (!res.ok) throw new Error('bad status'); return res.json(); })
      .then(data => {
        if (data && data.latitude && data.longitude) {
          hasLocated = true;
          mapInstance.setView([data.latitude, data.longitude], 12);
        }
      })
      .catch(() => {});
  };

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (position) => { hasLocated = true; mapInstance.setView([position.coords.latitude, position.coords.longitude], 14); },
      () => fetchIPLocationFallback(),
      { enableHighAccuracy: false, timeout: 5000, maximumAge: 30000 }
    );
  } else {
    fetchIPLocationFallback();
  }

  L.control.zoom({ position: 'topright' }).addTo(mapInstance);

  const googleRoadmap = L.tileLayer('https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', { attribution: '&copy; Google Maps', maxZoom: 20 });
  const googleHybrid = L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', { attribution: '&copy; Google Maps', maxZoom: 20 });
  googleHybrid.addTo(mapInstance);
  L.control.layers({ 'Google Maps (Satellite Hybrid)': googleHybrid, 'Google Maps (Standard Roadmap)': googleRoadmap }, null, { position: 'bottomleft' }).addTo(mapInstance);

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
  parameterTabsContainer.innerHTML = '';
  Object.values(PARAMETERS).forEach(p => {
    const tab = document.createElement('button');
    tab.className = `param-tab ${p.name === activeParameter ? 'active' : ''}`;
    tab.setAttribute('data-param', p.name);
    tab.title = p.label;
    tab.textContent = getShortLabel(p);
    tab.addEventListener('click', () => setActiveParameter(p.name));
    parameterTabsContainer.appendChild(tab);
  });
}

function setActiveParameter(param) {
  activeParameter = param;
  document.querySelectorAll('.param-tab').forEach(tab => tab.classList.toggle('active', tab.getAttribute('data-param') === param));
  renderPointsOnMap();
  fetchAllRasters();
}

function bindGlobalEvents() {
  document.getElementById('cancel-point-btn').addEventListener('click', cancelDraw);
  pointForm.addEventListener('submit', handlePointFormSubmit);

  let searchDebounce = null;
  readingsSearchInput.addEventListener('input', function () {
    clearTimeout(searchDebounce);
    const val = this.value;
    searchDebounce = setTimeout(() => { readingsQuery = val.trim(); readingsPage = 1; fetchReadings(); }, 350);
  });
}

function flyToLocation(lat, lon) {
  if (!lat || !lon) return;
  mapInstance.flyTo([lat, lon], 17, { duration: 1.2 });
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
      renderPlotsOnMap();
      fetchAllRasters();
    }
  } catch (e) { console.error('Error fetching plots:', e); }
}

function renderPlotsOnMap() {
  plotsLayerGroup.clearLayers();
  plots.forEach(plot => {
    const layer = L.geoJSON(plot.geometry, { style: { color: '#2d6a4f', weight: 1.5, fillColor: '#2d6a4f', fillOpacity: 0.05 } });
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
      renderPointsList();
      renderPointsOnMap();
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
  const paramConfig = PARAMETERS[activeParameter];
  if (!paramConfig) return;

  points.forEach(point => {
    if (!point.coordinates) return;
    const lat = point.coordinates.lat, lon = point.coordinates.lon;
    const val = point.parameters[activeParameter];
    const formattedVal = (val !== undefined && val !== null) ? val.toFixed(2) : 'N/A';

    const invisibleIcon = L.divIcon({ className: 'invisible-point-marker', html: '<div style="width:0;height:0;"></div>', iconSize: [0, 0], iconAnchor: [0, 0] });
    const marker = L.marker([lat, lon], { icon: invisibleIcon });

    marker.bindTooltip(`<div class="ticket-map-label param-${activeParameter}">${formattedVal} ${paramConfig.unit || ''}</div>`, {
      permanent: true, direction: 'top', offset: [0, -10], className: 'custom-ticket-tooltip',
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
  });
}

async function handleDeletePoint(point) {
  if (!confirm('Delete this point (and its boundary)?')) return;
  try {
    const res = await fetch(URLS.pointDetail(point.id), { method: 'DELETE', headers: { 'X-CSRFToken': getCsrf() } });
    if (res.ok) {
      if (point.plot) await deletePlotSilently(point.plot);
      points = points.filter(p => p.id !== point.id);
      renderPointsList();
      renderPointsOnMap();
      fetchPlots();
      fetchReadings();
    }
  } catch (e) { console.error('Error deleting point:', e); }
}

// ── Rasters ──────────────────────────────────────────────────────────────────

async function fetchAllRasters() {
  if (plots.length === 0) { allRasters = {}; renderRastersOnMap(); return; }
  const newRasters = {};
  for (const plot of plots) {
    const cacheKey = `${plot.id}-${activeParameter}`;
    if (rasterCache[cacheKey]) { newRasters[plot.id] = rasterCache[cacheKey]; continue; }
    try {
      const res = await fetch(`${URLS.raster(plot.id)}?parameter=${activeParameter}&resolution=60`);
      if (res.ok) {
        const data = await res.json();
        rasterCache[cacheKey] = data;
        newRasters[plot.id] = data;
      }
    } catch (e) { console.error(`Error fetching raster for plot ${plot.id}:`, e); }
  }
  allRasters = newRasters;
  renderRastersOnMap();
}

function renderRastersOnMap() {
  rasterLayerGroup.clearLayers();
  const paramConfig = PARAMETERS[activeParameter];
  if (!paramConfig) return;

  Object.values(allRasters).forEach(raster => {
    if (!raster || !raster.cells || raster.parameter !== activeParameter) return;
    raster.cells.forEach(cell => {
      const color = paramConfig.getColor(cell.value);
      const rect = L.rectangle(cell.bounds, { stroke: false, fillColor: color, fillOpacity: 0.7, renderer: canvasRenderer, interactive: true });
      rect.bindTooltip(`<div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:11px;padding:4px;color:#1e2f23;">
        <strong>Value:</strong> ${cell.value.toFixed(2)} ${paramConfig.unit || ''}<br/>
        <strong>Status:</strong> ${raster.method === 'single_sample_gradient' ? 'Estimated (1 point)' : 'Interpolated (IDW)'}
      </div>`, { sticky: true });
      rasterLayerGroup.addLayer(rect);
    });
  });
  updateLegendPanel();
}

function updateLegendPanel() {
  const legendPanel = document.getElementById('legend-panel');
  let globalMin = null, globalMax = null, globalMethod = 'none';
  Object.values(allRasters).forEach(r => {
    if (r && r.parameter === activeParameter && r.cells && r.cells.length > 0) {
      if (globalMin === null || r.min_value < globalMin) globalMin = r.min_value;
      if (globalMax === null || r.max_value > globalMax) globalMax = r.max_value;
      if (r.method === 'idw') globalMethod = 'idw';
      else if (r.method === 'single_sample_gradient' && globalMethod !== 'idw') globalMethod = 'single_sample_gradient';
    }
  });
  if (globalMin === null || globalMax === null) { legendPanel.style.display = 'none'; return; }
  legendPanel.style.display = 'block';
  document.getElementById('legend-title').textContent = PARAMETERS[activeParameter].label;
  document.getElementById('legend-bar').style.background = PARAMETERS[activeParameter].legendGradient;
  document.getElementById('legend-min').textContent = `${globalMin.toFixed(1)} ${PARAMETERS[activeParameter].unit}`;
  document.getElementById('legend-max').textContent = `${globalMax.toFixed(1)} ${PARAMETERS[activeParameter].unit}`;
  document.getElementById('legend-method').textContent = globalMethod === 'idw' ? 'IDW Interpolation' : globalMethod === 'single_sample_gradient' ? 'Radial Gradient (1 point)' : 'No Overlays';
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

const PARAM_NEUTRALS = { ph: 7.0, ec: 2.0, n: 150.0, p: 50.0, k: 200.0, organic_carbon: 2.0, s: 15.0, fe: 10.0, zn: 2.0, cu: 1.0, b: 0.8, mn: 15.0 };

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
