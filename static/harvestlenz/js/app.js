document.addEventListener('DOMContentLoaded', () => {
    function getCookie(name) {
        let value = null;
        document.cookie.split(';').forEach(c => {
            c = c.trim();
            if (c.startsWith(name + '=')) value = decodeURIComponent(c.slice(name.length + 1));
        });
        return value;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    const rupees = n => `Rs ${Number(n || 0).toFixed(2)}`;

    // API base — HarvestLenz endpoints are scoped to this device
    const API_BASE = `/api/mobile/devices/${HARVESTLENZ_DEVICE_ID}/harvestlenz`;

    let activeFile = null;
    let cameraStream = null;
    let isSingle = true;
    let fruitsLoaded = false;

    const $ = id => document.getElementById(id);

    const navButtons = document.querySelectorAll('.nav-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    const fruitType = $('fruit-type');
    const singleButtons = document.querySelectorAll('.hl-toggle button');

    const tabUpload = $('tab-upload');
    const tabCamera = $('tab-camera');
    const uploadZone = $('upload-zone');
    const cameraZone = $('camera-zone');
    const fileInput = $('file-input');
    const previewContainer = $('preview-container');
    const imagePreview = $('image-preview');
    const videoStream = $('video-stream');
    const captureCanvas = $('capture-canvas');

    const resultsPanel = $('results-panel');
    const resultsEmpty = $('results-empty');
    const resultsLoading = $('results-loading');
    const resultsContent = $('results-content');

    // ==========================================================================
    // 1. NAVIGATION
    // ==========================================================================

    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-tab');
            navButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.add('hidden'));
            btn.classList.add('active');
            $(`tab-${target}`).classList.remove('hidden');

            if (target === 'fruits') loadFruits();
            else if (target === 'analytics') loadStats();
        });
    });

    singleButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            singleButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            isSingle = btn.dataset.single === 'true';
        });
    });

    // ==========================================================================
    // 2. FILE UPLOAD & CAMERA
    // ==========================================================================

    tabUpload.addEventListener('click', () => switchMediaTab('upload'));
    tabCamera.addEventListener('click', () => switchMediaTab('camera'));

    function switchMediaTab(mode) {
        if (mode === 'upload') {
            tabUpload.classList.add('active');
            tabCamera.classList.remove('active');
            uploadZone.classList.remove('hidden');
            cameraZone.classList.add('hidden');
            stopCamera();
        } else {
            tabUpload.classList.remove('active');
            tabCamera.classList.add('active');
            uploadZone.classList.add('hidden');
            cameraZone.classList.remove('hidden');
            previewContainer.classList.remove('scanning');
            previewContainer.classList.add('hidden');
            activeFile = null;
            startCamera();
        }
    }

    async function startCamera() {
        try {
            cameraStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' }, audio: false,
            });
            videoStream.srcObject = cameraStream;
        } catch (err) {
            console.error('Error accessing camera:', err);
            alert('Unable to access camera. Please upload an image instead.');
            switchMediaTab('upload');
        }
    }

    function stopCamera() {
        if (cameraStream) {
            cameraStream.getTracks().forEach(track => track.stop());
            cameraStream = null;
        }
        videoStream.srcObject = null;
    }

    $('btn-stop-camera').addEventListener('click', () => switchMediaTab('upload'));

    $('btn-snap').addEventListener('click', () => {
        if (!videoStream.srcObject) return;
        captureCanvas.width = videoStream.videoWidth;
        captureCanvas.height = videoStream.videoHeight;
        captureCanvas.getContext('2d').drawImage(videoStream, 0, 0, captureCanvas.width, captureCanvas.height);
        captureCanvas.toBlob(blob => {
            handleSelectedFile(new File([blob], 'captured_fruit.jpg', { type: 'image/jpeg' }));
            stopCamera();
            uploadZone.classList.add('hidden');
            cameraZone.classList.add('hidden');
        }, 'image/jpeg', 0.95);
    });

    uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
    uploadZone.addEventListener('drop', e => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) handleSelectedFile(e.dataTransfer.files[0]);
    });
    uploadZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', e => {
        if (e.target.files.length > 0) handleSelectedFile(e.target.files[0]);
    });

    function handleSelectedFile(file) {
        if (!file.type.startsWith('image/')) {
            alert('Please select an image file (PNG/JPEG/WEBP).');
            return;
        }
        activeFile = file;
        const reader = new FileReader();
        reader.onload = e => {
            imagePreview.src = e.target.result;
            previewContainer.classList.remove('hidden');
            uploadZone.classList.add('hidden');
        };
        reader.readAsDataURL(file);
    }

    function backToCapture() {
        activeFile = null;
        fileInput.value = '';
        previewContainer.classList.add('hidden');
        previewContainer.classList.remove('scanning');
        if (tabUpload.classList.contains('active')) {
            uploadZone.classList.remove('hidden');
        } else {
            startCamera();
            cameraZone.classList.remove('hidden');
        }
    }

    $('btn-reset').addEventListener('click', e => { e.stopPropagation(); backToCapture(); });

    // ==========================================================================
    // 3. GRADING & RESULTS
    // ==========================================================================

    function showResultsState(state) {
        resultsPanel.classList.toggle('empty', state === 'empty');
        resultsEmpty.classList.toggle('hidden', state !== 'empty');
        resultsLoading.classList.toggle('hidden', state !== 'loading');
        resultsContent.classList.toggle('hidden', state !== 'content');
    }

    $('btn-analyze').addEventListener('click', async () => {
        if (!activeFile) return;
        previewContainer.classList.add('scanning');
        showResultsState('loading');

        const formData = new FormData();
        formData.append('image', activeFile);
        formData.append('fruit_type', fruitType.value);
        formData.append('is_single', isSingle ? 'true' : 'false');

        try {
            const response = await fetch(`${API_BASE}/scan/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
                body: formData,
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Grading failed');
            previewContainer.classList.remove('scanning');
            displayResults(data);
        } catch (err) {
            console.error('Grading error:', err);
            previewContainer.classList.remove('scanning');
            alert(err.message || 'Failed to connect to the fruit grading engine.');
            showResultsState('empty');
            previewContainer.classList.remove('hidden');
        }
    });

    function displayResults(data) {
        const a = data.analysis;
        showResultsState('content');

        const img = $('res-image');
        img.src = data.annotated_image || imagePreview.src;

        $('res-fruit').textContent = a.fruit_name + (a.auto_detected ? ' (auto)' : '');
        const grade = $('res-grade');
        grade.textContent = a.overall_grade;
        grade.className = `hl-grade grade-${a.overall_grade.toLowerCase()}`;
        $('res-score').textContent = `Score ${a.score}/100`;

        const mismatch = $('res-mismatch');
        mismatch.classList.toggle('hidden', !a.mismatch);
        mismatch.textContent = a.mismatch ? a.ai_recommendations[0] : '';

        $('res-total').textContent = a.total_fruits;
        $('res-counts').textContent = `${a.summary.good} / ${a.summary.better} / ${a.summary.reject}`;
        $('res-shelf').textContent = `${a.average_shelf_life} days`;
        $('res-market').textContent = a.recommended_market;
        $('res-value').textContent = rupees(a.total_price);
        $('res-selling').textContent = rupees(a.estimated_selling_price);

        const tbody = $('res-fruits');
        tbody.innerHTML = a.fruits.length ? '' :
            '<tr><td colspan="6">No gradeable fruit found in this photo. Try a closer, well-lit photo.</td></tr>';
        a.fruits.forEach(f => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${escapeHtml(f.fruit_id)}</td>
                <td><span class="hl-dot" style="background:${escapeHtml(f.grade_color)}"></span>${escapeHtml(f.grade)}</td>
                <td>${(f.confidence * 100).toFixed(1)}%</td>
                <td>${f.shelf_life_days} days</td>
                <td>${escapeHtml(f.market_recommendation)}</td>
                <td>${escapeHtml((f.defects || []).join(', ').replace(/_/g, ' ') || '—')}</td>`;
            tbody.appendChild(tr);
        });

        const recs = $('res-recs');
        recs.innerHTML = '';
        (a.mismatch ? a.ai_recommendations.slice(1) : a.ai_recommendations).forEach(text => {
            const li = document.createElement('li');
            li.textContent = text;
            recs.appendChild(li);
        });
        if (!recs.children.length) recs.innerHTML = '<li>No additional recommendations.</li>';
    }

    $('btn-scan-another').addEventListener('click', () => {
        $('res-image').src = '';
        showResultsState('empty');
        backToCapture();
    });

    // ==========================================================================
    // 4. SUPPORTED FRUITS
    // ==========================================================================

    async function loadFruits() {
        if (fruitsLoaded) return;
        try {
            const response = await fetch('/api/mobile/harvestlenz/fruits/', {
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
            });
            if (!response.ok) return;
            const data = await response.json();
            const tbody = $('fruits-table');
            tbody.innerHTML = '';
            data.fruits.forEach(f => {
                const cell = g => {
                    const m = f.market[g] || {};
                    return `${f.shelf_life_days[g] ?? '—'} days &bull; ${escapeHtml(m.market || '—')}<br>
                            <small>${escapeHtml(m.price_range || '')}</small>`;
                };
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${escapeHtml(f.name)}</strong><br><small><em>${escapeHtml(f.scientific)}</em></small></td>
                    <td>${cell('Good')}</td><td>${cell('Better')}</td><td>${cell('Reject')}</td>`;
                tbody.appendChild(tr);
            });
            $('fruits-count').textContent = `${data.fruits.length} fruits`;
            fruitsLoaded = true;
        } catch (err) {
            console.error('Error loading fruits:', err);
        }
    }

    // ==========================================================================
    // 5. ANALYTICS (this device only)
    // ==========================================================================

    async function loadStats() {
        try {
            const response = await fetch(`${API_BASE}/stats/`, {
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
            });
            if (!response.ok) return;
            const data = await response.json();

            $('stat-total-scans').textContent = data.total_scans;
            $('stat-total-fruits').textContent = data.total_fruits;
            const g = data.grade_totals;
            $('stat-grades').textContent = `${g.good} / ${g.better} / ${g.reject}`;

            const chart = $('stats-distribution-chart');
            const noStats = $('no-stats-text');
            chart.innerHTML = '';
            if (!data.fruit_distribution.length) {
                chart.appendChild(noStats);
                return;
            }
            const maxCount = Math.max(...data.fruit_distribution.map(d => d.count), 1);
            data.fruit_distribution.forEach(item => {
                const row = document.createElement('div');
                row.className = 'distribution-row';
                row.innerHTML = `
                    <div class="distribution-label-bar">
                        <span>${escapeHtml(item.fruit_name)}</span>
                        <span>${item.count} scan${item.count !== 1 ? 's' : ''}</span>
                    </div>
                    <div class="distribution-bar-bg"><div class="distribution-bar-fill" style="width: 0%"></div></div>`;
                chart.appendChild(row);
                setTimeout(() => {
                    row.querySelector('.distribution-bar-fill').style.width = `${(item.count / maxCount * 100).toFixed(1)}%`;
                }, 50);
            });
        } catch (err) {
            console.error('Error loading analytics:', err);
        }
    }
});
