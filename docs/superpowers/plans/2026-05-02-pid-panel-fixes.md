# PID Panel Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger le graphe PID de l'onglet ANALYSE : flou Retina, timing de création, `spanGaps`, et filtre "en vol" dans les badges.

**Architecture:** Quatre patches ciblés dans `web/viewer.html` sur la branche `feature/analyse-redesign`. Tout est dans le même fichier. Les fonctions `getPIDRows()`, `updatePIDCursors()` et `render()` sont déjà correctes — ne pas y toucher.

**Tech Stack:** Chart.js (existant), Canvas 2D API, JS ES6 (const/let déjà utilisés dans les fonctions ciblées)

---

## File Map

- Modify: `web/viewer.html` — 4 zones ciblées :
  - `rebuildPIDCharts()` lignes ~4782–4852 (canvas setup + options Chart.js + spanGaps)
  - `showAnalysis()` dispatch pid lignes ~11023–11027
  - `buildPIDSelector()` lignes ~11055–11060
  - `computeAnalysisBadges()` section PID lignes ~11200–11203

---

### Task 1 : DPR + spanGaps dans `rebuildPIDCharts()`

**Files:**
- Modify: `web/viewer.html:4782–4852`

Ce task corrige deux choses dans la même fonction :
1. Le canvas est dimensionné sans tenir compte du `devicePixelRatio` → flou sur Retina
2. `spanGaps:true` relie visuellement les segments de vol séparés par des pauses non-armées

- [ ] **Step 1 : Remplacer le setup canvas (lignes 4788–4790)**

  Trouver le bloc :
  ```js
  const W = container.offsetWidth  || 700;
  const H = container.offsetHeight > 40 ? container.offsetHeight : 320;
  canvas.width  = W;
  canvas.height = H;
  ```

  Remplacer par :
  ```js
  const W = container.offsetWidth  || 700;
  const H = container.offsetHeight > 40 ? container.offsetHeight : 320;
  canvas.style.width  = W + 'px';
  canvas.style.height = H + 'px';
  ```
  (Supprimer les deux lignes `canvas.width = W` et `canvas.height = H`. Chart.js lira `canvas.style.width/height` et appliquera lui-même le DPR via l'option ajoutée ci-dessous.)

- [ ] **Step 2 : Ajouter `devicePixelRatio` dans la config Chart.js (ligne ~4850)**

  Trouver :
  ```js
  options:{
    animation:false, responsive:false, maintainAspectRatio:false,
  ```

  Remplacer par :
  ```js
  options:{
    animation:false, responsive:false, maintainAspectRatio:false,
    devicePixelRatio: window.devicePixelRatio || 1,
  ```

- [ ] **Step 3 : Passer `spanGaps:false` sur les 4 datasets**

  Dans les 4 `datasets.push({...})`, changer chaque `spanGaps:true` en `spanGaps:false`.

  Les 4 occurrences sont dans les datasets `Consigne`, `Mesure IMU`, `Erreur`, `PID out` (chercher `spanGaps:true` dans la fonction).

  Résultat attendu : les coupures entre segments de vol apparaissent comme des interruptions de ligne plutôt qu'une ligne continue.

- [ ] **Step 4 : Vérifier visuellement**

  Ouvrir une session de vol. Onglet ANALYSE → PID. Le graphe doit être net (pas de flou). Sur un vol avec des phases non-armées, les courbes doivent présenter des discontinuités.

- [ ] **Step 5 : Commit**

  ```bash
  git add web/viewer.html
  git commit -m "fix(analyse): rebuildPIDCharts — DPR Retina + spanGaps false"
  ```

---

### Task 2 : DPR dans `buildPIDSelector()`

**Files:**
- Modify: `web/viewer.html` — fonction `buildPIDSelector()`, lignes ~11055–11062

Canvas 2D pur (pas Chart.js) — il faut multiplier les dimensions physiques par `dpr` et scaler le contexte.

- [ ] **Step 1 : Remplacer le setup canvas du sélecteur**

  Trouver dans `buildPIDSelector()` :
  ```js
  var W = wrap.offsetWidth || 700;
  var H = 44;
  canvas.width = W; canvas.height = H;
  var ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, W, H);
  ```

  Remplacer par :
  ```js
  var dpr = window.devicePixelRatio || 1;
  var W = wrap.offsetWidth || 700;
  var H = 44;
  canvas.width  = W * dpr;
  canvas.height = H * dpr;
  canvas.style.width  = W + 'px';
  canvas.style.height = H + 'px';
  var ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);
  ```

  Tout le code de dessin qui suit utilise des coordonnées CSS (0..W, 0..H) — aucune autre ligne à changer grâce au `ctx.scale`.

- [ ] **Step 2 : Vérifier visuellement**

  Onglet ANALYSE → PID. Le mini-sélecteur en bas du graphe doit être net sur Retina.

- [ ] **Step 3 : Commit**

  ```bash
  git add web/viewer.html
  git commit -m "fix(analyse): buildPIDSelector — DPR Retina pour canvas sélecteur"
  ```

---

### Task 3 : Timing `showAnalysis('pid')` — setTimeout 50ms

**Files:**
- Modify: `web/viewer.html` — fonction `showAnalysis()`, dispatch `pid`, lignes ~11023–11027

WebKit n'a pas encore appliqué `display:flex` quand `rebuildPIDCharts()` est appelée synchronement → `container.offsetWidth = 0` → Chart.js crée le chart à 700×320 par défaut au lieu des vraies dimensions.

- [ ] **Step 1 : Wrapper le dispatch `pid` dans un setTimeout**

  Trouver dans le dispatch de `showAnalysis` :
  ```js
  pid:    function() {
            if(typeof rebuildPIDCharts==='function') rebuildPIDCharts();
            if(typeof runPIDAdvisor==='function') runPIDAdvisor();
            buildPIDSelector();
          },
  ```

  Remplacer par :
  ```js
  pid:    function() {
            setTimeout(function() {
              if(typeof rebuildPIDCharts==='function') rebuildPIDCharts();
              if(typeof runPIDAdvisor==='function') runPIDAdvisor();
              buildPIDSelector();
            }, 50);
          },
  ```

- [ ] **Step 2 : Vérifier**

  Onglet ANALYSE → PID. Le graphe doit remplir toute la zone centrale (pas de graphe minuscule dans un coin).

- [ ] **Step 3 : Commit**

  ```bash
  git add web/viewer.html
  git commit -m "fix(analyse): showAnalysis pid — setTimeout 50ms pour layout WebKit"
  ```

---

### Task 4 : Filtre `thro_des > 0.05` dans `computeAnalysisBadges()`

**Files:**
- Modify: `web/viewer.html` — fonction `computeAnalysisBadges()`, section PID, lignes ~11200–11203

Le calcul RMSE pour le badge PID filtre `armed` seulement. Il doit filtrer `armed && thro_des > 0.05` (même critère que `getPIDRows()`).

- [ ] **Step 1 : Mettre à jour le filtre de la section PID**

  Trouver dans `computeAnalysisBadges()` la section `// PID — RMSE` :
  ```js
  var armed = flightData.filter(function(r) { return r.armed===1||r.armed==='1'; });
  if (!armed.length) return;
  var sum2 = armed.reduce(function(s, r) {
  ```

  Remplacer `var armed = ...` par :
  ```js
  var armed = flightData.filter(function(r) {
    return (r.armed===1||r.armed==='1') && +(r.thro_des||0) > 0.05;
  });
  ```
  (les deux lignes suivantes `if (!armed.length) return;` et `var sum2 = armed.reduce(...)` restent inchangées)

- [ ] **Step 2 : Vérifier**

  Ouvrir un vol. Badge PID dans la sidebar ANALYSE : si le vol a peu de phases de vol réel, le badge doit refléter le RMSE sur ces phases uniquement (et non le bruit de sol).

- [ ] **Step 3 : Commit**

  ```bash
  git add web/viewer.html
  git commit -m "fix(analyse): badge PID — filtre armed+thro_des>0.05 comme getPIDRows"
  ```

---

## Self-Review

### Spec coverage

| Exigence spec | Task |
|---|---|
| DPR rebuildPIDCharts — style.width/height + devicePixelRatio option | Task 1 |
| spanGaps: false sur les 4 datasets | Task 1 |
| DPR buildPIDSelector — canvas physique + ctx.scale | Task 2 |
| setTimeout 50ms dans showAnalysis pid | Task 3 |
| Filtre thro_des > 0.05 dans computeAnalysisBadges PID | Task 4 |

### Cohérence

- `W` et `H` sont des constantes CSS (coordonnées logiques) dans les deux fonctions — le code de dessin en aval n'a pas besoin de changer.
- Chart.js reçoit `canvas.style.width/height` (CSS px) + `devicePixelRatio` → il gère `canvas.width/height` physiques en interne. Ne pas remettre `canvas.width = W` manuellement après.
- Le `ctx.scale(dpr, dpr)` dans `buildPIDSelector` s'applique à TOUT le dessin qui suit dans la fonction — ne pas appeler `ctx.scale` à nouveau.
