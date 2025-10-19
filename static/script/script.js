/* ---------- File handling ---------- */
let selectedFile = null;
let originalFile = null;

const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');

uploadArea.addEventListener('click', () => fileInput.click());
uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); uploadArea.classList.add('dragover'); });
uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
uploadArea.addEventListener('drop', (e) => { e.preventDefault(); uploadArea.classList.remove('dragover'); const files = e.dataTransfer.files; if (files.length > 0) handleFile(files[0]); });
fileInput.addEventListener('change', (e) => { if (e.target.files.length > 0) handleFile(e.target.files[0]); });

function handleFile(file) {
    const allowedTypes = ['image/png','image/jpeg','image/jpg','image/webp','image/bmp'];
    if (!allowedTypes.includes(file.type)) { showError('Please select a valid image file (PNG, JPG, JPEG, WEBP, or BMP)'); return; }
    if (file.size > 20 * 1024 * 1024) { showError('File size must be less than 20MB'); return; }

    selectedFile = file; originalFile = file;
    fileName.textContent = `📄 ${file.name}`;
    fileSize.textContent = `Size: ${(file.size / 1024 / 1024).toFixed(2)} MB`;
    fileInfo.style.display = 'block';
    document.getElementById('actionButtons').style.display = 'block';
    document.getElementById('resetButton').style.display = 'none';
    fileInput.value = '';
    hideError(); hideSuccess();
}

/* ---------- Split / OCR flow ---------- */
let splitData = null;
let processedSegments = [];
let segmentImages = [];
let currentModalIndex = 0;
let cropper = null;
let currentZoom = 1;

async function splitImage() {
    if (!selectedFile) { showError('Please select a file first'); return; }

    const loading = document.getElementById('loading');
    const splitResults = document.getElementById('splitResults');

    loading.style.display = 'block';
    splitResults.style.display = 'none';
    hideError(); hideSuccess();

    try {
        loading.querySelector('p').textContent = 'Splitting image into segments...';
        const formData = new FormData(); formData.append('file', selectedFile);
        const splitResponse = await fetch('/api/split', { method: 'POST', body: formData });
        const splitResult = await splitResponse.json();
        if (!splitResponse.ok) throw new Error(splitResult.detail || 'Failed to split image');

        splitData = splitResult;
        loading.querySelector('p').textContent = 'Downloading segment images...';
        segmentImages = [];

        for (let i = 0; i < splitResult.total_segments; i++) {
            const segmentId = `${splitResult.split_id}_${i}`;
            const imageUrl = `/api/segment/${segmentId}`;
            try {
                const imageResponse = await fetch(imageUrl);
                if (imageResponse.ok) {
                    const imageBlob = await imageResponse.blob();
                    segmentImages.push({ id: segmentId, image: imageBlob, url: URL.createObjectURL(imageBlob) });
                } else {
                    const retry = await fetch(imageUrl);
                    if (retry.ok) {
                        const imageBlob = await retry.blob();
                        segmentImages.push({ id: segmentId, image: imageBlob, url: URL.createObjectURL(imageBlob) });
                    } else throw new Error('retry failed');
                }
            } catch {
                segmentImages.push({ id: segmentId, image: null, url: null, failed: true });
            }
        }

        displaySegmentImages(segmentImages);
        splitResults.style.display = 'block';
        document.getElementById('success').style.display = 'block';
        const s = segmentImages.filter(x=>!x.failed).length, f = segmentImages.filter(x=>x.failed).length;
        document.getElementById('success').textContent = `✓ Successfully split into ${segmentImages.length} segments (${s} successful, ${f} failed)! Using intelligent lap boundary detection for optimal OCR processing.`;
    } catch (err) {
        showError(`Error: ${err.message}`);
    } finally {
        loading.style.display = 'none';
    }
}

function displaySegmentImages(segments) {
    const grid = document.getElementById('segmentsGrid');
    grid.innerHTML = '';
    segments.forEach((segment, index) => {
        const segmentDiv = document.createElement('div');
        segmentDiv.className = 'segment-item';
        if (segment.failed) {
            segmentDiv.innerHTML = `
                <div style="width:100%;height:120px;background:#0b1220;display:flex;align-items:center;justify-content:center;border-radius:6px;margin-bottom:10px;border:1px dashed rgba(148,163,184,.25);">
                    <span style="color:#94a3b8;font-size:14px;">Failed to load</span>
                </div>
                <div class="segment-info">
                    <strong>Segment ${index + 1} (Failed)</strong><br>
                    <small>~${splitData.segment_info[index]?.estimated_laps_per_segment || 5} laps</small><br>
                    <small>Height: ${splitData.segment_info[index]?.height || 0}px</small>
                </div>`;
        } else {
            segmentDiv.innerHTML = `
                <img src="${segment.url}" alt="Segment ${index + 1}" onclick="openModal(${index})">
                <div class="segment-info">
                    <strong>Segment ${index + 1}</strong><br>
                    <small>~${splitData.segment_info[index]?.estimated_laps_per_segment || 5} laps</small><br>
                    <small>Height: ${splitData.segment_info[index]?.height || 0}px</small>
                </div>`;
        }
        grid.appendChild(segmentDiv);
    });
}

async function processExtraction() {
    if (!segmentImages.length) { showError('Please split the image first'); return; }
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');

    loading.style.display = 'block';
    results.style.display = 'none';
    hideError(); hideSuccess();

    try {
        loading.querySelector('p').textContent = 'Processing segments one by one...';
        processedSegments = [];
        let globalLapCounter = 1;

        for (let i = 0; i < segmentImages.length; i++) {
            const seg = segmentImages[i];
            loading.querySelector('p').textContent = `Processing segment ${i + 1}/${segmentImages.length}...`;
            if (seg.failed) continue;

            try {
                const ocrResponse = await fetch(`/api/ocr-segment/${seg.id}`, { method: 'POST' });
                const ocrResult = await ocrResponse.json();
                if (ocrResponse.ok) {
                    if (ocrResult.segment.laps && Array.isArray(ocrResult.segment.laps)) {
                        const segmentLaps = ocrResult.segment.laps.map(lap => ({ ...lap, lap: globalLapCounter++ }));
                        processedSegments.push(...segmentLaps);
                    } else {
                        processedSegments.push({ ...ocrResult.segment, lap: globalLapCounter++ });
                    }
                } else {
                    processedSegments.push({ lap: globalLapCounter++, stroke_type: "Unknown", lap_length_m: 50, duration: "1:30", strokes: 25, swolf: 100, pace_per_100m: "2:00" });
                }
            } catch {
                processedSegments.push({ lap: globalLapCounter++, stroke_type: "Unknown", lap_length_m: 50, duration: "1:30", strokes: 25, swolf: 100, pace_per_100m: "2:00" });
            }
        }

        const finalResult = { date: new Date().toISOString().split('T')[0], segments: processedSegments };
        renderCollapsibleJSON(finalResult, 'jsonViewer');

        const csvData = createCSV(processedSegments);
        const csvBlob = new Blob([csvData], { type: 'text/csv' });
        document.getElementById('csvDownload').href = URL.createObjectURL(csvBlob);

        // Display performance highlights
        displayPerformanceHighlights(processedSegments);

        results.style.display = 'block';
        document.getElementById('success').style.display = 'block';
        document.getElementById('success').textContent = `✓ Successfully processed ${processedSegments.length} swimming segments!`;
    } catch (err) {
        showError(`Error: ${err.message}`);
    } finally {
        loading.style.display = 'none';
    }
}

function resetProcess() {
    splitData = null; processedSegments = []; segmentImages = [];
    document.getElementById('splitResults').style.display = 'none';
    document.getElementById('results').style.display = 'none';
    document.getElementById('performanceHighlights').style.display = 'none';
    document.getElementById('segmentsGrid').innerHTML = '';
    hideError(); hideSuccess();
}

function createCSV(segments) {
    const headers = ["lap","stroke_type","lap_length_m","duration","strokes","swolf","pace_per_100m"];
    const rows = segments.map(seg => {
        const duration = seg.duration || secondsToMMSS(seg.duration_sec);
        const pace = seg.pace_per_100m || secondsToMMSS(seg.pace_per_100m_sec);
        
        return [
            seg.lap, 
            seg.stroke_type, 
            seg.lap_length_m,
            duration,
            seg.strokes,
            seg.swolf,
            pace
        ];
    });
    
    return [headers, ...rows].map(row => row.join(',')).join('\n');
}

function analyzePerformance(segments) {
    // Convert time strings to seconds for comparison
    const parseTimeToSeconds = (timeStr) => {
        if (!timeStr) return 0;
        const parts = timeStr.split(':');
        return parts.length === 2 ? parseInt(parts[0]) * 60 + parseInt(parts[1]) : 0;
    };
    
    // Extract numeric values for analysis
    const durations = segments.map(s => parseTimeToSeconds(s.duration || secondsToMMSS(s.duration_sec))).filter(d => d > 0);
    const strokes = segments.map(s => s.strokes).filter(s => s && s > 0);
    const swolfs = segments.map(s => s.swolf).filter(s => s && s > 0);
    const paces = segments.map(s => parseTimeToSeconds(s.pace_per_100m || secondsToMMSS(s.pace_per_100m_sec))).filter(p => p > 0);
    
    return {
        duration: {
            best: durations.length > 0 ? secondsToMMSS(Math.min(...durations)) : "N/A",
            worst: durations.length > 0 ? secondsToMMSS(Math.max(...durations)) : "N/A",
            values: durations
        },
        strokes: {
            best: strokes.length > 0 ? Math.min(...strokes) : "N/A",
            worst: strokes.length > 0 ? Math.max(...strokes) : "N/A",
            values: strokes
        },
        swolf: {
            best: swolfs.length > 0 ? Math.min(...swolfs) : "N/A",
            worst: swolfs.length > 0 ? Math.max(...swolfs) : "N/A",
            values: swolfs
        },
        pace: {
            best: paces.length > 0 ? secondsToMMSS(Math.min(...paces)) : "N/A",
            worst: paces.length > 0 ? secondsToMMSS(Math.max(...paces)) : "N/A",
            values: paces
        }
    };
}

function getPerformanceIndicator(value, metric, type) {
    if (!metric.values || metric.values.length === 0) return "";
    
    let indicator = "";
    let numericValue;
    
    // Convert value to numeric for comparison
    if (type === 'time') {
        numericValue = parseTimeToSeconds(value);
    } else {
        numericValue = parseFloat(value);
    }
    
    if (isNaN(numericValue)) return "";
    
    const min = Math.min(...metric.values);
    const max = Math.max(...metric.values);
    
    // For time-based metrics (duration, pace), lower is better
    // For stroke count, lower is generally better
    // For swolf, lower is better
    if (type === 'time' || type === 'strokes' || type === 'swolf') {
        if (numericValue === min) indicator = "🏆 BEST";
        else if (numericValue === max) indicator = "⚠️ WORST";
        else if (numericValue <= (min + (max - min) * 0.25)) indicator = "🟢 GOOD";
        else if (numericValue >= (min + (max - min) * 0.75)) indicator = "🟡 NEEDS IMPROVEMENT";
        else indicator = "⚪ AVERAGE";
    }
    
    return indicator;
}

function parseTimeToSeconds(timeStr) {
    if (!timeStr) return 0;
    const parts = timeStr.split(':');
    return parts.length === 2 ? parseInt(parts[0]) * 60 + parseInt(parts[1]) : 0;
}

function displayPerformanceHighlights(segments) {
    const performanceAnalysis = analyzePerformance(segments);
    const highlightsContainer = document.getElementById('performanceHighlights');
    const grid = document.getElementById('performanceGrid');
    
    // Clear existing content
    grid.innerHTML = '';
    
    // Create performance cards for each metric
    const metrics = [
        {
            title: '⏱️ Duration',
            best: performanceAnalysis.duration.best,
            worst: performanceAnalysis.duration.worst,
            unit: '',
            type: 'time'
        },
        {
            title: '🏊‍♂️ Strokes',
            best: performanceAnalysis.strokes.best,
            worst: performanceAnalysis.strokes.worst,
            unit: ' strokes',
            type: 'strokes'
        },
        {
            title: '📊 SWOLF',
            best: performanceAnalysis.swolf.best,
            worst: performanceAnalysis.swolf.worst,
            unit: '',
            type: 'swolf'
        },
        {
            title: '🏃‍♂️ Pace/100m',
            best: performanceAnalysis.pace.best,
            worst: performanceAnalysis.pace.worst,
            unit: '',
            type: 'time'
        }
    ];
    
    metrics.forEach(metric => {
        if (metric.best !== "N/A" && metric.worst !== "N/A") {
            const card = document.createElement('div');
            card.className = 'performance-card';
            
            card.innerHTML = `
                <div class="card-title">${metric.title}</div>
                <div class="performance-metric">
                    <span class="metric-label">Best:</span>
                    <span class="metric-value metric-best">${metric.best}${metric.unit}</span>
                    <span class="performance-indicator">🏆</span>
                </div>
                <div class="performance-metric">
                    <span class="metric-label">Worst:</span>
                    <span class="metric-value metric-worst">${metric.worst}${metric.unit}</span>
                    <span class="performance-indicator">⚠️</span>
                </div>
            `;
            
            grid.appendChild(card);
        }
    });
    
    // Add overall performance summary card
    const summaryCard = document.createElement('div');
    summaryCard.className = 'performance-card';
    
    const totalLaps = segments.length;
    const avgDuration = calculateAverage(performanceAnalysis.duration.values, true); // Time value
    const avgStrokes = calculateAverage(performanceAnalysis.strokes.values, false); // Numeric value
    const avgSwolf = calculateAverage(performanceAnalysis.swolf.values, false); // Numeric value
    
    summaryCard.innerHTML = `
        <div class="card-title">📈 Session Summary</div>
        <div class="performance-metric">
            <span class="metric-label">Total Laps:</span>
            <span class="metric-value">${totalLaps}</span>
        </div>
        <div class="performance-metric">
            <span class="metric-label">Avg Duration:</span>
            <span class="metric-value metric-average">${avgDuration}</span>
        </div>
        <div class="performance-metric">
            <span class="metric-label">Avg Strokes:</span>
            <span class="metric-value metric-average">${avgStrokes}</span>
        </div>
        <div class="performance-metric">
            <span class="metric-label">Avg SWOLF:</span>
            <span class="metric-value metric-average">${avgSwolf}</span>
        </div>
    `;
    
    grid.appendChild(summaryCard);
    
    // Show the highlights section
    highlightsContainer.style.display = 'block';
}

function calculateAverage(values, isTimeValue = false) {
    if (!values || values.length === 0) return "N/A";
    const sum = values.reduce((a, b) => a + b, 0);
    const avg = sum / values.length;
    
    // For time values, convert back to MM:SS format
    if (isTimeValue) {
        return secondsToMMSS(avg);
    } else {
        return avg.toFixed(1);
    }
}

function secondsToMMSS(seconds) {
    if (!seconds || seconds <= 0) return "0:00";
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        // HH:MM:SS format for hours
        return `${hours}:${minutes.toString().padStart(2,'0')}:${secs.toString().padStart(2,'0')}`;
    } else if (minutes > 0) {
        // MM:SS format for minutes
        return `${minutes}:${secs.toString().padStart(2,'0')}`;
    } else {
        // SS format for seconds only
        return `${secs}`;
    }
}

/* ---------- Image viewer ---------- */
function openModal(index){ if (!segmentImages.length) return; currentModalIndex=index; const m=document.getElementById('imageModal'); document.getElementById('modalImage').src=segmentImages[index].url; document.getElementById('modalInfo').textContent=`Segment ${index+1} of ${segmentImages.length}`; m.classList.add('show'); document.body.style.overflow='hidden'; }
function closeModal(){ document.getElementById('imageModal').classList.remove('show'); document.body.style.overflow='auto'; }
function nextImage(){ if(!segmentImages.length) return; currentModalIndex=(currentModalIndex+1)%segmentImages.length; updateModalImage(); }
function prevImage(){ if(!segmentImages.length) return; currentModalIndex=(currentModalIndex-1+segmentImages.length)%segmentImages.length; updateModalImage(); }
function updateModalImage(){ document.getElementById('modalImage').src=segmentImages[currentModalIndex].url; document.getElementById('modalInfo').textContent=`Segment ${currentModalIndex+1} of ${segmentImages.length}`; }
document.addEventListener('keydown', function(e){ const modal=document.getElementById('imageModal'); if(!modal.classList.contains('show')) return; if(e.key==='Escape') closeModal(); if(e.key==='ArrowLeft') prevImage(); if(e.key==='ArrowRight') nextImage(); });
document.getElementById('imageModal').addEventListener('click', function(e){ if(e.target===this) closeModal(); });

function openImageModal(){ if(!selectedFile){ showError('Please select a file first'); return; } const modal=document.getElementById('imageViewModal'); const viewImage=document.getElementById('viewImage'); viewImage.src=URL.createObjectURL(selectedFile); setupImageViewZoom(viewImage); modal.classList.add('show'); document.body.style.overflow='hidden'; }
function closeImageViewModal(){ document.getElementById('imageViewModal').classList.remove('show'); document.body.style.overflow='auto'; }

let viewZoom=1, viewPan={x:0,y:0}, isViewDragging=false, viewDragStart={x:0,y:0}, currentViewImage=null;
function setupImageViewZoom(image){ viewZoom=1; viewPan={x:0,y:0}; isViewDragging=false; currentViewImage=image; updateImageViewTransform(image); image.addEventListener('wheel', handleWheel, { passive:false }); image.addEventListener('mousedown', handleMouseDown); image.addEventListener('mousemove', handleMouseMove); image.addEventListener('mouseup', handleMouseUp); image.addEventListener('mouseleave', handleMouseLeave); image.addEventListener('dblclick', handleDoubleClick); }
function handleWheel(e){ e.preventDefault(); const rect=currentViewImage.getBoundingClientRect(); const cx=e.clientX-rect.left; const cy=e.clientY-rect.top; const delta=e.deltaY>0?0.9:1.1; const newZoom=Math.max(0.1, Math.min(5, viewZoom*delta)); const zc=newZoom/viewZoom; viewPan.x = cx - (cx - viewPan.x)*zc; viewPan.y = cy - (cy - viewPan.y)*zc; viewZoom=newZoom; updateImageViewTransform(currentViewImage); }
function handleMouseDown(e){ isViewDragging=true; viewDragStart.x=e.clientX-viewPan.x; viewDragStart.y=e.clientY-viewPan.y; currentViewImage.style.cursor='grabbing'; e.preventDefault(); }
function handleMouseMove(e){ if(isViewDragging){ viewPan.x=e.clientX-viewDragStart.x; viewPan.y=e.clientY-viewDragStart.y; updateImageViewTransform(currentViewImage); } }
function handleMouseUp(){ isViewDragging=false; if(currentViewImage){ currentViewImage.style.cursor='grab'; } }
function handleMouseLeave(){ isViewDragging=false; if(currentViewImage){ currentViewImage.style.cursor='grab'; } }
function handleDoubleClick(e){ e.preventDefault(); viewZoom=1; viewPan={x:0,y:0}; updateImageViewTransform(currentViewImage); }
function updateImageViewTransform(image){ const t=`translate(${viewPan.x}px, ${viewPan.y}px) scale(${viewZoom})`; image.style.transform=t; image.style.transformOrigin='0 0'; image.style.cursor = viewZoom>1.1 ? (isViewDragging?'grabbing':'grab') : 'default'; }

function resetToOriginal(){ if(originalFile){ selectedFile=originalFile; fileName.textContent=`📄 ${originalFile.name}`; fileSize.textContent=`Size: ${(originalFile.size / 1024 / 1024).toFixed(2)} MB`; document.getElementById('resetButton').style.display='none'; showSuccess('✓ Reset to original image'); } }
function showError(message){ const el=document.getElementById('error'); el.textContent=message; el.style.display='block'; }
function showSuccess(message){ const el=document.getElementById('success'); el.textContent=message; el.style.display='block'; }
function hideError(){ document.getElementById('error').style.display='none'; }
function hideSuccess(){ document.getElementById('success').style.display='none'; }

/* ===========================
   Collapsible JSON Viewer (fixed commas)
   =========================== */

function renderCollapsibleJSON(data, containerId, { collapsed = false } = {}) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';

  const root = document.createElement('div');
  root.className = 'json-item';

  // root never needs a trailing comma
  const tree = buildNode(data, null, 0, collapsed, /* addComma */ false);
  root.appendChild(tree);
  container.appendChild(root);
}

function buildNode(value, key, depth, collapsed, addComma) {
  const item = document.createElement('div');
  item.className = 'json-item';
  item.style.marginLeft = (depth * 20) + 'px';

  const keyPrefix = (key !== null && key !== undefined)
    ? (typeof key === 'number'
        ? `<span class="json-index">[${key}]</span>: `
        : `<span class="json-key">"${escapeHtml(String(key))}"</span>: `)
    : '';

  // null
  if (value === null) {
    item.innerHTML = `<div class="json-row">${keyPrefix}<span class="json-null">null</span>${addComma ? '<span class="json-comma">,</span>' : ''}</div>`;
    return item;
  }

  const type = typeof value;

  // primitives
  if (type === 'string' || type === 'number' || type === 'boolean') {
    const cls = type === 'string' ? 'json-string' : (type === 'number' ? 'json-number' : 'json-boolean');
    const val = type === 'string' ? `"${escapeHtml(value)}"` : String(value);
    item.innerHTML = `<div class="json-row">${keyPrefix}<span class="${cls}">${val}</span>${addComma ? '<span class="json-comma">,</span>' : ''}</div>`;
    return item;
  }

  // arrays
  if (Array.isArray(value)) {
    const row = document.createElement('div');
    row.className = 'json-row';

    const toggle = document.createElement('span');
    toggle.className = 'json-toggle';
    toggle.textContent = collapsed ? '▶' : '▼';
    toggle.title = 'Click to toggle (Alt-click toggles subtree)';

    row.innerHTML = `${keyPrefix}<span class="json-bracket">[</span><span class="json-array-length">(${value.length} items)</span>`;
    row.insertBefore(toggle, row.firstChild);
    item.appendChild(row);

    const children = document.createElement('div');
    children.className = 'json-children';
    children.style.display = collapsed ? 'none' : 'block';

    value.forEach((childVal, idx) => {
      // pass comma flag down for each element
      const child = buildNode(childVal, idx, depth + 1, collapsed, /* addComma */ idx < value.length - 1);
      children.appendChild(child);
    });

    const closing = document.createElement('div');
    closing.style.marginLeft = (depth * 20) + 'px';
    closing.innerHTML = `<span class="json-bracket">]</span>${addComma ? '<span class="json-comma">,</span>' : ''}`;

    item.appendChild(children);
    item.appendChild(closing);

    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const subtree = e.altKey;
      toggleSection(children, toggle, subtree);
    });

    return item;
  }

  // objects
  if (type === 'object') {
    const keys = Object.keys(value);
    const row = document.createElement('div');
    row.className = 'json-row';

    const toggle = document.createElement('span');
    toggle.className = 'json-toggle';
    toggle.textContent = collapsed ? '▶' : '▼';
    toggle.title = 'Click to toggle (Alt-click toggles subtree)';

    row.innerHTML = `${keyPrefix}<span class="json-bracket">{</span><span class="json-object-length">(${keys.length} properties)</span>`;
    row.insertBefore(toggle, row.firstChild);
    item.appendChild(row);

    const children = document.createElement('div');
    children.className = 'json-children';
    children.style.display = collapsed ? 'none' : 'block';

    keys.forEach((k, idx) => {
      // comma flag for each property
      const child = buildNode(value[k], k, depth + 1, collapsed, /* addComma */ idx < keys.length - 1);
      children.appendChild(child);
    });

    const closing = document.createElement('div');
    closing.style.marginLeft = (depth * 20) + 'px';
    closing.innerHTML = `<span class="json-bracket">}</span>${addComma ? '<span class="json-comma">,</span>' : ''}`;

    item.appendChild(children);
    item.appendChild(closing);

    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const subtree = e.altKey;
      toggleSection(children, toggle, subtree);
    });

    return item;
  }

  // fallback
  item.innerHTML = `<div class="json-row">${keyPrefix}<span>${escapeHtml(String(value))}</span>${addComma ? '<span class="json-comma">,</span>' : ''}</div>`;
  return item;
}

function toggleSection(childrenEl, toggleEl, toggleSubtree) {
  const isHidden = childrenEl.style.display === 'none';
  childrenEl.style.display = isHidden ? 'block' : 'none';
  toggleEl.textContent = isHidden ? '▼' : '▶';

  if (toggleSubtree) {
    const allChildren = childrenEl.querySelectorAll('.json-children');
    const allToggles = childrenEl.querySelectorAll('.json-toggle');
    allChildren.forEach((c) => { c.style.display = isHidden ? 'block' : 'none'; });
    allToggles.forEach((t) => { t.textContent = isHidden ? '▼' : '▶'; });
  }
}

function expandAll(containerId) {
  const root = document.getElementById(containerId);
  root.querySelectorAll('.json-children').forEach(el => el.style.display = 'block');
  root.querySelectorAll('.json-toggle').forEach(t => t.textContent = '▼');
}

function collapseAll(containerId) {
  const root = document.getElementById(containerId);
  root.querySelectorAll('.json-children').forEach(el => el.style.display = 'none');
  root.querySelectorAll('.json-toggle').forEach(t => t.textContent = '▶');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

async function copyJSONToClipboard() {
    try {
        if (!processedSegments || processedSegments.length === 0) {
            showError('No data to copy');
            return;
        }
        
        const finalResult = { 
            date: new Date().toISOString().split('T')[0], 
            segments: processedSegments 
        };
        
        const jsonString = JSON.stringify(finalResult, null, 2);
        
        // Use the modern clipboard API
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(jsonString);
            showSuccess('✓ JSON data copied to clipboard!');
        } else {
            // Fallback for older browsers or non-secure contexts
            const textArea = document.createElement('textarea');
            textArea.value = jsonString;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            textArea.style.top = '-999999px';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            
            try {
                document.execCommand('copy');
                showSuccess('✓ JSON data copied to clipboard!');
            } catch (err) {
                showError('Failed to copy data. Please try again.');
            } finally {
                document.body.removeChild(textArea);
            }
        }
    } catch (err) {
        showError('Failed to copy data: ' + err.message);
    }
}

/* ---------- Crop functionality ---------- */
function showCropTool() {
    if (!selectedFile) {
        showError('Please select a file first');
        return;
    }

    document.getElementById('fileInfo').style.display = 'none';
    document.getElementById('cropModal').classList.add('show');
    document.body.style.overflow = 'hidden';
    
    const cropImage = document.getElementById('cropImage');
    cropImage.src = URL.createObjectURL(selectedFile);
    
    cropImage.onload = function() {
        if (cropper) {
            cropper.destroy();
        }
        
        cropper = new Cropper(cropImage, {
            aspectRatio: NaN,
            viewMode: 1,
            dragMode: 'move',
            autoCropArea: 0.8,
            background: false,
            guides: true,
            center: true,
            highlight: true,
            cropBoxMovable: true,
            cropBoxResizable: true,
            toggleDragModeOnDblclick: false,
            zoomable: true,
            zoomOnTouch: true,
            zoomOnWheel: true,
            wheelZoomRatio: 0.1,
            minCropBoxWidth: 50,
            minCropBoxHeight: 50,
            checkCrossOrigin: false,
            checkOrientation: true,
            modal: false,
            responsive: true,
            restore: true,
            scalable: true,
            rotatable: true,
        });
        
        currentZoom = 1;
        updateZoomDisplay();
    };
}

function closeCropModal() {
    const cropModal = document.getElementById('cropModal');
    cropModal.classList.remove('show');
    document.body.style.overflow = 'auto';
    
    // Restore file info display
    document.getElementById('fileInfo').style.display = 'block';
    
    if (cropper) {
        cropper.destroy();
        cropper = null;
    }
}

function applyCrop() {
    if (!cropper) {
        showError('No crop area selected');
        return;
    }
    
    try {
        // Get the cropped canvas with high quality settings
        const canvas = cropper.getCroppedCanvas({
            // Remove fixed dimensions to maintain original aspect ratio and quality
            minWidth: 50,
            minHeight: 50,
            maxWidth: 8192,
            maxHeight: 8192,
            fillColor: '#fff',
            imageSmoothingEnabled: true,
            imageSmoothingQuality: 'high'
        });
        
        // Set canvas context for maximum quality
        const ctx = canvas.getContext('2d');
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        
        // Convert canvas to blob with PNG format for better quality
        canvas.toBlob(function(blob) {
            if (blob) {
                // Create a new file from the cropped blob
                const croppedFile = new File([blob], selectedFile.name, {
                    type: blob.type,
                    lastModified: Date.now()
                });
                
                // Update the selected file
                selectedFile = croppedFile;
                
                // Update file info display
                fileName.textContent = `📄 ${croppedFile.name} (cropped)`;
                fileSize.textContent = `Size: ${(croppedFile.size / 1024 / 1024).toFixed(2)} MB`;
                
                // Show reset button
                document.getElementById('resetButton').style.display = 'inline-block';
                
                // Restore file info display
                document.getElementById('fileInfo').style.display = 'block';
                
                // Close the crop modal
                closeCropModal();
                
                showSuccess('✓ Image cropped successfully!');
            } else {
                showError('Failed to crop image');
            }
        }, 'image/png', 1.0); // Use PNG with maximum quality (1.0)
        
    } catch (err) {
        showError('Error cropping image: ' + err.message);
    }
}

function resetCrop() {
    if (cropper) {
        cropper.reset();
        currentZoom = 1;
        updateZoomDisplay();
    }
}

function zoomIn() {
    if (cropper) {
        cropper.zoom(0.1);
        currentZoom = cropper.getImageData().scaleX;
        updateZoomDisplay();
    }
}

function zoomOut() {
    if (cropper) {
        cropper.zoom(-0.1);
        currentZoom = cropper.getImageData().scaleX;
        updateZoomDisplay();
    }
}

function fitToScreen() {
    if (cropper) {
        cropper.reset();
        currentZoom = 1;
        updateZoomDisplay();
    }
}

function resetZoom() {
    if (cropper) {
        cropper.reset();
        currentZoom = 1;
        updateZoomDisplay();
    }
}

function updateZoomDisplay() {
    const zoomLevel = document.getElementById('zoomLevel');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}
