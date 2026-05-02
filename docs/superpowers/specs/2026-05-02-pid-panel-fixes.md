# Spec — Correctifs panel PID (onglet ANALYSE)

Date : 2026-05-02

## Contexte

L'onglet ANALYSE a été refait (branche `feature/analyse-redesign`). Le panel PID présente trois problèmes :

1. **Graphe flou** — canvas non adapté au devicePixelRatio Retina
2. **Filtre incohérent** — `computeAnalysisBadges()` utilise `armed` seul pour le RMSE PID ; les graphes utilisent déjà `armed && thro_des > 0.05`
3. **Ressenti "déconnecté"** — `showAnalysis('pid')` appelle `rebuildPIDCharts()` synchronement après `display:flex`, avant que WebKit ait calculé le layout → dimensions = 0 → chart mal cadré, curseur décalé

## Ce qui fonctionne déjà

- `getPIDRows()` filtre `viewStart/viewEnd` et `armed && thro_des > 0.05` — aucun changement nécessaire
- `applyViewFilterCore()` appelle `setTimeout(rebuildPIDCharts, 130)` — la connexion au filtre de vue fonctionne
- `render()` appelle `updatePIDCursors()` à chaque frame — la connexion au curseur fonctionne si `pidChart` existe

## Changements requis

Tous dans `web/viewer.html`, branche `feature/analyse-redesign`.

---

### Fix 1 — DPR dans `rebuildPIDCharts()`

**Problème :** `canvas.width = W; canvas.height = H` force les dimensions en pixels CSS sans DPR. Chart.js (mode `responsive:false`) lit la taille CSS puis multiplie par `devicePixelRatio` pour les pixels physiques — mais seulement si on ne force pas `canvas.width` à la main avant la création.

**Fix :**
```js
const dpr = window.devicePixelRatio || 1;
const W = container.offsetWidth  || 700;
const H = container.offsetHeight > 40 ? container.offsetHeight : 320;
canvas.style.width  = W + 'px';
canvas.style.height = H + 'px';
// NE PAS set canvas.width / canvas.height manuellement
```

Et dans la config Chart.js :
```js
options: {
  animation: false,
  responsive: false,
  devicePixelRatio: window.devicePixelRatio || 1,
  maintainAspectRatio: false,
  // ... reste inchangé
}
```

Chart.js règle alors `canvas.width = W * dpr` et `canvas.height = H * dpr` en interne.

---

### Fix 2 — DPR dans `buildPIDSelector()`

Canvas 2D pur (pas Chart.js) — pattern standard :

```js
const dpr = window.devicePixelRatio || 1;
const W = wrap.offsetWidth || 700;
const H = 44;
canvas.width  = W * dpr;
canvas.height = H * dpr;
canvas.style.width  = W + 'px';
canvas.style.height = '44px';
const ctx = canvas.getContext('2d');
ctx.scale(dpr, dpr);
// tout le dessin en coordonnées CSS (0..W, 0..H)
```

---

### Fix 3 — Timing dans `showAnalysis('pid')`

**Problème :** appel synchrone → `container.offsetWidth = 0` sous WebKit si le layout n'est pas encore calculé.

**Fix :** dans le dispatch `showAnalysis`, remplacer l'appel synchrone par :
```js
pid: function() {
  setTimeout(function() {
    if(typeof rebuildPIDCharts==='function') rebuildPIDCharts();
    if(typeof runPIDAdvisor==='function') runPIDAdvisor();
    buildPIDSelector();
  }, 50);
},
```

---

### Fix 4 — `spanGaps: false` dans `rebuildPIDCharts()`

**Problème :** `spanGaps: true` (valeur par défaut Chart.js) relie les segments de vol avec une ligne continue sur les pauses non-vol. Fix :

Dans chaque `datasets.push({...})` de `rebuildPIDCharts()`, ajouter `spanGaps: false`.

---

### Fix 5 — Filtre `thro_des > 0.05` dans `computeAnalysisBadges()`

**Problème :** la section PID de `computeAnalysisBadges()` filtre `armed` seulement.

**Fix :** utiliser le même critère que `getPIDRows()` :
```js
var armed = flightData.filter(function(r) {
  return (r.armed===1||r.armed==='1') && +(r.thro_des||0) > 0.05;
});
```

---

## Ce qui ne change pas

- `getPIDRows()` — déjà correct
- `updatePIDCursors()` — déjà correct
- `render()` — déjà correct
- Les 5 autres panels ANALYSE (ÉNERGIE, VIB, EKF, TRAJ, MOTEUR)
