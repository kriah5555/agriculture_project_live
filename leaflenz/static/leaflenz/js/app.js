document.addEventListener('DOMContentLoaded', () => {
    // ==========================================================================
    // 0. ONBOARDING POPUP
    // ==========================================================================
    const onboardingOverlay = document.getElementById('onboarding-overlay');
    const onboardingProceedBtn = document.getElementById('onboarding-proceed-btn');
    const onboardingSkip = document.getElementById('onboarding-skip');

    function dismissOnboarding() {
        onboardingOverlay.classList.add('hiding');
        setTimeout(() => {
            onboardingOverlay.style.display = 'none';
        }, 420);
    }

    if (onboardingProceedBtn) {
        onboardingProceedBtn.addEventListener('click', dismissOnboarding);
    }
    if (onboardingSkip) {
        onboardingSkip.addEventListener('click', dismissOnboarding);
    }

    function getCookie(name) {
        let value = null;
        document.cookie.split(';').forEach(c => {
            c = c.trim();
            if (c.startsWith(name + '=')) value = decodeURIComponent(c.slice(name.length + 1));
        });
        return value;
    }

    // API base — LeafLenz endpoints are scoped to this device
    const API_BASE = `/api/mobile/devices/${LEAFLENZ_DEVICE_ID}/leaflenz`;

    // State management
    let activeFile = null;
    let cameraStream = null;
    let diseaseDatabase = {};  // Stores disease encyclopedia loaded from api
    let uniquePlants = new Set();

    // Navigation and Tab Elements
    const navButtons = document.querySelectorAll('.nav-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    // AI Scanner Elements
    const tabUpload = document.getElementById('tab-upload');
    const tabCamera = document.getElementById('tab-camera');
    const uploadZone = document.getElementById('upload-zone');
    const cameraZone = document.getElementById('camera-zone');
    const fileInput = document.getElementById('file-input');
    const previewContainer = document.getElementById('preview-container');
    const imagePreview = document.getElementById('image-preview');

    const videoStream = document.getElementById('video-stream');
    const captureCanvas = document.getElementById('capture-canvas');
    const btnSnap = document.getElementById('btn-snap');
    const btnStopCamera = document.getElementById('btn-stop-camera');
    const btnReset = document.getElementById('btn-reset');
    const btnAnalyze = document.getElementById('btn-analyze');

    const resultsPanel = document.getElementById('results-panel');
    const resultsEmpty = document.getElementById('results-empty');
    const resultsLoading = document.getElementById('results-loading');
    const resultsContent = document.getElementById('results-content');

    const resImage = document.getElementById('res-image');
    const resPlant = document.getElementById('res-plant');
    const resDisease = document.getElementById('res-disease');
    const resConfidence = document.getElementById('res-confidence');
    const resConfidenceBar = document.getElementById('res-confidence-bar');
    const btnScanAnother = document.getElementById('btn-scan-another');

    const descText = document.getElementById('desc-text');
    const symptomsText = document.getElementById('symptoms-text');
    const treatmentText = document.getElementById('treatment-text');
    const infoTabs = document.querySelectorAll('.info-tab');
    const infoPanes = document.querySelectorAll('.info-pane');

    // Encyclopedia Elements
    const encyclopediaGrid = document.getElementById('encyclopedia-grid');
    const encyclopediaSearch = document.getElementById('encyclopedia-search');
    const encyclopediaFilter = document.getElementById('encyclopedia-filter');
    const encyclopediaCount = document.getElementById('encyclopedia-count');

    // Stats Elements
    const statTotalScans = document.getElementById('stat-total-scans');
    const statsDistributionChart = document.getElementById('stats-distribution-chart');
    const noStatsText = document.getElementById('no-stats-text');

    // ==========================================================================
    // 1. NAVIGATION & THEME SYSTEM
    // ==========================================================================

    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');

            navButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.add('hidden'));

            btn.classList.add('active');
            document.getElementById(`tab-${targetTab}`).classList.remove('hidden');

            if (targetTab === 'encyclopedia') {
                ensureDiseaseDatabaseLoaded().then(() => renderEncyclopedia());
            } else if (targetTab === 'analytics') {
                loadStats();
            }
        });
    });

    // ==========================================================================
    // 2. FILE UPLOAD & CAMERA SYSTEM
    // ==========================================================================

    tabUpload.addEventListener('click', () => {
        switchMediaTab('upload');
    });

    tabCamera.addEventListener('click', () => {
        switchMediaTab('camera');
    });

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
                video: { facingMode: 'environment' },
                audio: false
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

    btnStopCamera.addEventListener('click', () => {
        switchMediaTab('upload');
    });

    btnSnap.addEventListener('click', () => {
        if (!videoStream.srcObject) return;

        captureCanvas.width = videoStream.videoWidth;
        captureCanvas.height = videoStream.videoHeight;

        const ctx = captureCanvas.getContext('2d');
        ctx.drawImage(videoStream, 0, 0, captureCanvas.width, captureCanvas.height);

        captureCanvas.toBlob((blob) => {
            const file = new File([blob], 'captured_leaf.jpg', { type: 'image/jpeg' });
            handleSelectedFile(file);
            stopCamera();
            uploadZone.classList.add('hidden');
            cameraZone.classList.add('hidden');
        }, 'image/jpeg', 0.95);
    });

    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleSelectedFile(e.dataTransfer.files[0]);
        }
    });

    uploadZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleSelectedFile(e.target.files[0]);
        }
    });

    function handleSelectedFile(file) {
        if (!file.type.startsWith('image/')) {
            alert('Please select an image file (PNG/JPEG).');
            return;
        }
        activeFile = file;

        const reader = new FileReader();
        reader.onload = (e) => {
            imagePreview.src = e.target.result;
            previewContainer.classList.remove('hidden');
            uploadZone.classList.add('hidden');
        };
        reader.readAsDataURL(file);
    }

    btnReset.addEventListener('click', (e) => {
        e.stopPropagation();
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
    });

    // ==========================================================================
    // 3. AI DIAGNOSTICS & RESULTS
    // ==========================================================================

    btnAnalyze.addEventListener('click', async () => {
        if (!activeFile) return;

        previewContainer.classList.add('scanning');
        resultsPanel.classList.remove('empty');
        resultsEmpty.classList.add('hidden');
        resultsLoading.classList.remove('hidden');
        resultsContent.classList.add('hidden');

        const formData = new FormData();
        formData.append('image', activeFile);

        try {
            const response = await fetch(`${API_BASE}/scan/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
                body: formData
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'API Diagnosis Error');

            previewContainer.classList.remove('scanning');
            displayResults(data);
        } catch (err) {
            console.error('Diagnosis error:', err);
            previewContainer.classList.remove('scanning');
            alert(err.message || 'Failed to connect to leaf diagnostic engine.');
            resetDiagnosticUI();
        }
    });

    function resetDiagnosticUI() {
        resultsPanel.classList.add('empty');
        resultsEmpty.classList.remove('hidden');
        resultsLoading.classList.add('hidden');
        resultsContent.classList.add('hidden');
        previewContainer.classList.remove('hidden');
    }

    function displayResults(data) {
        resultsLoading.classList.add('hidden');
        resultsContent.classList.remove('hidden');

        if (imagePreview.src) {
            resImage.src = imagePreview.src;
            resImage.style.display = 'block';
        }

        const plantName = data.plant_name;
        const diseaseName = data.disease_name;
        const isHealthy = (diseaseName || '').toLowerCase() === 'healthy';

        resPlant.textContent = plantName;
        resDisease.textContent = isHealthy ? '✅ Healthy!' : diseaseName;

        const headerCard = document.getElementById('prediction-header-card');
        const iconEl = document.getElementById('disease-icon-el');
        const subtitleEl = document.getElementById('disease-subtitle');
        headerCard.classList.remove('result-healthy', 'result-disease');

        if (isHealthy) {
            headerCard.classList.add('result-healthy');
            iconEl.className = 'fa-solid fa-heart-pulse';
            subtitleEl.textContent = 'No Disease Detected';
        } else {
            headerCard.classList.add('result-disease');
            iconEl.className = 'fa-solid fa-virus';
            subtitleEl.textContent = 'Disease Detected';
        }

        const confidencePct = ((data.field1 || 0) * 100).toFixed(1);
        resConfidence.textContent = `${confidencePct}%`;
        resConfidenceBar.style.width = '0%';
        setTimeout(() => {
            resConfidenceBar.style.width = `${confidencePct}%`;
        }, 150);

        const info = data.disease_info || {};
        descText.textContent = info.description || 'N/A';
        symptomsText.textContent = info.symptoms || 'N/A';
        treatmentText.textContent = info.treatment_and_prevention || 'N/A';
    }

    // Results panel tab navigation
    infoTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            infoTabs.forEach(t => t.classList.remove('active'));
            infoPanes.forEach(p => p.classList.remove('active'));

            tab.classList.add('active');
            const target = tab.getAttribute('data-target');
            document.getElementById(target).classList.add('active');
        });
    });

    // ==========================================================================
    // 4. ENCYCLOPEDIA SYSTEM
    // ==========================================================================

    async function ensureDiseaseDatabaseLoaded() {
        if (Object.keys(diseaseDatabase).length > 0) return;

        try {
            const response = await fetch('/api/mobile/leaflenz/diseases/', {
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
            });
            if (!response.ok) return;

            diseaseDatabase = await response.json();

            uniquePlants.clear();
            Object.keys(diseaseDatabase).forEach(key => {
                if (key === 'fallback') return;
                uniquePlants.add(diseaseDatabase[key].plant_name);
            });

            encyclopediaFilter.innerHTML = '<option value="all">All Plants</option>';
            Array.from(uniquePlants).sort().forEach(plant => {
                const opt = document.createElement('option');
                opt.value = plant;
                opt.textContent = plant;
                encyclopediaFilter.appendChild(opt);
            });
        } catch (err) {
            console.error('Error fetching disease data:', err);
        }
    }

    function renderEncyclopedia() {
        encyclopediaGrid.innerHTML = '';

        const filterVal = encyclopediaFilter.value.toLowerCase();
        const searchVal = encyclopediaSearch.value.trim().toLowerCase();

        let visibleCount = 0;

        Object.keys(diseaseDatabase).forEach(key => {
            if (key === 'fallback') return;
            const info = diseaseDatabase[key];

            const plantMatches = filterVal === 'all' || info.plant_name.toLowerCase() === filterVal;
            const searchMatches = !searchVal ||
                info.plant_name.toLowerCase().includes(searchVal) ||
                info.disease_name.toLowerCase().includes(searchVal) ||
                info.description.toLowerCase().includes(searchVal) ||
                info.symptoms.toLowerCase().includes(searchVal) ||
                info.treatment_prevention.toLowerCase().includes(searchVal);

            if (plantMatches && searchMatches) {
                visibleCount++;
                const card = document.createElement('div');
                card.className = 'encyco-card';
                card.innerHTML = `
                    <div class="encyco-card-header">
                        <div class="encyco-card-title">
                            <span>${info.plant_name}</span>
                            <h3>${info.disease_name}</h3>
                        </div>
                        <i class="fa-solid fa-chevron-down chevron-icon"></i>
                    </div>
                    <div class="encyco-card-body collapsed">
                        <div class="encyco-section">
                            <h4><i class="fa-solid fa-circle-info"></i> About the Condition</h4>
                            <p>${info.description}</p>
                        </div>
                        <div class="encyco-section">
                            <h4><i class="fa-solid fa-list-check"></i> Symptoms</h4>
                            <p>${info.symptoms}</p>
                        </div>
                        <div class="encyco-section">
                            <h4><i class="fa-solid fa-hand-holding-medical"></i> Treatment & Prevention</h4>
                            <p>${info.treatment_prevention}</p>
                        </div>
                    </div>
                `;

                const header = card.querySelector('.encyco-card-header');
                const body = card.querySelector('.encyco-card-body');

                header.addEventListener('click', () => {
                    const isExpanded = card.classList.toggle('expanded');
                    if (isExpanded) {
                        body.classList.remove('collapsed');
                        body.style.maxHeight = 'none';
                        const height = body.scrollHeight + 'px';
                        body.style.maxHeight = '0px';
                        setTimeout(() => { body.style.maxHeight = height; }, 10);
                        setTimeout(() => { body.style.maxHeight = 'none'; }, 310);
                    } else {
                        body.style.maxHeight = body.scrollHeight + 'px';
                        setTimeout(() => { body.style.maxHeight = '0px'; }, 10);
                        setTimeout(() => { body.classList.add('collapsed'); }, 300);
                    }
                });

                encyclopediaGrid.appendChild(card);
            }
        });

        encyclopediaCount.textContent = `${visibleCount} condition${visibleCount !== 1 ? 's' : ''}`;
    }

    encyclopediaSearch.addEventListener('input', renderEncyclopedia);
    encyclopediaFilter.addEventListener('change', renderEncyclopedia);

    // ==========================================================================
    // 5. STATISTICS & ANALYTICS DASHBOARD (this device only — no feedback/accuracy
    //    metrics are tracked, since LeafLenz reuses the shared readings table)
    // ==========================================================================

    async function loadStats() {
        try {
            const response = await fetch(`${API_BASE}/stats/`, {
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
            });
            if (!response.ok) return;

            const data = await response.json();
            statTotalScans.textContent = data.total_scans;

            statsDistributionChart.innerHTML = '';

            if (data.plant_distribution && data.plant_distribution.length > 0) {
                const maxCount = Math.max(...data.plant_distribution.map(d => d.count), 1);

                data.plant_distribution.forEach(item => {
                    const percentage = ((item.count / maxCount) * 100).toFixed(1);
                    const row = document.createElement('div');
                    row.className = 'distribution-row';
                    row.innerHTML = `
                        <div class="distribution-label-bar">
                            <span>${item.plant_name}</span>
                            <span>${item.count} scan${item.count !== 1 ? 's' : ''}</span>
                        </div>
                        <div class="distribution-bar-bg">
                            <div class="distribution-bar-fill" style="width: 0%"></div>
                        </div>
                    `;
                    statsDistributionChart.appendChild(row);

                    setTimeout(() => {
                        const bar = row.querySelector('.distribution-bar-fill');
                        if (bar) bar.style.width = `${percentage}%`;
                    }, 50);
                });
            } else if (noStatsText) {
                statsDistributionChart.appendChild(noStatsText);
                noStatsText.classList.remove('hidden');
            }
        } catch (err) {
            console.error('Error loading analytics:', err);
        }
    }

    // ==========================================================================
    // 6. SCAN ANOTHER — reset back to the upload state from the results panel
    // ==========================================================================

    if (btnScanAnother) {
        btnScanAnother.addEventListener('click', () => {
            activeFile = null;
            fileInput.value = '';
            resImage.style.display = 'none';
            resImage.src = '';
            previewContainer.classList.add('hidden');
            previewContainer.classList.remove('scanning');
            resultsPanel.classList.add('empty');
            resultsEmpty.classList.remove('hidden');
            resultsLoading.classList.add('hidden');
            resultsContent.classList.add('hidden');
            if (tabUpload.classList.contains('active')) {
                uploadZone.classList.remove('hidden');
            } else {
                startCamera();
                cameraZone.classList.remove('hidden');
            }
        });
    }
});
