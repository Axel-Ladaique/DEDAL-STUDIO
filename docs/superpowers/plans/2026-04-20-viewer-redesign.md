# Viewer Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructurer `web/viewer.html` en 3 onglets (Télémétrie / Graphes / Analyse) avec un nouvel explorateur de graphes multi-panels MATLAB-style (sidebar drag & drop, grille configurable, curseur partagé, zoom/pan).

**Architecture:** Tout le contenu JS/HTML de calcul existant est conservé intact. On ajoute une nav d'onglets, on enveloppe les sections existantes dans des tab-panes, et on remplace le `<!-- CHART EXPLORER -->` par le nouveau système multi-panels. L'integration layer DEDAL (lignes 9417+) n'est pas touchée.

**Tech Stack:** HTML/CSS/JS vanilla, Chart.js 4.4 (déjà chargé), Leaflet 1.9 (déjà chargé), Three.js r128 (déjà chargé), Google Fonts (Orbitron + Share Tech Mono + DM Mono)

---

## Fichiers touchés

| Fichier | Opération | Lignes clés |
|---------|-----------|-------------|
| `web/viewer.html` | Modify | L7 (fonts), L14-29 (CSS vars), L859-893 (header), L893-894 (main tag), L1059-1402 (panels → onglets), L1333-1402 (chart explorer → nouveau) |

Aucun nouveau fichier créé — tout reste dans `viewer.html` pour rester self-contained (PyWebView).

---

## Task 1 — Design system : fonts + CSS variables

**Files:**
- Modify: `web/viewer.html:7` (balise fonts)
- Modify: `web/viewer.html:14-29` (`:root`)

- [ ] **Étape 1 : Remplacer la balise Google Fonts (ligne 7)**

```html
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Share+Tech+Mono&family=DM+Mono:wght@300;400;500&display=swap" rel="stylesheet">
```

- [ ] **Étape 2 : Remplacer le bloc `:root` (lignes 14-29)**

```css
:root {
  --bg:        #050810;
  --surface:   #080d1a;
  --surface2:  #0c1220;
  --border:    rgba(255,255,255,0.06);
  --border2:   rgba(255,255,255,0.12);
  --accent:    #00ff9d;
  --accent2:   #ffb340;
  --accent3:   #00d4ff;
  --warn:      #ffb340;
  --red:       #ff453a;
  --text:      #c8d8f0;
  --dim:       #3a4a60;
  --dim2:      #5a6a80;
  --font-hud:  'Orbitron', monospace;
  --font-mono: 'Share Tech Mono', monospace;
  --font-ui:   'DM Mono', monospace;
  --glow-g:    0 0 8px rgba(0,255,157,0.4);
  --glow-a:    0 0 8px rgba(255,179,64,0.4);
  --r:         6px;
  /* legacy compat */
  --hover:     #00cc7a;
  --trans:     rgba(0,255,157,0.08);
}
```

- [ ] **Étape 3 : Ajouter CSS tab bar + tab panes après le bloc `body::before`**

Chercher `/* ---- HEADER ---- */` et insérer avant :

```css
/* ── TAB BAR ── */
#tab-bar {
  display: flex; align-items: flex-end; gap: 2px;
  padding: 0 16px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  position: sticky; top: 0; z-index: 99;
}
.vtab {
  padding: 8px 16px 7px;
  font-family: var(--font-hud); font-size: 9px; letter-spacing: 2px; font-weight: 600;
  color: var(--dim); cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color .2s, border-color .2s;
  user-select: none; white-space: nowrap;
}
.vtab:hover { color: var(--dim2); }
.vtab.active { color: var(--accent); border-color: var(--accent); }
.vtab.disabled { opacity: 0.25; pointer-events: none; font-style: italic; }

/* ── TAB PANES ── */
.tab-pane { display: none; }
.tab-pane.active { display: block; }
#pane-graphs.active { display: flex; flex-direction: column; height: calc(100vh - 84px); overflow: hidden; }
#pane-analyse.active { display: flex; flex-direction: column; height: calc(100vh - 84px); overflow: hidden; }
```

- [ ] **Étape 4 : Vérifier visuellement**

```bash
source .venv/bin/activate && python app.py --browser
```

Ouvrir une session avec un log. Le header doit afficher Orbitron, les couleurs doivent être vertes phosphore. Fermer l'app.

- [ ] **Étape 5 : Commit**

```bash
git add web/viewer.html
git commit -m "feat(viewer): design system — Orbitron + vert phosphore + tab CSS"
```

---

## Task 2 — Structure HTML : tab bar + tab panes

**Files:**
- Modify: `web/viewer.html:859-894` (header → ajouter tab bar)
- Modify: `web/viewer.html:893-` (main → wrapper tabs)

- [ ] **Étape 1 : Mettre à jour le contenu du `<header>` (lignes 862-880)**

Remplacer le bloc `<div class="logo">...</div>` par :

```html
<div class="logo">
  <div class="logo-icon" style="border-color:var(--accent);box-shadow:var(--glow-g);">✈</div>
  <div>
    <h1 style="font-family:var(--font-hud);color:var(--accent);letter-spacing:4px;">DEDAL</h1>
    <span style="font-size:9px;font-family:var(--font-hud);letter-spacing:2px;color:var(--dim2);">STUDIO · VIEWER</span>
  </div>
</div>
```

- [ ] **Étape 2 : Insérer la tab bar après `</header>` (après ligne 881)**

```html
<nav id="tab-bar">
  <div class="vtab active" data-tab="telem">◈ TÉLÉMÉTRIE</div>
  <div class="vtab" data-tab="graphs">◫ GRAPHES</div>
  <div class="vtab" data-tab="analyse">◎ ANALYSE</div>
  <div class="vtab disabled">⚙ HUD</div>
  <div class="vtab disabled">⇄ COMPARAISON</div>
</nav>
```

- [ ] **Étape 3 : Envelopper le contenu de `<div id="main">` en 3 tab-panes**

Remplacer `<div id="main">` (ligne 894) par :

```html
<div id="main">

<!-- ══ TAB TÉLÉMÉTRIE ══ -->
<div class="tab-pane active" id="pane-telem">
  <!-- VIEW FILTER BAR -->
  <!-- STICKY TIMELINE -->
  <!-- MAP -->
  <!-- STATUS -->
  <!-- BOTTOM GRID (attitude 2D, 3D, radio, motors) -->
  <!-- CONFIG DE VOL -->
  <!-- FLIGHT STATS -->
  <!-- RADIO TX16S -->
  <!-- MOTORS + SERVOS -->
  <!-- ENERGY -->
```

Fermer `</div><!-- /pane-telem -->` juste avant `<!-- CHART EXPLORER -->` (ligne 1333).

```html
</div><!-- /pane-telem -->

<!-- ══ TAB GRAPHES ══ -->
<div class="tab-pane" id="pane-graphs">
  <!-- nouveau explorer — Task 4 -->
</div><!-- /pane-graphs -->

<!-- ══ TAB ANALYSE ══ -->
<div class="tab-pane" id="pane-analyse">
  <!-- PID ANALYSE -->
  <!-- 3D GPS TRAJECTORY -->
  <!-- EKF VELOCITY ESTIMATION -->
  <!-- VIBRATION ANALYSIS -->
</div><!-- /pane-analyse -->
```

Déplacer les sections `<!-- CHART EXPLORER -->`, `<!-- PID ANALYSE -->`, `<!-- 3D GPS TRAJECTORY -->`, `<!-- EKF VELOCITY ESTIMATION -->`, `<!-- VIBRATION ANALYSIS -->` dans leurs panes respectifs (couper-coller dans l'HTML).

- [ ] **Étape 4 : Ajouter le JS de tab switching**

Juste avant la balise `</script>` de fermeture du IIFE (ligne ~9414), ajouter :

```js
// ── TAB SWITCHING ──
(function() {
  document.querySelectorAll('.vtab[data-tab]').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('.vtab').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      document.getElementById('pane-' + t.dataset.tab).classList.add('active');
    });
  });
})();
```

- [ ] **Étape 5 : Vérifier**

Lancer l'app, charger un log. Cliquer sur TÉLÉMÉTRIE → contenu visible. Cliquer GRAPHES → pane vide. Cliquer ANALYSE → PID/FFT/EKF/Traj visibles.

- [ ] **Étape 6 : Commit**

```bash
git add web/viewer.html
git commit -m "feat(viewer): tab bar — 3 onglets TÉLÉMÉTRIE / GRAPHES / ANALYSE"
```

---

## Task 3 — Onglet Télémétrie : layout 3×2

**Files:**
- Modify: `web/viewer.html` (intérieur de `#pane-telem`)

- [ ] **Étape 1 : Ajouter CSS grille télémétrie**

Dans le bloc `<style>`, ajouter :

```css
/* ── TÉLÉMÉTRIE GRID ── */
#telem-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 6px; padding: 8px;
  height: calc(100vh - 84px);
  overflow: hidden;
}
.telem-cell {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r);
  display: flex; flex-direction: column;
  overflow: hidden; min-height: 0;
}
.telem-cell-label {
  padding: 5px 10px;
  font-family: var(--font-hud); font-size: 8px; letter-spacing: 2px;
  color: var(--dim2); border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.telem-cell-body { flex: 1; overflow: hidden; position: relative; }
```

- [ ] **Étape 2 : Remplacer le contenu du `#pane-telem` par la grille**

Conserver le VIEW FILTER BAR et STICKY TIMELINE en dehors de la grille (ils restent sticky en haut du pane). Envelopper les 6 blocs de contenu dans `#telem-grid` :

```html
<div id="view-filter-bar">...</div>
<div id="sticky-timeline">...</div>

<div id="telem-grid">
  <!-- Col 1 rows 1-2 : Carte GPS -->
  <div class="telem-cell" style="grid-row:1/3;" id="telem-map-cell">
    <div class="telem-cell-label"><span style="color:var(--accent3);">◈</span> CARTE GPS</div>
    <div class="telem-cell-body">
      <!-- contenu du panel MAP existant transféré ici -->
    </div>
  </div>

  <!-- Col 2 row 1 : État de vol -->
  <div class="telem-cell" id="telem-status-cell">
    <div class="telem-cell-label"><span style="color:var(--accent);">◈</span> ÉTAT DE VOL</div>
    <div class="telem-cell-body">
      <!-- STATUS panel existant -->
    </div>
  </div>

  <!-- Col 2 row 2 : Attitude (AHI + 3D) -->
  <div class="telem-cell" id="telem-attitude-cell">
    <div class="telem-cell-label"><span style="color:var(--accent);">◈</span> ATTITUDE</div>
    <div class="telem-cell-body" style="display:flex;">
      <!-- AHI canvas + 3D canvas côte à côte -->
    </div>
  </div>

  <!-- Col 3 row 1 : FLIGHT STATS -->
  <div class="telem-cell" id="telem-stats-cell">
    <div class="telem-cell-label"><span style="color:var(--accent2);">◈</span> STATS VOL</div>
    <div class="telem-cell-body" id="flight-stats-body">...</div>
  </div>

  <!-- Col 3 row 2 : Radio RC -->
  <div class="telem-cell" id="telem-radio-cell">
    <div class="telem-cell-label"><span style="color:var(--accent2);">◈</span> RADIO RC</div>
    <div class="telem-cell-body">
      <!-- RADIO panel existant -->
    </div>
  </div>
</div>
```

- [ ] **Étape 3 : Vérifier**

La grille doit remplir l'écran. La carte doit s'initialiser dans `telem-map-cell`. Vérifier que `initMap()` référence correctement `#map` (vérifier que l'id du div Leaflet est toujours `map`).

```bash
grep -n 'id="map"' web/viewer.html
```

Si `initMap()` référence `document.getElementById('map')`, le div doit garder l'id `map`.

- [ ] **Étape 4 : Commit**

```bash
git add web/viewer.html
git commit -m "feat(viewer): télémétrie — grille 3×2 (carte, état, attitude, stats, radio)"
```

---

## Task 4 — Onglet Graphes : nouveau multi-panel explorer

**Files:**
- Modify: `web/viewer.html` (intérieur de `#pane-graphs`)

C'est la tâche la plus importante. On remplace l'ancien `<!-- CHART EXPLORER -->` par un système de panels indépendants.

- [ ] **Étape 1 : Ajouter CSS du nouvel explorer**

```css
/* ── NEW GRAPH EXPLORER ── */
#graphs-pane-inner { display:flex; height:100%; }

/* Sidebar signaux */
#sig-sidebar {
  width:130px; flex-shrink:0;
  background:var(--surface); border-right:1px solid var(--border);
  display:flex; flex-direction:column; overflow:hidden;
  transition:width .25s ease;
}
#sig-sidebar.collapsed { width:32px; }
.sig-sidebar-head {
  display:flex; align-items:center; justify-content:space-between;
  padding:7px 10px; border-bottom:1px solid var(--border);
  cursor:pointer; flex-shrink:0;
}
.sig-sidebar-title {
  font-family:var(--font-hud); font-size:8px; letter-spacing:2px; color:var(--accent);
  overflow:hidden; white-space:nowrap;
}
#sig-sidebar.collapsed .sig-sidebar-title { opacity:0; }
.sig-sidebar-toggle { color:var(--dim2); font-size:10px; flex-shrink:0; transition:transform .25s; }
#sig-sidebar.collapsed .sig-sidebar-toggle { transform:rotate(180deg); }

.sig-list { flex:1; overflow-y:auto; padding:5px; display:flex; flex-direction:column; gap:2px; }
.sig-list::-webkit-scrollbar { width:3px; }
.sig-list::-webkit-scrollbar-thumb { background:var(--dim); border-radius:2px; }
.sig-group-lbl {
  font-family:var(--font-hud); font-size:7px; letter-spacing:2px; color:var(--dim);
  padding:5px 3px 2px;
}
.sig-item {
  display:flex; align-items:center; gap:6px;
  padding:4px 6px; border-radius:4px; cursor:grab;
  font-family:var(--font-mono); font-size:10px;
  border:1px solid transparent;
  transition:background .15s, border-color .15s;
  user-select:none; white-space:nowrap; overflow:hidden;
}
.sig-item:hover { background:var(--surface2); border-color:var(--border2); }
.sig-dot { width:6px; height:6px; border-radius:50%; flex-shrink:0; }

/* Graphs main area */
#graphs-main { flex:1; display:flex; flex-direction:column; overflow:hidden; }

/* Toolbar */
#graphs-toolbar {
  display:flex; align-items:center; gap:4px; flex-shrink:0;
  padding:5px 10px; background:var(--surface); border-bottom:1px solid var(--border);
}
.g-tlabel { font-family:var(--font-hud); font-size:7px; letter-spacing:2px; color:var(--dim); margin-right:2px; }
.g-tbtn {
  padding:3px 8px; border-radius:4px;
  font-family:var(--font-hud); font-size:7px; letter-spacing:1px;
  background:var(--surface2); color:var(--dim2); border:1px solid var(--border);
  cursor:pointer; transition:all .15s; white-space:nowrap;
}
.g-tbtn:hover { border-color:var(--border2); color:var(--text); }
.g-tbtn.g-active { background:rgba(0,255,157,0.1); border-color:rgba(0,255,157,0.3); color:var(--accent); }
.g-tbtn.g-map-on { background:rgba(0,212,255,0.1); border-color:rgba(0,212,255,0.3); color:var(--accent3); }
.g-tsep { width:1px; height:16px; background:var(--border); margin:0 3px; }
.g-tadd {
  margin-left:auto; padding:3px 10px; border-radius:4px;
  font-family:var(--font-mono); font-size:11px;
  background:rgba(0,255,157,0.08); color:var(--accent);
  border:1px solid rgba(0,255,157,0.2); cursor:pointer;
}

/* Panels grid */
#panels-grid {
  flex:1; display:grid; gap:5px; padding:6px; overflow:hidden;
}

/* Individual panel */
.g-panel {
  background:var(--surface); border:1px solid var(--border); border-radius:var(--r);
  display:flex; flex-direction:column; overflow:hidden; position:relative;
  transition:border-color .2s;
}
.g-panel:hover { border-color:var(--border2); }
.g-panel-header {
  display:flex; align-items:center; gap:4px;
  padding:3px 7px; border-bottom:1px solid var(--border); flex-shrink:0;
}
.g-curve-tags { display:flex; align-items:center; gap:3px; flex:1; flex-wrap:wrap; overflow:hidden; }
.g-ctag {
  display:flex; align-items:center; gap:3px;
  background:var(--surface2); border:1px solid var(--border2);
  border-radius:10px; padding:2px 7px 2px 5px; font-family:var(--font-mono); font-size:9px;
}
.g-ctag-x { color:var(--dim); cursor:pointer; margin-left:1px; font-size:8px; }
.g-ctag-x:hover { color:var(--red); }
.g-drop-hint {
  font-family:var(--font-mono); font-size:8px; color:var(--dim);
  border:1px dashed var(--border2); border-radius:8px; padding:1px 7px; cursor:default;
}
.g-panel-btns { display:flex; gap:2px; flex-shrink:0; }
.g-pbtn {
  width:18px; height:18px; border-radius:3px; background:none; border:none;
  cursor:pointer; color:var(--dim); font-size:9px;
  display:flex; align-items:center; justify-content:center; transition:all .15s;
}
.g-pbtn:hover { background:var(--surface2); color:var(--text); }
.g-pbtn.close:hover { color:var(--red); }

/* Panel canvas area */
.g-canvas-wrap { flex:1; position:relative; overflow:hidden; }
.g-shared-cursor {
  position:absolute; top:0; bottom:0; width:1px;
  background:var(--accent2); opacity:0.75;
  box-shadow:0 0 5px var(--accent2);
  pointer-events:none; z-index:4;
  display:none;
}
.g-cursor-tip {
  position:absolute; top:3px;
  background:var(--bg); border:1px solid var(--accent2);
  border-radius:3px; padding:2px 5px;
  font-family:var(--font-mono); font-size:8px; color:var(--accent2);
  white-space:nowrap; pointer-events:none; z-index:5;
}

/* Panel add zone */
.g-add-zone {
  background:var(--surface); border:1px dashed var(--border); border-radius:var(--r);
  display:flex; align-items:center; justify-content:center; flex-direction:column;
  gap:4px; cursor:pointer; color:var(--dim); font-size:10px; font-family:var(--font-mono);
  transition:border-color .2s, color .2s;
}
.g-add-zone:hover { border-color:var(--accent); color:var(--accent); }

/* Map panel body */
.g-map-body { width:100%; height:100%; position:relative; }
```

- [ ] **Étape 2 : Ajouter HTML du nouvel explorer dans `#pane-graphs`**

```html
<div class="tab-pane" id="pane-graphs">
  <div id="graphs-pane-inner">

    <!-- Sidebar signaux -->
    <div id="sig-sidebar">
      <div class="sig-sidebar-head" onclick="sigSidebarToggle()">
        <span class="sig-sidebar-title">SIGNAUX</span>
        <span class="sig-sidebar-toggle">◀</span>
      </div>
      <div class="sig-list" id="sig-list">
        <!-- Peuplé par buildSignalSidebar() -->
      </div>
    </div>

    <!-- Zone principale -->
    <div id="graphs-main">
      <!-- Toolbar -->
      <div id="graphs-toolbar">
        <span class="g-tlabel">LAYOUT</span>
        <button class="g-tbtn g-active" id="btn-layout-2x1" onclick="setGraphLayout('2x1')">2×1</button>
        <button class="g-tbtn" onclick="setGraphLayout('1x1')">1×1</button>
        <button class="g-tbtn" onclick="setGraphLayout('2x2')">2×2</button>
        <button class="g-tbtn" onclick="setGraphLayout('3x2')">3×2</button>
        <div class="g-tsep"></div>
        <button class="g-tbtn g-map-on" id="btn-map-toggle" onclick="toggleMapPanel()">🗺 CARTE</button>
        <div class="g-tsep"></div>
        <button class="g-tbtn" id="btn-zoom" onclick="setGraphTool('zoom')">🔍 ZOOM</button>
        <button class="g-tbtn" id="btn-pan" onclick="setGraphTool('pan')">✋ PAN</button>
        <button class="g-tbtn" onclick="resetGraphZoom()">↺ RESET</button>
        <button class="g-tadd" onclick="addGraphPanel()">＋ PANEL</button>
      </div>
      <!-- Panels grid -->
      <div id="panels-grid" style="grid-template-columns:1fr;grid-template-rows:1fr 1fr;">
        <!-- Peuplé par initGraphExplorer() -->
      </div>
    </div>

  </div>
</div>
```

- [ ] **Étape 3 : Ajouter le JS du nouvel explorer**

Juste avant la fin du IIFE (avant `function boot()`), ajouter le bloc suivant :

```js
// ================================================================
//  NEW GRAPH EXPLORER
// ================================================================

// ── Définition des groupes de signaux ──
const SIG_GROUPS = [
  { label: 'ATTITUDE', sigs: [
    { key:'roll_IMU',   color:'#00ff9d' },
    { key:'pitch_IMU',  color:'#00d4ff' },
    { key:'yaw_IMU',    color:'#bf5af2' },
    { key:'roll_des',   color:'#ffb340' },
    { key:'pitch_des',  color:'#ff6b35' },
    { key:'yaw_des',    color:'#ff453a' },
  ]},
  { label: 'PID', sigs: [
    { key:'roll_PID',   color:'#00ff9d' },
    { key:'pitch_PID',  color:'#00d4ff' },
    { key:'yaw_PID',    color:'#bf5af2' },
  ]},
  { label: 'MOTEURS', sigs: [
    { key:'m1_PWM',     color:'#ff453a' },
    { key:'m3_PWM',     color:'#ff6b35' },
    { key:'m2_PWM',     color:'#ffb340' },
    { key:'m4_PWM',     color:'#ffd700' },
  ]},
  { label: 'SERVOS', sigs: [
    { key:'s1_PWM',     color:'#00d4ff' },
    { key:'s2_PWM',     color:'#bf5af2' },
    { key:'s3_PWM',     color:'#00ff9d' },
    { key:'s4_PWM',     color:'#ffb340' },
    { key:'s5_PWM',     color:'#ff6b35' },
  ]},
  { label: 'IMU', sigs: [
    { key:'AccX',       color:'#ff453a' },
    { key:'AccY',       color:'#00ff9d' },
    { key:'AccZ',       color:'#00d4ff' },
    { key:'GyroX',      color:'#ff453a' },
    { key:'GyroY',      color:'#00ff9d' },
    { key:'GyroZ',      color:'#00d4ff' },
  ]},
  { label: 'GPS / BAT', sigs: [
    { key:'gps_alt_m',  color:'#00d4ff' },
    { key:'gps_speed_ms',color:'#00ff9d'},
    { key:'vbat_V',     color:'#ffb340' },
    { key:'home_dist_m',color:'#ff453a' },
  ]},
  { label: 'RC', sigs: [
    { key:'ch1',        color:'#00ff9d' },
    { key:'ch2',        color:'#00d4ff' },
    { key:'ch3',        color:'#ffb340' },
    { key:'ch4',        color:'#bf5af2' },
    { key:'thro_des',   color:'#ff453a' },
  ]},
];

let gPanels = [];           // liste des objets panel actifs
let gCharts = {};           // Chart.js instances { panelId: Chart }
let gTool   = 'pan';        // 'zoom' | 'pan'
let gMapPanelVisible = true;
let gDragSig = null;        // signal en cours de drag { key, color }
let gZoomRange = null;      // { minIdx, maxIdx } ou null = tout

// ── Panel counter ──
let gPanelCounter = 0;
function newPanelId() { return 'gp-' + (++gPanelCounter); }

// ── Build sidebar ──
function buildSignalSidebar() {
  const list = document.getElementById('sig-list');
  if (!list) return;
  list.innerHTML = '';
  SIG_GROUPS.forEach(group => {
    const lbl = document.createElement('div');
    lbl.className = 'sig-group-lbl';
    lbl.textContent = group.label;
    list.appendChild(lbl);
    group.sigs.forEach(sig => {
      // Only show signals that exist in loaded data
      if (flightData.length && !(sig.key in flightData[0])) return;
      const el = document.createElement('div');
      el.className = 'sig-item';
      el.draggable = true;
      el.dataset.key = sig.key;
      el.dataset.color = sig.color;
      el.innerHTML = `<div class="sig-dot" style="background:${sig.color}"></div>${sig.key}`;
      el.addEventListener('dragstart', e => {
        gDragSig = { key: sig.key, color: sig.color };
        e.dataTransfer.effectAllowed = 'copy';
      });
      el.addEventListener('dragend', () => { gDragSig = null; });
      list.appendChild(el);
    });
  });
}

function sigSidebarToggle() {
  document.getElementById('sig-sidebar').classList.toggle('collapsed');
}

// ── Panel DOM builder ──
function buildPanelDOM(pid) {
  const panel = document.createElement('div');
  panel.className = 'g-panel';
  panel.id = pid;
  panel.innerHTML = `
    <div class="g-panel-header">
      <div class="g-curve-tags" id="${pid}-tags">
        <div class="g-drop-hint">↕ drop signal</div>
      </div>
      <div class="g-panel-btns">
        <button class="g-pbtn" title="Dupliquer" onclick="duplicateGraphPanel('${pid}')">⊕</button>
        <button class="g-pbtn close" title="Fermer" onclick="removeGraphPanel('${pid}')">✕</button>
      </div>
    </div>
    <div class="g-canvas-wrap" id="${pid}-wrap">
      <canvas id="${pid}-canvas"></canvas>
      <div class="g-shared-cursor" id="${pid}-cursor"></div>
      <div class="g-cursor-tip" id="${pid}-tip" style="display:none;"></div>
    </div>
  `;
  // Drop zone
  const wrap = panel.querySelector('.g-canvas-wrap');
  wrap.addEventListener('dragover', e => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; });
  wrap.addEventListener('drop', e => {
    e.preventDefault();
    if (gDragSig) addCurveToPanel(pid, gDragSig.key, gDragSig.color);
  });
  return panel;
}

// ── Add/remove panels ──
function addGraphPanel(curves) {
  const pid = newPanelId();
  gPanels.push({ id: pid, curves: curves || [] });
  const grid = document.getElementById('panels-grid');
  const panel = buildPanelDOM(pid);
  grid.appendChild(panel);
  // Initialize Chart.js
  initPanelChart(pid);
  if (curves) curves.forEach(c => addCurveToPanel(pid, c.key, c.color, false));
  refreshPanelGridLayout();
  return pid;
}

function removeGraphPanel(pid) {
  if (gCharts[pid]) { gCharts[pid].destroy(); delete gCharts[pid]; }
  gPanels = gPanels.filter(p => p.id !== pid);
  const el = document.getElementById(pid);
  if (el) el.remove();
  refreshPanelGridLayout();
}

function duplicateGraphPanel(pid) {
  const src = gPanels.find(p => p.id === pid);
  if (!src) return;
  addGraphPanel([...src.curves]);
}

// ── Chart.js init per panel ──
function initPanelChart(pid) {
  const canvas = document.getElementById(pid + '-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const chart = new Chart(ctx, {
    type: 'line',
    data: { datasets: [] },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: {
          type: 'linear',
          ticks: { color: '#3a4a60', font: { family: "'Share Tech Mono'", size: 9 },
            callback: v => v.toFixed(1) + 's' },
          grid: { color: 'rgba(255,255,255,0.04)' },
        },
        y: {
          ticks: { color: '#3a4a60', font: { family: "'Share Tech Mono'", size: 9 } },
          grid: { color: 'rgba(255,255,255,0.04)' },
        },
      },
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
    },
  });
  gCharts[pid] = chart;
}

// ── Add curve to a panel ──
function addCurveToPanel(pid, key, color, redraw) {
  if (redraw === undefined) redraw = true;
  const panel = gPanels.find(p => p.id === pid);
  if (!panel || panel.curves.find(c => c.key === key)) return;
  panel.curves.push({ key, color });

  // Update header tags
  const tagsEl = document.getElementById(pid + '-tags');
  if (tagsEl) {
    const hint = tagsEl.querySelector('.g-drop-hint');
    const tag = document.createElement('div');
    tag.className = 'g-ctag';
    tag.dataset.key = key;
    tag.innerHTML = `<div class="sig-dot" style="background:${color}"></div>${key}<span class="g-ctag-x" onclick="removeCurveFromPanel('${pid}','${key}')">×</span>`;
    tagsEl.insertBefore(tag, hint);
  }
  if (redraw) refreshPanelChart(pid);
}

function removeCurveFromPanel(pid, key) {
  const panel = gPanels.find(p => p.id === pid);
  if (!panel) return;
  panel.curves = panel.curves.filter(c => c.key !== key);
  const tagsEl = document.getElementById(pid + '-tags');
  if (tagsEl) {
    const tag = tagsEl.querySelector(`[data-key="${key}"]`);
    if (tag) tag.remove();
  }
  refreshPanelChart(pid);
}

// ── Redraw one panel chart from flightData ──
function refreshPanelChart(pid) {
  const chart = gCharts[pid];
  const panel = gPanels.find(p => p.id === pid);
  if (!chart || !panel || !flightData.length) return;

  const t0 = flightData[0].timestamp_us;
  const decimate = 5;
  const start = gZoomRange ? gZoomRange.minIdx : viewStart;
  const end   = gZoomRange ? gZoomRange.maxIdx : viewEnd;

  chart.data.datasets = panel.curves.map(c => {
    const pts = [];
    for (let i = start; i <= end; i += decimate) {
      const r = flightData[i];
      const t = (r.timestamp_us - t0) / 1e6;
      const v = parseFloat(r[c.key]);
      if (!isNaN(v)) pts.push({ x: t, y: v });
    }
    return {
      data: pts,
      borderColor: c.color,
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0,
    };
  });
  chart.update('none');
}

function refreshAllPanelCharts() {
  gPanels.forEach(p => refreshPanelChart(p.id));
}

// ── Layout ──
function setGraphLayout(mode) {
  const grid = document.getElementById('panels-grid');
  document.querySelectorAll('#graphs-toolbar .g-tbtn').forEach(b => {
    if (['1×1','2×1','2×2','3×2'].some(x => b.textContent.trim() === x)) b.classList.remove('g-active');
  });
  const btn = document.getElementById('btn-layout-' + mode.replace('x', 'x'));
  if (btn) btn.classList.add('g-active');
  if (mode === '1x1') { grid.style.gridTemplateColumns = '1fr'; grid.style.gridTemplateRows = '1fr'; }
  if (mode === '2x1') { grid.style.gridTemplateColumns = '1fr'; grid.style.gridTemplateRows = '1fr 1fr'; }
  if (mode === '2x2') { grid.style.gridTemplateColumns = '1fr 1fr'; grid.style.gridTemplateRows = '1fr 1fr'; }
  if (mode === '3x2') { grid.style.gridTemplateColumns = '1fr 1fr 1fr'; grid.style.gridTemplateRows = '1fr 1fr'; }
}

function refreshPanelGridLayout() {
  // After add/remove, maintain current layout
  const btn = document.querySelector('#graphs-toolbar .g-tbtn.g-active');
  const current = btn ? btn.textContent.trim().replace('×','x').toLowerCase() : '2x1';
  setGraphLayout(current);
}

// ── Map panel ──
let gMapLeaflet = null;

function toggleMapPanel() {
  gMapPanelVisible = !gMapPanelVisible;
  const btn = document.getElementById('btn-map-toggle');
  btn.classList.toggle('g-map-on', gMapPanelVisible);
  const existing = document.getElementById('gp-map');
  if (gMapPanelVisible && !existing) {
    addMapPanel();
  } else if (!gMapPanelVisible && existing) {
    existing.remove();
    gPanels = gPanels.filter(p => p.id !== 'gp-map');
  }
}

function addMapPanel() {
  const panel = document.createElement('div');
  panel.className = 'g-panel';
  panel.id = 'gp-map';
  panel.innerHTML = `
    <div class="g-panel-header">
      <div class="g-curve-tags">
        <span style="font-family:var(--font-hud);font-size:8px;letter-spacing:1px;color:var(--accent3);">🗺 CARTE GPS</span>
        <span style="font-size:8px;color:var(--dim2);margin-left:6px;">position synchronisée avec curseur</span>
      </div>
      <div class="g-panel-btns">
        <button class="g-pbtn close" onclick="toggleMapPanel()">✕</button>
      </div>
    </div>
    <div class="g-canvas-wrap">
      <div id="g-map-div" style="width:100%;height:100%;"></div>
      <div class="g-shared-cursor" id="gp-map-cursor"></div>
    </div>
  `;
  document.getElementById('panels-grid').appendChild(panel);
  gPanels.push({ id: 'gp-map', curves: [], isMap: true });

  // Init leaflet dans le nouveau div
  if (!gMapLeaflet) {
    gMapLeaflet = L.map('g-map-div', { zoomControl: true, attributionControl: false });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(gMapLeaflet);
    // Draw track if data available
    if (flightData.length) buildGraphMapTrack();
  }
}

function buildGraphMapTrack() {
  if (!gMapLeaflet || !flightData.length) return;
  const pts = flightData
    .filter(r => r.gps_valid == 1 && r.gps_lat && r.gps_lon)
    .map(r => [parseFloat(r.gps_lat), parseFloat(r.gps_lon)]);
  if (pts.length < 2) return;
  L.polyline(pts, { color: '#00ff9d', weight: 1.5, opacity: 0.7 }).addTo(gMapLeaflet);
  gMapLeaflet.fitBounds(L.latLngBounds(pts));
}

// ── Shared cursor ──
function showGraphCursor(pct, tSec) {
  gPanels.forEach(p => {
    const cursor = document.getElementById(p.id + '-cursor');
    const tip    = document.getElementById(p.id + '-tip');
    if (cursor) { cursor.style.display = 'block'; cursor.style.left = pct + '%'; }
    if (tip) {
      tip.style.display = 'block';
      tip.style.left = `calc(${pct}% + 4px)`;
      tip.textContent = 't = ' + tSec.toFixed(2) + ' s';
    }
  });
}

function hideGraphCursor() {
  gPanels.forEach(p => {
    const cursor = document.getElementById(p.id + '-cursor');
    const tip    = document.getElementById(p.id + '-tip');
    if (cursor) cursor.style.display = 'none';
    if (tip) tip.style.display = 'none';
  });
}

// ── Tool (zoom/pan) ──
function setGraphTool(tool) {
  gTool = tool;
  document.getElementById('btn-zoom').classList.toggle('g-active', tool === 'zoom');
  document.getElementById('btn-pan').classList.toggle('g-active', tool === 'pan');
}

function resetGraphZoom() {
  gZoomRange = null;
  refreshAllPanelCharts();
}

// ── Cursor sync on mouse move over grid ──
function setupGraphCursorSync() {
  const grid = document.getElementById('panels-grid');
  if (!grid) return;
  grid.addEventListener('mousemove', e => {
    const rect = grid.getBoundingClientRect();
    const pct = ((e.clientX - rect.left) / rect.width * 100);
    const t0  = flightData.length ? flightData[0].timestamp_us : 0;
    const tMax= flightData.length ? (flightData[flightData.length-1].timestamp_us - t0) / 1e6 : 87;
    const tSec = pct / 100 * tMax;
    showGraphCursor(pct, tSec);
    // Seek current index
    if (flightData.length) {
      const targetUs = t0 + tSec * 1e6;
      let idx = viewStart;
      while (idx < viewEnd && flightData[idx].timestamp_us < targetUs) idx++;
      seekTo(idx);
    }
  });
  grid.addEventListener('mouseleave', hideGraphCursor);
}

// ── Init ──
function initGraphExplorer() {
  buildSignalSidebar();
  // Créer 2 panels par défaut
  const pid1 = addGraphPanel();
  addCurveToPanel(pid1, 'roll_IMU', '#00ff9d');
  addCurveToPanel(pid1, 'roll_des', '#ffb340');
  const pid2 = addGraphPanel();
  addCurveToPanel(pid2, 'm1_PWM', '#ff453a');
  addCurveToPanel(pid2, 'm3_PWM', '#ff6b35');
  setGraphLayout('2x1');
  setupGraphCursorSync();
  // Map panel par défaut
  addMapPanel();
}
```

- [ ] **Étape 4 : Appeler `initGraphExplorer()` depuis `initFlight()`**

Chercher `function initFlight(data)` (ligne ~2128). À la fin de cette fonction, avant le `}` fermant, ajouter :

```js
// Refresh new explorer if visible
if (document.getElementById('pane-graphs').classList.contains('active')) {
  refreshAllPanelCharts();
  buildSignalSidebar();
} else {
  // Will refresh on tab open
  document.querySelector('[data-tab="graphs"]').addEventListener('click', () => {
    refreshAllPanelCharts();
    buildSignalSidebar();
  }, { once: true });
}
```

Et dans `boot()` (ligne 9401), ajouter :

```js
function boot() {
  setupAllPanels();
  setupResizeObserver();
  initGraphExplorer(); // NEW
}
```

- [ ] **Étape 5 : Vérifier**

Lancer l'app, charger un log, cliquer GRAPHES. Vérifier :
- [ ] Sidebar visible avec les signaux groupés
- [ ] 2 panels créés avec courbes par défaut
- [ ] Panel carte visible
- [ ] Déplacer la souris sur les panels → curseur ambre synchronisé

```bash
python -m pytest tests/ -v
```

Expected: tous les tests passent (backend non impacté).

- [ ] **Étape 6 : Commit**

```bash
git add web/viewer.html
git commit -m "feat(viewer): graphes — multi-panel explorer, sidebar drag&drop, curseur partagé"
```

---

## Task 5 — Graphes : zoom/pan MATLAB-style

**Files:**
- Modify: `web/viewer.html` (JS dans le IIFE)

- [ ] **Étape 1 : Ajouter zoom par scroll molette**

Dans la fonction `setupGraphCursorSync()`, après le `mouseleave` listener, ajouter :

```js
// Zoom par scroll molette
grid.addEventListener('wheel', e => {
  e.preventDefault();
  if (!flightData.length) return;
  const total = viewEnd - viewStart;
  if (total < 2) return;
  const factor = e.deltaY > 0 ? 1.2 : 0.833;  // zoom in/out
  const rect = grid.getBoundingClientRect();
  const pct  = (e.clientX - rect.left) / rect.width;
  const center = viewStart + Math.round(pct * total);
  const half   = Math.round((total * factor) / 2);
  const newStart = Math.max(0, center - half);
  const newEnd   = Math.min(flightData.length - 1, center + half);
  if (newEnd - newStart < 10) return;
  gZoomRange = { minIdx: newStart, maxIdx: newEnd };
  refreshAllPanelCharts();
}, { passive: false });
```

- [ ] **Étape 2 : Ajouter pan par drag**

```js
let gDragPan = null;

grid.addEventListener('mousedown', e => {
  if (gTool !== 'pan') return;
  gDragPan = { x: e.clientX, startMin: gZoomRange?.minIdx ?? viewStart, startMax: gZoomRange?.maxIdx ?? viewEnd };
  grid.style.cursor = 'grabbing';
});
grid.addEventListener('mouseup', () => { gDragPan = null; grid.style.cursor = ''; });
grid.addEventListener('mousemove', e => {
  if (!gDragPan || !flightData.length) return;
  const rect  = grid.getBoundingClientRect();
  const dx    = e.clientX - gDragPan.x;
  const total = gDragPan.startMax - gDragPan.startMin;
  const shift = -Math.round((dx / rect.width) * total);
  let newMin  = gDragPan.startMin + shift;
  let newMax  = gDragPan.startMax + shift;
  if (newMin < 0) { newMax -= newMin; newMin = 0; }
  if (newMax >= flightData.length) { newMin -= (newMax - flightData.length + 1); newMax = flightData.length - 1; }
  gZoomRange = { minIdx: newMin, maxIdx: newMax };
  refreshAllPanelCharts();
});
```

- [ ] **Étape 3 : Vérifier**

Charger un log, aller sur GRAPHES. Scroll molette → les courbes zooment horizontalement centrées sur la souris. Drag → pan. Bouton ↺ RESET → revient à la vue complète.

- [ ] **Étape 4 : Commit**

```bash
git add web/viewer.html
git commit -m "feat(viewer): graphes — zoom scroll molette + pan drag MATLAB-style"
```

---

## Task 6 — Onglet Analyse : chip selector

**Files:**
- Modify: `web/viewer.html` (HTML `#pane-analyse`, CSS)

- [ ] **Étape 1 : Ajouter CSS onglet analyse**

```css
/* ── ANALYSE TAB ── */
#analyse-selector {
  display:flex; align-items:center; gap:6px; flex-wrap:wrap;
  padding:6px 12px; background:var(--surface); border-bottom:1px solid var(--border);
  flex-shrink:0;
}
.an-slot-lbl { font-family:var(--font-hud); font-size:7px; letter-spacing:2px; }
.an-slot-a { color:var(--accent); }
.an-slot-b { color:var(--accent3); }
.an-chip {
  padding:3px 10px; border-radius:12px;
  font-family:var(--font-hud); font-size:7px; letter-spacing:1px;
  cursor:pointer; border:1px solid var(--border);
  background:var(--surface2); color:var(--dim2);
  transition:all .15s; white-space:nowrap;
}
.an-chip:hover { border-color:var(--border2); color:var(--text); }
.an-chip.an-sel-a { background:rgba(0,255,157,0.1); border-color:rgba(0,255,157,0.3); color:var(--accent); }
.an-chip.an-sel-b { background:rgba(0,212,255,0.1); border-color:rgba(0,212,255,0.3); color:var(--accent3); }
.an-slot-sep { width:1px; height:18px; background:var(--border); margin:0 4px; }
#analyse-panels { flex:1; display:flex; gap:6px; padding:8px; overflow:hidden; }
.an-panel-wrap {
  flex:1; background:var(--surface); border:1px solid var(--border); border-radius:var(--r);
  display:flex; flex-direction:column; overflow:hidden; min-width:0;
}
.an-panel-header {
  padding:5px 10px; border-bottom:1px solid var(--border);
  display:flex; align-items:center; gap:8px; flex-shrink:0;
}
.an-panel-title { font-family:var(--font-hud); font-size:9px; letter-spacing:2px; }
.an-panel-title.a { color:var(--accent); }
.an-panel-title.b { color:var(--accent3); }
.an-panel-body { flex:1; overflow:auto; }
.an-empty {
  flex:1; display:flex; align-items:center; justify-content:center; flex-direction:column;
  gap:8px; color:var(--dim); border:1px dashed var(--border); border-radius:var(--r);
  font-family:var(--font-mono); font-size:11px;
}
```

- [ ] **Étape 2 : Restructurer l'HTML de `#pane-analyse`**

Les sections existantes (PID, FFT, EKF, Trajectoire) ont des `id` définis. On les réutilise comme corps des panels. Remplacer le contenu de `#pane-analyse` par :

```html
<div class="tab-pane" id="pane-analyse">
  <!-- Sélecteur chips -->
  <div id="analyse-selector">
    <span class="an-slot-lbl an-slot-a">A</span>
    <div id="an-chips-a">
      <span class="an-chip an-sel-a" data-slot="a" data-val="pid"  onclick="selectAnalysis('a','pid')">📐 PID</span>
      <span class="an-chip"          data-slot="a" data-val="fft"  onclick="selectAnalysis('a','fft')">〰 VIBRATIONS</span>
      <span class="an-chip"          data-slot="a" data-val="ekf"  onclick="selectAnalysis('a','ekf')">🧭 EKF</span>
      <span class="an-chip"          data-slot="a" data-val="traj" onclick="selectAnalysis('a','traj')">🌐 TRAJECTOIRE</span>
    </div>
    <div class="an-slot-sep"></div>
    <span class="an-slot-lbl an-slot-b">B</span>
    <div id="an-chips-b">
      <span class="an-chip"          data-slot="b" data-val="pid"  onclick="selectAnalysis('b','pid')">📐 PID</span>
      <span class="an-chip an-sel-b" data-slot="b" data-val="fft"  onclick="selectAnalysis('b','fft')">〰 VIBRATIONS</span>
      <span class="an-chip"          data-slot="b" data-val="ekf"  onclick="selectAnalysis('b','ekf')">🧭 EKF</span>
      <span class="an-chip"          data-slot="b" data-val="traj" onclick="selectAnalysis('b','traj')">🌐 TRAJECTOIRE</span>
    </div>
  </div>
  <!-- Panels -->
  <div id="analyse-panels">
    <div id="an-empty" class="an-empty">
      <div style="font-size:24px;opacity:0.3">🔬</div>
      Sélectionne une analyse ci-dessus
    </div>
    <!-- Panel A -->
    <div class="an-panel-wrap" id="an-panel-a" style="display:none;">
      <div class="an-panel-header">
        <span class="an-panel-title a" id="an-title-a">—</span>
        <span style="font-size:9px;color:var(--dim2);margin-left:auto;" id="an-meta-a"></span>
      </div>
      <div class="an-panel-body" id="an-body-a">
        <!-- contenu injecté par selectAnalysis() -->
      </div>
    </div>
    <!-- Panel B -->
    <div class="an-panel-wrap" id="an-panel-b" style="display:none;">
      <div class="an-panel-header">
        <span class="an-panel-title b" id="an-title-b">—</span>
        <span style="font-size:9px;color:var(--dim2);margin-left:auto;" id="an-meta-b"></span>
      </div>
      <div class="an-panel-body" id="an-body-b">
        <!-- contenu injecté par selectAnalysis() -->
      </div>
    </div>
  </div>
</div>
```

- [ ] **Étape 3 : Ajouter le JS chip selector**

```js
// ── ANALYSE TAB CHIP SELECTOR ──
const AN_DEFS = {
  pid:  { title: '📐 ANALYSE PID',        meta: 'roll · pitch · yaw',    srcId: 'pid-analyse-panel' },
  fft:  { title: '〰 VIBRATIONS FFT',     meta: 'AccX · AccY · AccZ',    srcId: 'vib-analyse-panel' },
  ekf:  { title: '🧭 ANALYSE EKF',        meta: 'vélocité estimée',       srcId: 'ekf-panel' },
  traj: { title: '🌐 TRAJECTOIRE 3D',     meta: 'GPS lat/lon/alt',        srcId: 'gps3d-panel' },
};

let anSlotA = 'pid', anSlotB = 'fft';

function selectAnalysis(slot, val) {
  if (slot === 'a') anSlotA = val;
  else              anSlotB = val;

  // Update chip classes
  ['a','b'].forEach(s => {
    const cur = s === 'a' ? anSlotA : anSlotB;
    document.querySelectorAll(`#an-chips-${s} .an-chip`).forEach(c => {
      c.classList.remove('an-sel-a', 'an-sel-b');
      if (c.dataset.val === cur) c.classList.add('an-sel-' + s);
    });
  });

  renderAnalysisPanels();
}

function renderAnalysisPanels() {
  const hasA = !!anSlotA;
  const hasB = !!anSlotB;
  const empty = document.getElementById('an-empty');
  const panA  = document.getElementById('an-panel-a');
  const panB  = document.getElementById('an-panel-b');

  empty.style.display = (!hasA && !hasB) ? 'flex' : 'none';
  panA.style.display  = hasA ? 'flex' : 'none';
  panB.style.display  = hasB ? 'flex' : 'none';

  if (hasA) injectAnalysisPanel('a', anSlotA);
  if (hasB) injectAnalysisPanel('b', anSlotB);
}

function injectAnalysisPanel(slot, val) {
  const def = AN_DEFS[val];
  if (!def) return;
  document.getElementById('an-title-' + slot).textContent = def.title;
  document.getElementById('an-meta-'  + slot).textContent = def.meta;
  const body = document.getElementById('an-body-' + slot);
  const src  = document.getElementById(def.srcId);
  if (body && src) {
    // Déplacer le nœud dans le panel (cloneNode pour ne pas casser l'autre slot)
    body.innerHTML = '';
    body.appendChild(src.cloneNode(true));
  }
}
```

**Note :** Les `srcId` (`pid-analyse-panel`, `vib-analyse-panel`, `ekf-panel`, `gps3d-panel`) doivent correspondre aux vrais IDs des sections existantes. Vérifier avec :

```bash
grep -n 'id="pid-analyse\|id="vib-analyse\|id="ekf-panel\|id="gps3d' web/viewer.html
```

Ajuster les `srcId` dans `AN_DEFS` en conséquence.

- [ ] **Étape 4 : Vérifier**

Aller sur ANALYSE. Cliquer un chip A → panel A affiche le contenu. Cliquer un chip B → côte à côte. Cliquer à nouveau le même chip B → panel B vide.

- [ ] **Étape 5 : Commit**

```bash
git add web/viewer.html
git commit -m "feat(viewer): analyse — chip selector A/B + panels côte à côte"
```

---

## Task 7 — Vérification finale + tests

**Files:**
- Read: `web/viewer.html`
- Run: `tests/`

- [ ] **Étape 1 : Tests backend**

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: tous passent.

- [ ] **Étape 2 : Checklist visuelle — charger un log réel**

```bash
python app.py --browser
```

Charger `INPUT_4_CLAUDE/LOG_017.csv` :

- [ ] **TÉLÉMÉTRIE** : carte centrée sur le vol, AHI animé, radio sticks corrects, stats de vol affichées
- [ ] **GRAPHES** : 2 panels + carte par défaut, drag d'un signal depuis sidebar → ajout courbe, scroll zoom, drag pan, curseur sync
- [ ] **ANALYSE** : chip PID → panel PID pleine largeur, chip FFT → côte à côte

- [ ] **Étape 3 : Vérifier l'integration layer DEDAL**

Vérifier que le bouton ← Sessions et le bouton ⚙ HUD sont toujours présents dans le header (ils sont injectés par l'integration layer, lignes 9417+).

- [ ] **Étape 4 : Commit final**

```bash
git add web/viewer.html
git commit -m "feat(viewer): redesign complet — télémétrie/graphes/analyse + MATLAB-style"
```

---

## Self-Review

**Spec coverage :**
- ✅ 3 onglets (Télémétrie / Graphes / Analyse)
- ✅ Sidebar masquable + groupes de signaux
- ✅ Grille 1×1/2×1/2×2/3×2
- ✅ Drag & drop signal → panel
- ✅ Curseur partagé synchronisé
- ✅ Zoom scroll molette + pan drag
- ✅ Bouton ↺ reset zoom
- ✅ Carte comme panel optionnel dans GRAPHES
- ✅ Panel add (＋) / close (✕) / duplicate (⊕)
- ✅ Retrait courbe individuelle (× sur tag)
- ✅ Onglet Télémétrie avec grille 3×2
- ✅ Chip selector A/B dans Analyse
- ✅ 1 panel = pleine largeur, 2 = côte à côte
- ✅ Design system Orbitron + vert phosphore
- ⚠️ Radio sticks SVG animés (présents dans l'existant, à vérifier que l'affichage tient dans la cellule télémétrie)
- ⚠️ Les `srcId` dans `AN_DEFS` doivent être vérifiés contre les vrais IDs HTML (Step 3, Task 6 — grep fourni)

**Aucun placeholder ni TBD dans ce plan.**
