# Télémétrie Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructurer l'onglet Télémétrie de viewer.html selon le layout validé (prototype v4).

**Architecture:** Toutes les modifications sont dans `web/viewer.html` — sections CSS, HTML et JS. Aucun nouveau fichier. Aucun refactoring du reste du viewer.

**Tech Stack:** HTML/CSS/JS vanilla, viewer.html existant (~10k lignes)

---

### Task 1: CSS — Grille et nouveaux styles

**Files:**
- Modify: `web/viewer.html:87-124` (section `/* ── TÉLÉMÉTRIE GRID ── */`)

- [ ] Remplacer le CSS `#telem-grid` : colonnes `1.4fr 1fr 1fr`, lignes `1fr 1fr 0.55fr`
- [ ] Ajouter CSS : attitude toggles, bande moteurs, switches 2-par-ligne, sticks
- [ ] Commit

### Task 2: HTML — Restructurer `#telem-grid`

**Files:**
- Modify: `web/viewer.html:1240-1507` (div#telem-grid)

- [ ] Remplacer les 5 cellules existantes par 6 cellules dans le nouvel ordre
- [ ] Cellule ATTITUDE : ajouter toggles + IMU values + AHI canvas agrandi
- [ ] Cellule RADIO : analog CH1-4 + switches 3×2 + sticks
- [ ] Cellule MOTEURS bande basse (col 2-3, row 3)
- [ ] Commit

### Task 3: HTML — Overlay CONFIG (sans moteurs)

**Files:**
- Modify: `web/viewer.html:1510-1549`

- [ ] Supprimer le bloc MOTEURS & SERVOS de l'overlay
- [ ] Garder uniquement la CONFIGURATION EMBARQUÉE
- [ ] Commit

### Task 4: JS — setAttiMode + buildMotorsBande + updateMotorsBande

**Files:**
- Modify: `web/viewer.html` section JS (autour de la ligne 10493 toggleTelemConfig)

- [ ] Ajouter `function setAttiMode(mode)`
- [ ] Ajouter `function buildMotorsBande()`
- [ ] Ajouter `function updateMotorsBande(row)`
- [ ] Hooker `buildMotorsBande()` dans l'appel existant `buildMotorsGrid()`
- [ ] Hooker `updateMotorsBande(row)` dans l'appel existant `updateMotors(row)`
- [ ] Commit

### Task 5: JS — Radio switches refaits + sticks

**Files:**
- Modify: `web/viewer.html` fonctions `updateRadio`, `updateTripleSwitch`, `setTripleLabel`

- [ ] Mettre à jour `updateTripleSwitch` pour les nouveaux IDs `sw-pos-X-Y`
- [ ] Mettre à jour les labels CH5/CH6/CH8 pour `sw-mode-X`
- [ ] Ajouter `updateSticks(ch)` appelé depuis `updateRadio`
- [ ] Commit

### Task 6: Tests visuels + commit final

- [ ] Lancer `python -m pytest tests/ -v`
- [ ] Lancer l'app (`python app.py --browser`) et vérifier l'onglet Télémétrie
- [ ] Vérifier toggles AHI/3D/LES DEUX
- [ ] Vérifier bande moteurs visible
- [ ] Vérifier sticks animés en scrubbing
- [ ] Commit final + update CLAUDE.md roadmap
