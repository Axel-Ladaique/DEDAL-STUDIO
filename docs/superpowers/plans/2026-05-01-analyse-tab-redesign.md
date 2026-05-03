# ANALYSE Tab Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken A/B slot system in the ANALYSE tab with a sidebar navigation + full-screen widget layout, status badges, PID range selector, and an optional toggle map.

**Architecture:** `#pane-analyse` gets a new `#an-layout` (flex row) = `#an-sidebar` (175 px) + `#an-content` (flex:1, 6 panels one at a time) + `#an-map-panel` (220 px, toggle). Widget HTML moves directly into each panel — no cloning. All existing render functions (`rebuildPIDCharts`, `rebuildVibPanel`, etc.) are reused unchanged except for two-line edits to PID x-axis range.

**Tech Stack:** HTML/CSS/JS vanilla, Chart.js (existing), Leaflet (existing), Canvas API (existing)

---

## File Map

- Modify: `web/viewer.html` — all changes (CSS lines ~82–486, HTML lines ~1890–2344, JS lines ~4727–4760, ~10936–11009)

---

### Task 1: Remove old A/B system HTML

**Files:**
- Modify: `web/viewer.html:1892–2342`

- [ ] **Step 1: Delete `#analyse-selector` chip bar**

  In `web/viewer.html`, delete lines 1892–1913 (the `<div id="analyse-selector">` block, including both `#an-chips-a` and `#an-chips-b`).

- [ ] **Step 2: Delete `#an-sources` hidden cloning pool**

  Delete lines 1915–2318 (the `<div id="an-sources" style="display:none;">` block, containing `#an-src-pid`, `#an-src-traj`, `#an-src-ekf`, `#an-src-energy`, `#an-src-fft`, `#an-src-motor`).

- [ ] **Step 3: Delete `#analyse-panels` display area**

  Delete lines 2320–2342 (the `<div id="analyse-panels">` block, containing `#an-empty`, `#an-panel-a`, `#an-panel-b`).

  After these deletions, `#pane-analyse` should be an empty div:
  ```html
  <div class="tab-pane" id="pane-analyse">
  
  </div><!-- /pane-analyse -->
  ```

- [ ] **Step 4: Verify in browser**

  Start the server. Click the ANALYSE tab. It should show a blank pane with no errors in the console related to `an-panel-a`, `an-panel-b`, or `an-empty`.

- [ ] **Step 5: Commit**

  ```bash
  git add web/viewer.html
  git commit -m "refactor(analyse): remove A/B slot HTML (chips, sources, panels)"
  ```

---

### Task 2: Remove old A/B system CSS

**Files:**
- Modify: `web/viewer.html:455–486`

- [ ] **Step 1: Delete `.an-*` CSS rules**

  Delete the following CSS rules (lines 455–486):
  ```css
  .an-slot-lbl { ... }
  .an-slot-a { ... }
  .an-slot-b { ... }
  .an-chip { ... }
  .an-chip:hover { ... }
  .an-chip.an-sel-a { ... }
  .an-chip.an-sel-b { ... }
  .an-slot-sep { ... }
  #analyse-panels { ... }
  .an-panel-wrap { ... }
  .an-panel-header { ... }
  .an-panel-title { ... }
  .an-panel-title.a { ... }
  .an-panel-title.b { ... }
  .an-panel-body { ... }
  .an-empty { ... }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add web/viewer.html
  git commit -m "refactor(analyse): remove A/B slot CSS"
  ```

---

### Task 3: Remove old A/B system JS

**Files:**
- Modify: `web/viewer.html` (JS, near lines 10936–11000)

- [ ] **Step 1: Delete `AN_DEFS` and slot variables**

  Delete the block at lines 10936–10947:
  ```js
  // ── ANALYSE TAB CHIP SELECTOR ──
  var AN_DEFS = {
    pid:    { title: '📐 ANALYSE PID', ... },
    ...
  };
  var anSlotA = 'pid';
  var anSlotB = 'fft';
  ```

- [ ] **Step 2: Delete `selectAnalysis`, `renderAnalysisPanels`, `injectAnalysisPanel`**

  Delete lines 10949–10990 (the three functions).

- [ ] **Step 3: Update `boot()` — replace `renderAnalysisPanels()`**

  In `boot()` (around line 11000), change:
  ```js
  renderAnalysisPanels();
  ```
  To:
  ```js
  showAnalysis('energy');
  ```

- [ ] **Step 4: Update tab-switch handler — replace `renderAnalysisPanels()`**

  Around line 10142–10143, change:
  ```js
  if (t.dataset.tab === 'analyse') {
    renderAnalysisPanels();
  }
  ```
  To:
  ```js
  if (t.dataset.tab === 'analyse') {
    showAnalysis(typeof anCurrentKey !== 'undefined' ? anCurrentKey : 'energy');
  }
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add web/viewer.html
  git commit -m "refactor(analyse): remove A/B slot JS (AN_DEFS, selectAnalysis, renderAnalysisPanels, injectAnalysisPanel)"
  ```

---

### Task 4: New CSS for ANALYSE layout

**Files:**
- Modify: `web/viewer.html` (CSS section, after line 486)

- [ ] **Step 1: Insert new CSS block**

  After the deleted `.an-*` rules (around line 486), insert:

  ```css
  /* ─── ANALYSE TAB REDESIGN ─── */
  #an-layout {
    display: flex; flex: 1; min-height: 0; overflow: hidden;
  }
  #an-sidebar {
    width: 175px; flex-shrink: 0;
    background: var(--surface2); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; padding: 4px 0; overflow-y: auto;
  }
  .an-sidebar-item {
    padding: 7px 10px; display: flex; justify-content: space-between; align-items: center;
    cursor: pointer; font-family: var(--font-mono); font-size: 11px; color: var(--dim2);
    transition: background .12s, color .12s; border-left: 2px solid transparent;
    user-select: none;
  }
  .an-sidebar-item:hover { background: rgba(255,255,255,0.03); color: var(--text); }
  .an-sidebar-item.active {
    background: rgba(0,212,255,0.08); border-left-color: var(--accent); color: var(--accent);
  }
  .an-badge {
    font-family: var(--font-mono); font-size: 9px; border-radius: 3px; padding: 1px 5px; display: none;
  }
  .an-badge.ok   { display: inline; background: rgba(57,255,20,0.12);  color: #39ff14; }
  .an-badge.warn { display: inline; background: rgba(255,204,0,0.15);  color: #ffcc00; }
  .an-badge.crit { display: inline; background: rgba(255,107,53,0.12); color: #ff6b35; }
  #an-content {
    flex: 1; min-width: 0; overflow: hidden; display: flex; flex-direction: column;
  }
  .an-panel { display: none; flex-direction: column; height: 100%; overflow: hidden; }
  .an-panel.active { display: flex; }
  .an-panel-hdr {
    padding: 6px 12px; border-bottom: 1px solid var(--border); background: var(--surface2);
    display: flex; align-items: center; gap: 10px; flex-shrink: 0;
  }
  .an-panel-ttl { font-family: var(--font-hud); font-size: 10px; letter-spacing: 2px; color: var(--accent); }
  .an-panel-body { flex: 1; overflow: auto; }
  .an-map-btn {
    margin-left: auto; background: rgba(0,212,255,0.08); color: var(--accent);
    border: 1px solid var(--border); border-radius: 3px; padding: 2px 8px;
    font-size: 9px; cursor: pointer; font-family: var(--font-mono);
  }
  .an-map-btn:hover  { background: rgba(0,212,255,0.15); }
  .an-map-btn.active { background: rgba(0,212,255,0.2); border-color: var(--accent); }
  #an-map-panel {
    width: 220px; flex-shrink: 0; border-left: 1px solid var(--border);
    background: var(--surface2); display: flex; flex-direction: column;
  }
  .an-map-hdr {
    padding: 6px 10px; border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center;
    font-size: 9px; color: var(--dim); font-family: var(--font-mono); flex-shrink: 0;
  }
  #an-map-div { flex: 1; min-height: 0; }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add web/viewer.html
  git commit -m "feat(analyse): add CSS for new sidebar/panel/map layout"
  ```

---

### Task 5: New `#pane-analyse` HTML structure

**Files:**
- Modify: `web/viewer.html:1890`

This task replaces the empty `#pane-analyse` with the full new structure. Widget panel bodies contain the original HTML from each `#an-src-*` div (the inner `.panel` div, without the outer `div style="padding: 0 20px 20px;"` wrapper). The PID panel gets an extra range selector canvas added below `#pid-canvas-main`.

- [ ] **Step 1: Replace `#pane-analyse` contents with new layout skeleton**

  Replace everything between `<div class="tab-pane" id="pane-analyse">` and `</div><!-- /pane-analyse -->` with:

  ```html
  <div class="tab-pane" id="pane-analyse">
    <div id="an-layout">

      <!-- ── Sidebar ── -->
      <div id="an-sidebar">
        <div class="an-sidebar-item" data-key="energy" onclick="showAnalysis('energy')">
          <span>⚡ ÉNERGIE</span><span class="an-badge" id="an-badge-energy"></span>
        </div>
        <div class="an-sidebar-item" data-key="pid" onclick="showAnalysis('pid')">
          <span>📐 PID</span><span class="an-badge" id="an-badge-pid"></span>
        </div>
        <div class="an-sidebar-item" data-key="fft" onclick="showAnalysis('fft')">
          <span>〰 VIBRATIONS</span><span class="an-badge" id="an-badge-fft"></span>
        </div>
        <div class="an-sidebar-item" data-key="ekf" onclick="showAnalysis('ekf')">
          <span>🧭 EKF</span><span class="an-badge" id="an-badge-ekf"></span>
        </div>
        <div class="an-sidebar-item" data-key="traj" onclick="showAnalysis('traj')">
          <span>🌐 TRAJECTOIRE</span><span class="an-badge" id="an-badge-traj"></span>
        </div>
        <div class="an-sidebar-item" data-key="motor" onclick="showAnalysis('motor')">
          <span>🔧 MOTEUR</span><span class="an-badge" id="an-badge-motor"></span>
        </div>
      </div>

      <!-- ── Content area (6 panels, one active at a time) ── -->
      <div id="an-content">

        <!-- ⚡ ÉNERGIE -->
        <div class="an-panel" id="an-panel-energy">
          <div class="an-panel-hdr">
            <span class="an-panel-ttl">⚡ ÉNERGIE & BATTERIE</span>
            <button class="an-map-btn" onclick="toggleAnMap()">🗺 CARTE</button>
          </div>
          <div class="an-panel-body">
            <!-- paste inner .panel div from former #an-src-energy here (see Step 2) -->
          </div>
        </div>

        <!-- 📐 PID -->
        <div class="an-panel" id="an-panel-pid">
          <div class="an-panel-hdr">
            <span class="an-panel-ttl">📐 ANALYSE PID</span>
            <button class="an-map-btn" onclick="toggleAnMap()">🗺 CARTE</button>
          </div>
          <div class="an-panel-body">
            <!-- paste inner .panel div from former #an-src-pid here (see Step 3) -->
            <!-- then add range selector canvas after the pid-canvas-main wrapper (see Step 4) -->
          </div>
        </div>

        <!-- 〰 VIBRATIONS -->
        <div class="an-panel" id="an-panel-fft">
          <div class="an-panel-hdr">
            <span class="an-panel-ttl">〰 VIBRATIONS</span>
            <button class="an-map-btn" onclick="toggleAnMap()">🗺 CARTE</button>
          </div>
          <div class="an-panel-body">
            <!-- paste inner .panel div from former #an-src-fft here -->
          </div>
        </div>

        <!-- 🧭 EKF -->
        <div class="an-panel" id="an-panel-ekf">
          <div class="an-panel-hdr">
            <span class="an-panel-ttl">🧭 EKF</span>
            <button class="an-map-btn" onclick="toggleAnMap()">🗺 CARTE</button>
          </div>
          <div class="an-panel-body">
            <!-- paste inner .panel div from former #an-src-ekf here -->
          </div>
        </div>

        <!-- 🌐 TRAJECTOIRE -->
        <div class="an-panel" id="an-panel-traj">
          <div class="an-panel-hdr">
            <span class="an-panel-ttl">🌐 TRAJECTOIRE</span>
            <button class="an-map-btn" onclick="toggleAnMap()">🗺 CARTE</button>
          </div>
          <div class="an-panel-body">
            <!-- paste inner .panel div from former #an-src-traj here -->
          </div>
        </div>

        <!-- 🔧 MOTEUR -->
        <div class="an-panel" id="an-panel-motor">
          <div class="an-panel-hdr">
            <span class="an-panel-ttl">🔧 MOTEUR</span>
            <button class="an-map-btn" onclick="toggleAnMap()">🗺 CARTE</button>
          </div>
          <div class="an-panel-body">
            <!-- paste inner .panel div from former #an-src-motor here -->
          </div>
        </div>

      </div><!-- /an-content -->

      <!-- ── Optional map panel (hidden by default) ── -->
      <div id="an-map-panel" style="display:none;">
        <div class="an-map-hdr">
          <span>🗺 CARTE</span>
          <span onclick="toggleAnMap()" style="cursor:pointer;">✕</span>
        </div>
        <div id="an-map-div"></div>
      </div>

    </div><!-- /an-layout -->
  </div><!-- /pane-analyse -->
  ```

- [ ] **Step 2: Fill ÉNERGIE, VIBRATIONS, EKF, TRAJECTOIRE, MOTEUR panel bodies**

  For each of the 5 panels (not PID), copy the inner `.panel` div from its former `#an-src-*` location into the `.an-panel-body`. The inner div starts with `<div class="panel">` and ends with `</div>`. Do NOT include the outer `<div style="padding: 0 20px 20px;">` wrapper — drop it.

  Mapping (old source → new location):
  - `#an-src-energy` inner `.panel` → `#an-panel-energy .an-panel-body`
  - `#an-src-fft` inner `.panel` → `#an-panel-fft .an-panel-body`
  - `#an-src-ekf` inner `.panel` → `#an-panel-ekf .an-panel-body`
  - `#an-src-traj` inner `.panel` → `#an-panel-traj .an-panel-body`
  - `#an-src-motor` inner `.panel` → `#an-panel-motor .an-panel-body`

- [ ] **Step 3: Fill PID panel body (without range selector)**

  Copy the inner `.panel` div from `#an-src-pid` into `#an-panel-pid .an-panel-body`. Drop the outer `<div style="padding: 0 20px 20px;">` wrapper.

- [ ] **Step 4: Add PID range selector canvas**

  Inside `#an-panel-pid .an-panel-body`, inside the `.panel-body`, inside the left column `<div style="display:flex;flex-direction:column;">`, after the `<div style="position:relative;flex:1;min-height:200px;...">` canvas wrapper and after the values readout div (`#pid-main-cur`), insert:

  ```html
  <!-- PID range selector -->
  <div style="position:relative;background:#020508;border:1px solid var(--border);border-radius:4px;overflow:hidden;cursor:crosshair;margin-top:6px;" id="pid-selector-wrap">
    <canvas id="pid-selector-canvas" style="display:block;width:100%;height:44px;"></canvas>
    <div id="pid-selection-box" style="position:absolute;top:0;bottom:0;background:rgba(0,212,255,0.12);border-left:1px solid rgba(0,212,255,0.6);border-right:1px solid rgba(0,212,255,0.6);pointer-events:none;display:none;"></div>
    <div id="pid-cursor-line-sel" style="position:absolute;top:0;bottom:0;width:1px;background:rgba(255,255,255,0.35);pointer-events:none;display:none;"></div>
  </div>
  <div style="display:flex;align-items:center;justify-content:space-between;margin-top:2px;">
    <span style="font-family:var(--font-mono);font-size:9px;color:var(--dim);" id="pid-range-info">tout le vol</span>
    <button onclick="pidResetRange()" style="background:transparent;border:1px solid var(--border);color:var(--dim);border-radius:3px;padding:1px 6px;cursor:pointer;font-family:var(--font-mono);font-size:9px;">↺ RESET</button>
  </div>
  ```

- [ ] **Step 5: Test in browser**

  Start the server. Click the ANALYSE tab. You should see the sidebar on the left with 6 items. Clicking each should (not yet switch panels since `showAnalysis` isn't written). No JS errors about missing elements.

- [ ] **Step 6: Commit**

  ```bash
  git add web/viewer.html
  git commit -m "feat(analyse): new #pane-analyse HTML structure with sidebar and 6 panels"
  ```

---

### Task 6: `showAnalysis(key)` routing function + PID range selector JS

**Files:**
- Modify: `web/viewer.html` (JS, after the removed AN_DEFS block, near line 10936)

- [ ] **Step 1: Insert `showAnalysis` and PID range selector JS**

  At the location where `AN_DEFS` was (around line 10936), insert the following block:

  ```js
  // ════════════════════════════════════════════════════
  //  ANALYSE TAB NAVIGATION
  // ════════════════════════════════════════════════════
  var anCurrentKey = 'energy';

  function showAnalysis(key) {
    anCurrentKey = key;
    document.querySelectorAll('.an-sidebar-item').forEach(function(el) {
      el.classList.toggle('active', el.dataset.key === key);
    });
    document.querySelectorAll('.an-panel').forEach(function(el) {
      el.classList.toggle('active', el.id === 'an-panel-' + key);
    });
    var mapPanel = document.getElementById('an-map-panel');
    var mapVisible = mapPanel && mapPanel.style.display !== 'none';
    document.querySelectorAll('.an-map-btn').forEach(function(btn) {
      btn.classList.toggle('active', mapVisible);
    });
    if (!flightData.length) return;
    ({
      energy: function() { if(typeof rebuildEnergyPanel==='function') rebuildEnergyPanel(); },
      pid:    function() {
                if(typeof rebuildPIDCharts==='function') rebuildPIDCharts();
                if(typeof runPIDAdvisor==='function') runPIDAdvisor();
                buildPIDSelector();
              },
      fft:    function() { if(typeof rebuildVibPanel==='function') rebuildVibPanel(); },
      ekf:    function() { if(typeof buildEKFChart==='function') buildEKFChart(); },
      traj:   function() { if(typeof rebuildGPS3D==='function') rebuildGPS3D(); },
      motor:  function() { if(typeof rebuildMotorPerfPanel==='function') rebuildMotorPerfPanel(); }
    }[key] || function(){})();
  }

  window.showAnalysis = showAnalysis;

  // ── PID range selector ──────────────────────────────
  var pidRangeStart = null;
  var pidRangeEnd   = null;

  function pidResetRange() {
    pidRangeStart = null; pidRangeEnd = null;
    var info = document.getElementById('pid-range-info');
    if (info) info.textContent = 'tout le vol';
    if (typeof rebuildPIDCharts === 'function') rebuildPIDCharts();
  }
  window.pidResetRange = pidResetRange;

  function buildPIDSelector() {
    var canvas = document.getElementById('pid-selector-canvas');
    var wrap   = document.getElementById('pid-selector-wrap');
    if (!canvas || !wrap || !flightData.length) return;

    var W = wrap.offsetWidth || 700;
    var H = 44;
    canvas.width = W; canvas.height = H;
    var ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, W, H);

    var pts  = flightData.slice(viewStart, viewEnd + 1);
    var step = Math.max(1, Math.floor(pts.length / W));

    pts.forEach(function(r, i) {
      if (i % step !== 0) return;
      var x = Math.floor(i / pts.length * W);
      var armed = r.armed === 1 || r.armed === '1';
      var fm = +(r.flight_mode || 0);
      ctx.fillStyle = !armed ? 'rgba(255,255,255,0.02)'
        : fm === 2 ? 'rgba(255,107,53,0.18)'
        : fm === 1 ? 'rgba(255,204,0,0.14)'
        : 'rgba(57,255,20,0.12)';
      ctx.fillRect(x, 0, Math.max(1, step) + 1, H);
    });

    var col  = (typeof PID_AXES !== 'undefined' && PID_AXES[pidActiveAxis])
                 ? PID_AXES[pidActiveAxis].imu : 'roll_IMU';
    var vals = pts.filter(function(_, i) { return i % step === 0; })
                  .map(function(r) { return +(r[col] || 0); });
    if (vals.length > 1) {
      var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals), rng = (mx - mn) || 1;
      [['rgba(0,0,0,0.6)', 3], ['#00d4ff', 1.5]].forEach(function(pair) {
        ctx.beginPath();
        vals.forEach(function(v, i) {
          var x = i / (vals.length - 1) * W;
          var y = H - 4 - (v - mn) / rng * (H - 8);
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });
        ctx.strokeStyle = pair[0]; ctx.lineWidth = pair[1]; ctx.stroke();
      });
    }

    updatePIDSelectionBox();
    if (!wrap._pidSetup) { wrap._pidSetup = true; attachPIDSelector(canvas, wrap); }
  }

  function attachPIDSelector(canvas, wrap) {
    var dragging = false, dragX0 = 0;
    function fracToIdx(frac) {
      return Math.round(viewStart + Math.max(0, Math.min(1, frac)) * (viewEnd - viewStart));
    }
    function getCanvasFrac(e) {
      var rect = canvas.getBoundingClientRect();
      return (e.clientX - rect.left) / rect.width;
    }
    canvas.addEventListener('mousedown', function(e) {
      dragging = true; dragX0 = e.clientX;
      pidRangeStart = fracToIdx(getCanvasFrac(e)); pidRangeEnd = pidRangeStart;
      updatePIDSelectionBox();
    });
    canvas.addEventListener('mousemove', function(e) {
      var curLine = document.getElementById('pid-cursor-line-sel');
      var x = e.clientX - canvas.getBoundingClientRect().left;
      if (curLine) { curLine.style.display = 'block'; curLine.style.left = x + 'px'; }
      if (!dragging) return;
      var frac2 = getCanvasFrac(e);
      var idx2  = fracToIdx(frac2);
      var frac1 = (dragX0 - canvas.getBoundingClientRect().left) / canvas.getBoundingClientRect().width;
      var idx1  = fracToIdx(Math.max(0, Math.min(1, frac1)));
      pidRangeStart = Math.min(idx1, idx2); pidRangeEnd = Math.max(idx1, idx2);
      updatePIDSelectionBox();
    });
    canvas.addEventListener('mouseup', function() {
      if (!dragging) return; dragging = false;
      if (pidRangeEnd - pidRangeStart < 10) {
        pidRangeStart = null; pidRangeEnd = null;
        var info = document.getElementById('pid-range-info');
        if (info) info.textContent = 'tout le vol';
        updatePIDSelectionBox();
      } else {
        var t0 = flightData[pidRangeStart].timestamp_us / 1e6;
        var t1 = flightData[pidRangeEnd].timestamp_us / 1e6;
        var info = document.getElementById('pid-range-info');
        if (info) info.textContent = t0.toFixed(1) + 's → ' + t1.toFixed(1) + 's  (' + (t1-t0).toFixed(1) + 's)';
      }
      if (typeof rebuildPIDCharts === 'function') rebuildPIDCharts();
    });
    canvas.addEventListener('mouseleave', function() {
      var curLine = document.getElementById('pid-cursor-line-sel');
      if (curLine) curLine.style.display = 'none';
      if (dragging) { dragging = false; if (typeof rebuildPIDCharts === 'function') rebuildPIDCharts(); }
    });
    canvas.addEventListener('dblclick', function() { pidResetRange(); });
  }

  function updatePIDSelectionBox() {
    var box    = document.getElementById('pid-selection-box');
    var canvas = document.getElementById('pid-selector-canvas');
    if (!box || !canvas) return;
    if (pidRangeStart === null || pidRangeEnd === null) { box.style.display = 'none'; return; }
    var W = canvas.width || canvas.offsetWidth || 1;
    var total = viewEnd - viewStart || 1;
    var x1 = (pidRangeStart - viewStart) / total * W;
    var x2 = (pidRangeEnd   - viewStart) / total * W;
    box.style.display = 'block';
    box.style.left    = x1 + 'px';
    box.style.width   = Math.max(2, x2 - x1) + 'px';
  }
  ```

- [ ] **Step 2: Wire PID range into `rebuildPIDCharts()`**

  In `rebuildPIDCharts()` (around line 4832), change the x-axis `min`/`max` lines:

  ```js
  // Before:
  min: pidWindow !== 'all' ? flightData[currentIdx].timestamp_us/1e6 - (+pidWindow) : undefined,
  max: pidWindow !== 'all' ? flightData[currentIdx].timestamp_us/1e6 + (+pidWindow) : undefined,

  // After:
  min: pidRangeStart !== null ? flightData[pidRangeStart].timestamp_us/1e6
       : (pidWindow !== 'all' ? flightData[currentIdx].timestamp_us/1e6 - (+pidWindow) : undefined),
  max: pidRangeEnd !== null ? flightData[pidRangeEnd].timestamp_us/1e6
       : (pidWindow !== 'all' ? flightData[currentIdx].timestamp_us/1e6 + (+pidWindow) : undefined),
  ```

- [ ] **Step 3: Make `updatePIDWindow()` respect range selector**

  In `updatePIDWindow()` (line 4727), insert an early-return after the first guard:

  ```js
  function updatePIDWindow() {
    if (typeof pidRangeStart !== 'undefined' && pidRangeStart !== null) {
      updatePIDCursors(); return;
    }
    if(!pidChart || !flightData.length) { rebuildPIDCharts(); return; }
    // ... rest unchanged
  ```

- [ ] **Step 4: Test navigation**

  Load a flight. Click ANALYSE tab. Click each sidebar item and verify: the sidebar item highlights, the widget renders correctly (no blank/broken panels), and the PID range selector canvas is visible below the PID chart.

- [ ] **Step 5: Test PID range selector**

  On the PID analysis, drag across the range selector canvas. The PID chart should zoom to the selected range. Click ↺ RESET to return to full view.

- [ ] **Step 6: Commit**

  ```bash
  git add web/viewer.html
  git commit -m "feat(analyse): showAnalysis() routing + PID range selector canvas"
  ```

---

### Task 7: `computeAnalysisBadges()` — auto-computed status badges

**Files:**
- Modify: `web/viewer.html` (JS, after the `showAnalysis` block; also near `initFlight` and `applyViewFilterCore`)

- [ ] **Step 1: Insert badge computation function**

  After the `updatePIDSelectionBox` function (still in the ANALYSE TAB section), insert:

  ```js
  // ── Analysis status badges ──────────────────────────
  var AN_VBAT_OK   = 3.7;  // V/cell — below = warn
  var AN_VBAT_CRIT = 3.5;  // V/cell — below = crit
  var AN_PID_RMSE  = 5.0;  // degrees — above = warn
  var AN_VIB_AMP   = 0.3;  // G (|AccZ|) — above = HIGH
  var AN_MOTOR_IMB = 0.15; // |M1-M3|/avg — above = IMBAL

  function setBadge(key, cls, text) {
    var el = document.getElementById('an-badge-' + key);
    if (!el) return;
    el.className = 'an-badge ' + cls;
    el.textContent = text;
  }

  function computeAnalysisBadges() {
    if (!flightData.length) return;
    var cells = +(flightConfig['CELLS'] || 6);

    // ÉNERGIE
    var vbatArmed = flightData.filter(function(r) {
      return (r.armed===1||r.armed==='1') && r.vbat_V > 0;
    }).map(function(r) { return r.vbat_V / cells; });
    if (vbatArmed.length) {
      var minVcell = Math.min.apply(null, vbatArmed);
      if (minVcell < AN_VBAT_CRIT)      setBadge('energy', 'crit', '✗ CRIT');
      else if (minVcell < AN_VBAT_OK)   setBadge('energy', 'warn', '⚠ LOW');
      else                               setBadge('energy', 'ok',   'OK');
    }

    // PID — RMSE of setpoint vs IMU for each axis
    var pidWarnAxis = null;
    ['roll','pitch','yaw'].forEach(function(axis) {
      if (pidWarnAxis) return;
      var cfg = (typeof PID_AXES !== 'undefined') ? PID_AXES[axis] : null;
      if (!cfg) return;
      var armed = flightData.filter(function(r) { return r.armed===1||r.armed==='1'; });
      if (!armed.length) return;
      var sum2 = armed.reduce(function(s, r) {
        var e = +(r[cfg.des]||0) - +(r[cfg.imu]||0); return s + e*e;
      }, 0);
      if (Math.sqrt(sum2 / armed.length) > AN_PID_RMSE) pidWarnAxis = axis.toUpperCase();
    });
    if (pidWarnAxis) setBadge('pid', 'warn', '⚠ ' + pidWarnAxis);
    else             setBadge('pid', 'ok',   'OK');

    // VIBRATIONS — peak |AccZ| in armed segments
    var accArmed = flightData.filter(function(r) {
      return r.armed===1||r.armed==='1';
    }).map(function(r) { return Math.abs(+(r.AccZ||0)); });
    if (accArmed.length) {
      if (Math.max.apply(null, accArmed) > AN_VIB_AMP) setBadge('fft', 'warn', '⚠ HIGH');
      else                                               setBadge('fft', 'ok',   'OK');
    }

    // EKF
    var hasGPS = flightData.some(function(r) { return r.gps_valid===1||r.gps_valid==='1'; });
    setBadge('ekf', hasGPS ? 'ok' : 'warn', hasGPS ? 'OK' : '⚠ NO GPS');

    // TRAJECTOIRE
    var gpsPts = flightData.filter(function(r) { return r.gps_valid===1||r.gps_valid==='1'; }).length;
    if (gpsPts > 0) setBadge('traj', 'ok',   gpsPts + ' pts');
    else            setBadge('traj', 'crit', 'NO GPS');

    // MOTEUR — mean |M1-M3|/avg imbalance
    var motorArmed = flightData.filter(function(r) {
      return (r.armed===1||r.armed==='1') && +(r.m1_PWM||0) > 0 && +(r.m3_PWM||0) > 0;
    });
    if (motorArmed.length) {
      var totalImb = motorArmed.reduce(function(s, r) {
        var m1 = +(r.m1_PWM||0), m3 = +(r.m3_PWM||0), avg = (m1+m3)/2;
        return s + (avg > 0 ? Math.abs(m1-m3)/avg : 0);
      }, 0);
      if (totalImb / motorArmed.length > AN_MOTOR_IMB) setBadge('motor', 'warn', '⚠ IMBAL');
      else                                               setBadge('motor', 'ok',   'OK');
    }
  }

  window.computeAnalysisBadges = computeAnalysisBadges;
  ```

- [ ] **Step 2: Call `computeAnalysisBadges()` in `initFlight()`**

  In `initFlight()` (starting at line 2688), find the section after flight data is loaded and header stats are computed (around line 2740, after `document.getElementById('hdr-vbat')...`). Add:

  ```js
  computeAnalysisBadges();
  ```

- [ ] **Step 3: Call `computeAnalysisBadges()` in `applyViewFilterCore()`**

  In `applyViewFilterCore()` (starting at line 5537), find the end of the function body. Add:

  ```js
  computeAnalysisBadges();
  ```

- [ ] **Step 4: Test badges**

  Load a flight with GPS data. Click the ANALYSE tab. Each sidebar item should show a colored badge: ÉNERGIE (OK/LOW/CRIT), PID (OK or ⚠ ROLL/PITCH/YAW), VIBRATIONS (OK or ⚠ HIGH), EKF (OK or ⚠ NO GPS), TRAJECTOIRE (N pts or NO GPS), MOTEUR (OK or ⚠ IMBAL).

- [ ] **Step 5: Commit**

  ```bash
  git add web/viewer.html
  git commit -m "feat(analyse): computeAnalysisBadges() with auto status badges in sidebar"
  ```

---

### Task 8: Analyse map toggle (`toggleAnMap()`)

**Files:**
- Modify: `web/viewer.html` (JS, after `computeAnalysisBadges`; also in `render()`)

- [ ] **Step 1: Insert `toggleAnMap()` and map helper functions**

  After `computeAnalysisBadges`, insert:

  ```js
  // ── Analyse map (toggle, lazy Leaflet init) ──────────
  var anMap       = null;
  var anMapMarker = null;
  var anMapTrack  = null;

  function toggleAnMap() {
    var panel = document.getElementById('an-map-panel');
    if (!panel) return;
    var show = panel.style.display === 'none';
    panel.style.display = show ? 'flex' : 'none';
    document.querySelectorAll('.an-map-btn').forEach(function(btn) {
      btn.classList.toggle('active', show);
    });
    if (show) {
      if (!anMap) {
        setTimeout(function() {
          anMap = L.map('an-map-div', { zoomControl: true, attributionControl: false });
          L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(anMap);
          if (flightData.length) buildAnMapTrack();
        }, 80);
      } else {
        setTimeout(function() { anMap.invalidateSize(); }, 80);
      }
    }
  }
  window.toggleAnMap = toggleAnMap;

  function buildAnMapTrack() {
    if (!anMap || !flightData.length) return;
    var pts = flightData
      .filter(function(r) { return r.gps_valid===1||r.gps_valid==='1'; })
      .map(function(r) { return [+(r.gps_lat||0), +(r.gps_lon||0)]; });
    if (!pts.length) return;
    if (anMapTrack) { anMap.removeLayer(anMapTrack); anMapTrack = null; }
    anMapTrack = L.polyline(pts, { color:'#00d4ff', weight:2, opacity:0.7 }).addTo(anMap);
    anMap.fitBounds(anMapTrack.getBounds(), { padding:[20,20] });
  }
  ```

- [ ] **Step 2: Sync analyse map marker in `render()`**

  In the `render()` function, after the existing map marker update block (where `droneMarker` is updated), add:

  ```js
  // Sync analyse map marker
  if (anMap && flightData[currentIdx]) {
    var _anR = flightData[currentIdx];
    if (_anR.gps_valid===1||_anR.gps_valid==='1') {
      var _anLL = [+(_anR.gps_lat||0), +(_anR.gps_lon||0)];
      if (!anMapMarker) {
        anMapMarker = L.circleMarker(_anLL, {
          radius:5, color:'#ffcc00', fillColor:'#ffcc00', fillOpacity:1
        }).addTo(anMap);
      } else {
        anMapMarker.setLatLng(_anLL);
      }
    }
  }
  ```

- [ ] **Step 3: Test map toggle**

  Load a flight with GPS data. Click ANALYSE → click 🗺 CARTE button. A Leaflet map should appear on the right with the GPS track drawn. Play the flight — the yellow dot should move along the track. Click ✕ to close.

- [ ] **Step 4: Commit**

  ```bash
  git add web/viewer.html
  git commit -m "feat(analyse): toggleAnMap() with lazy Leaflet init and render() marker sync"
  ```

---

### Task 9: Fix graph map resize handle

**Files:**
- Modify: `web/viewer.html` (JS, `setupMapResize()`, around line 10723)

The current `setupMapResize()` uses `document.addEventListener` for move/up. On WebKit, if another handler consumed the event or didn't clean up properly, the resize can stop working. The fix: add `e.stopPropagation()` to mousedown and use `window` instead of `document` for move/up.

- [ ] **Step 1: Rewrite `setupMapResize()`**

  Replace the existing `setupMapResize()` function (lines 10723–10746) with:

  ```js
  function setupMapResize() {
    var handle  = document.getElementById('graph-map-resize');
    var sidebar = document.getElementById('graph-map-sidebar');
    if (!handle || !sidebar) return;
    var resizing = false, startX = 0, startW = 0;
    handle.addEventListener('mousedown', function(e) {
      e.stopPropagation();
      e.preventDefault();
      resizing = true;
      startX = e.clientX;
      startW = sidebar.offsetWidth;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    });
    window.addEventListener('mousemove', function(e) {
      if (!resizing) return;
      var newW = Math.max(160, Math.min(600, startW - (e.clientX - startX)));
      sidebar.style.width = newW + 'px';
      if (gMapLeaflet) gMapLeaflet.invalidateSize();
    });
    window.addEventListener('mouseup', function() {
      if (!resizing) return;
      resizing = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    });
  }
  ```

- [ ] **Step 2: Test the resize handle**

  Go to the GRAPHS tab. Click the 🗺 MAP button to show the map sidebar. Hover the left edge of the sidebar — cursor should change to `col-resize`. Drag left/right to resize the sidebar.

- [ ] **Step 3: Commit**

  ```bash
  git add web/viewer.html
  git commit -m "fix(graphs): setupMapResize uses window events + stopPropagation for WebKit"
  ```

---

## Self-Review

### Spec coverage

| Spec requirement | Covered by |
|-----------------|-----------|
| Sidebar 175px, 6 items, active border | Task 4 CSS + Task 5 HTML |
| Badges with colors and thresholds | Task 7 |
| `showAnalysis(key)` routing | Task 6 |
| ÉNERGIE: `rebuildEnergyPanel()` | Task 6 (showAnalysis) |
| PID: `rebuildPIDCharts()` + `runPIDAdvisor()` | Task 6 |
| PID range selector timeline | Task 5 HTML + Task 6 JS |
| VIBRATIONS: `rebuildVibPanel()` | Task 6 |
| EKF: `buildEKFChart()` | Task 6 |
| TRAJ: `rebuildGPS3D()` | Task 6 |
| MOTEUR: `rebuildMotorPerfPanel()` | Task 6 |
| Optional map toggle 🗺 | Task 8 |
| Reuse existing Leaflet (lazy init) | Task 8 |
| `map.invalidateSize()` on show | Task 8 |
| Remove A/B HTML/CSS/JS | Tasks 1–3 |
| `computeAnalysisBadges()` in `initFlight()` + `applyViewFilterCore()` | Task 7 |
| Fix graph map resize handle | Task 9 |

### Type consistency

- `pidRangeStart`, `pidRangeEnd` declared before `rebuildPIDCharts()` modification — present in Task 6 Step 1.
- `showAnalysis` exported via `window.showAnalysis` — Step 1 of Task 6.
- `toggleAnMap`, `pidResetRange` exported via `window.*` — Tasks 6 and 8.
- `anCurrentKey` initialized to `'energy'` — used in both `boot()` (Task 3 Step 3) and tab-switch handler (Task 3 Step 4).
- All badge IDs match: `an-badge-{energy,pid,fft,ekf,traj,motor}` in HTML (Task 5) and `setBadge(key, ...)` in JS (Task 7).

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-01-analyse-tab-redesign.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks

**2. Inline Execution** — execute tasks in this session using executing-plans

**Which approach?**
