# Spec — Refonte onglet ANALYSE

Date : 2026-05-01

## Contexte

L'onglet ANALYSE actuel repose sur un système de deux slots A/B avec clonage de panels HTML (`injectAnalysisPanel`). Ce mécanisme est cassé (graphes non rendus, sélecteurs invisibles) et confus pour l'utilisateur. Le système A/B est supprimé entièrement.

Les fonctions JS de rendu (`rebuildPIDCharts`, `rebuildGPS3D`, `rebuildEnergyPanel`, `rebuildVibPanel`, `updateMotorRadar`) sont fonctionnelles — elles sont utilisées dans l'onglet TÉLÉMÉTRIE. Seule la structure HTML/CSS du pane-analyse est refaite.

---

## Layout

```
┌─────────────┬──────────────────────────────────────┬────────────┐
│  SIDEBAR    │  WIDGET ACTIF (plein espace)          │  CARTE     │
│  ~175px     │                                       │  ~220px    │
│             │  ┌─ header widget ─────────────────┐  │  (toggle)  │
│  ⚡ ÉNERGIE │  │ titre · sélecteurs · 🗺 CARTE   │  │            │
│  📐 PID  ⚠ │  └─────────────────────────────────┘  │  Leaflet   │
│  〰 VIB HIGH│  ┌─ contenu ───────────────────────┐  │  synchro   │
│  🧭 EKF     │  │                                 │  │  avec      │
│  🌐 TRAJ    │  │  graphe / canvas principal      │  │  curseur   │
│  🔧 MOTEUR  │  │                                 │  │  timeline  │
│             │  ├─ timeline sélecteur (si besoin)─┤  │            │
└─────────────┴──┴─────────────────────────────────┴──┴────────────┘
```

### Sidebar gauche (`#an-sidebar`)
- Largeur fixe 175px
- 6 items cliquables, un seul actif à la fois (bordure gauche cyan)
- Chaque item : icône + label + badge d'état optionnel
- Badges calculés une fois après chargement du vol (`computeAnalysisBadges()`)

### Zone centrale (`#an-content`)
- `flex: 1`, prend tout l'espace restant
- Contient 6 panels `div.an-panel[data-key]`, un seul `display:flex` à la fois
- Chaque panel : header fixe + zone scrollable + (optionnel) timeline sélecteur en bas

### Carte optionnelle (`#an-map-panel`)
- Largeur 220px, masquée par défaut
- Bouton 🗺 CARTE dans le header de chaque widget toggle `#an-map-panel`
- Réutilise la carte Leaflet existante (`map`) — pas une nouvelle instance
- Synchronisée avec le curseur timeline via `render()` existant

---

## Badges d'état

Calculés par `computeAnalysisBadges()` appelée dans `initFlight()` et `applyViewFilterCore()`.

| Analyse | Badge vert | Badge orange | Badge rouge |
|---------|-----------|--------------|-------------|
| ÉNERGIE | OK (Vbat > 3.7V/cell) | ⚠ LOW (< 3.7V) | ✗ CRIT (< 3.5V) |
| PID | OK | ⚠ + axe (RMSE > seuil ou oscillation détectée) | — |
| VIBRATIONS | OK | ⚠ HIGH (amplitude dom. > 0.3G) | — |
| EKF | OK (GPS acquis) | ⚠ NO GPS | — |
| TRAJECTOIRE | nb points GPS | — | NO GPS |
| MOTEUR | OK | ⚠ IMBAL (|M1-M3| moyen > 15%) | — |

Les seuils sont des constantes modifiables en tête de script.

---

## Widgets

### ⚡ ÉNERGIE (défaut)
Réutilise `rebuildEnergyPanel()` tel quel. Le div `#an-src-energy` est déplacé directement dans `#an-panel-energy` sans clonage.

### 📐 PID
Structure :
- Header : sélecteur axe (ROLL/PITCH/YAW) · fenêtre temporelle (TOUT/±5s/±10s/±30s) · toggle couches
- Colonne gauche (flex:1) : canvas `#pid-canvas-main` + timeline sélecteur (mini overview drag-to-select, même pattern que VIBRATIONS)
- Colonne droite (200px) : métriques calculées + conseiller PID
- Réutilise `rebuildPIDCharts()`, `runPIDAdvisor()`, `updatePIDWindow()`

Le timeline sélecteur PID (`#pid-range-selector`) est un canvas permettant de sélectionner une plage temporelle, identique à `#vib-selector-wrap`. Il remplace les boutons ±5s/±10s/±30s comme méthode principale de zoom — les boutons restent comme raccourcis.

### 〰 VIBRATIONS
Réutilise `rebuildVibPanel()`. Le div `#an-src-fft` déplacé dans `#an-panel-fft`. Aucun changement de contenu.

### 🧭 EKF
Réutilise le code EKF existant. `#an-src-ekf` → `#an-panel-ekf`.

### 🌐 TRAJECTOIRE
Réutilise `rebuildGPS3D()`, `initGPS3D()`. `#an-src-traj` → `#an-panel-traj`.

### 🔧 MOTEUR
Réutilise `updateMotorRadar()`. `#an-src-motor` → `#an-panel-motor`.

---

## Navigation (`showAnalysis(key)`)

```js
function showAnalysis(key) {
  // Met à jour la sidebar (item actif)
  // Affiche le bon panel, masque les autres
  // Appelle la fonction rebuild correspondante
  // Met à jour le bouton 🗺 CARTE selon l'état actuel
}
```

Mapping clé → rebuild :

| key | rebuild |
|-----|---------|
| energy | rebuildEnergyPanel() |
| pid | rebuildPIDCharts(); runPIDAdvisor() |
| fft | rebuildVibPanel() |
| ekf | (rebuild EKF chart) |
| traj | rebuildGPS3D() |
| motor | updateMotorRadar() |

---

## Carte partagée

La carte Leaflet `map` est déjà initialisée dans l'onglet TÉLÉMÉTRIE. Quand `#an-map-panel` est visible, `map.invalidateSize()` est appelé pour forcer le recalcul. La synchronisation du marker est assurée par `render()` qui met déjà à jour `map`.

---

## Suppression (code à retirer)

- HTML : `#analyse-selector` (chips A/B), `#an-sources` (panels cachés), `#an-panel-a`, `#an-panel-b`, `#an-empty`
- JS : `selectAnalysis()`, `renderAnalysisPanels()`, `injectAnalysisPanel()`, `AN_DEFS`, `anSlotA`, `anSlotB`
- CSS : `.an-chip`, `.an-sel-a`, `.an-sel-b`, `.an-slot-lbl`, `.an-slot-sep`

---

## Bug connexe — carte graphes non redimensionnable

Dans l'onglet GRAPHES, la carte sidebar a un resize handle (`#map-resize-handle`) dont le handler mousedown/mousemove est probablement cassé après le refactoring WebKit DnD (commit 692ba02). À corriger en même temps.

---

## Ce qui ne change pas

- Toutes les fonctions de calcul/rendu (`rebuildPIDCharts`, `rebuildGPS3D`, etc.)
- Les IDs des éléments internes à chaque widget (canvas, badges, selects)
- Le CSS des panels individuels
- L'intégration avec `render()` et `seekTo()` / `seekInPlace()`
