# Spec — Redesign onglet Télémétrie

**Date :** 2026-04-22  
**Statut :** Validé (prototype v4 approuvé)

---

## Contexte

L'onglet Télémétrie avait été remanié le 2026-04-22 avec un layout `col1=État/Stats, col2=Carte/Radio, col3=Attitude pleine hauteur`. Ce layout n'était pas satisfaisant. Ce spec décrit le nouveau layout validé par l'utilisateur.

---

## Layout global

Grille CSS : `grid-template-columns: 1.4fr 1fr 1fr` / `grid-template-rows: 1fr 1fr 0.55fr`

| Position | Panneau |
|---|---|
| Col 1, rows 1–3 (pleine hauteur) | CARTE GPS |
| Col 2, row 1 | ÉTAT DE VOL |
| Col 2, row 2 | ATTITUDE |
| Col 3, row 1 | STATS VOL |
| Col 3, row 2 | RADIO RC |
| Col 2–3, row 3 | MOTEURS & SERVOS (bande basse) |

---

## Panneaux — détail des changements

### CARTE GPS (col 1, pleine hauteur) — inchangé
Reprend le contenu existant tel quel : trajectoire Leaflet, toggles layers (HOVER/TRANS/PLANE/DÉSARMÉ/ÉVÉN.), toggles tuiles (SAT/OSM/DARK), profil altitude en bas.

### ÉTAT DE VOL (col 2, row 1) — allégé
Retire la section **ATTITUDE IMU** (Roll/Pitch/Yaw/AccZ) qui est déplacée dans la cellule ATTITUDE.  
Conserve : Mode vol, Stabilisation, Throttle, Tension batt., GPS Sats, Altitude GPS, Vitesse sol, Loop dt, PID outputs (Roll/Pitch/Yaw).

### ATTITUDE (col 2, row 2) — restructuré
Trois boutons toggle dans le header de la cellule :
- **◯ AHI** — affiche uniquement l'horizon artificiel
- **✈ 3D** — affiche uniquement le drone 3D Three.js
- **◯+✈ LES DEUX** (défaut) — AHI et drone 3D côte à côte

En dessous des toggles, affichage des valeurs IMU : Roll / Pitch / Yaw / G-force (texte, toujours visible).  
L'AHI canvas peut être légèrement plus grand (`max-width: 140px`) par rapport à l'ancienne version.

### STATS VOL (col 3, row 1) — inchangé
Reprend le contenu existant.

### RADIO RC (col 3, row 2) — restructuré

**Section barres analogiques (CH1–CH4) :**  
Grille `22px 1fr 52px` (numéro / barre / valeur µs). Couleurs : CH1 vert, CH2+CH3 bleu, CH4 ambre.

**Section switches (CH5–CH10) — 3 lignes × 2 :**

| Ligne | Switch A | Switch B |
|---|---|---|
| 1 | CH5 ARM — SF (2 pos : DISARM / ARM) | CH6 CTRL MODE — SE (3 pos : ANGLE / ACRO / CUSTOM) |
| 2 | CH7 SA — INTER G (3 pos : LOW / MID / HIGH) | CH8 MODE VOL — SB (3 pos : HOVER / TRANS / PLANE) |
| 3 | CH9 SC — TRIPLE (3 pos : LOW / MID / HIGH) | CH10 INTER D — TRIPLE (3 pos : LOW / MID / HIGH) |

Chaque switch affiche : numéro, nom, mode actif coloré (droite), barres de positions colorées, labels sous chaque position.  
Couleurs de position active : rouge = ARMED, vert = ANGLE, bleu = HOVER/mode flight, ambre = LOW par défaut.

**Section sticks (80×80 px) :**  
Deux carrés côte à côte avec point de position lumineux.
- **Stick GAUCHE** : axe X = CH4 (droite→gauche), axe Y = CH1 (bas→haut)
- **Stick DROIT** : axe X = CH2 (gauche→droite), axe Y = CH3 (bas→haut)

Les coordonnées sont calculées depuis les valeurs µs : `pct = (val_us - 1000) / 1000` clampé [0,1].

### MOTEURS & SERVOS (col 2–3, row 3) — sorti de l'overlay, affiché en permanence

Trois zones côte à côte dans la bande basse :

**Zone moteurs (gauche) :**  
2 barres verticales uniquement : M1 (DROIT) et M3 (GAUCHE). Couleur vert gradient quand actifs, gris quand idle. Valeur % sous chaque barre.

**Zone radar symétrie (centre, ~84px) :**  
Canvas radar minimaliste montrant M1 vs M3 sur un axe horizontal. Affiche le delta `ΔM`.

**Zone servos (droite) :**  
7 barres verticales bipolaires S1–S7. Zéro au centre, positif vers le haut, négatif vers le bas. Couleurs : S1–S2 ambre (microtilts), S3–S4 bleu (ailerons), S5–S7 vert (élevateur/mode/dérive). Valeur en degrés sous chaque barre.

**Overlay CONFIG :** reste accessible via le bouton ⚙ CONFIG dans la filter bar — contient la configuration embarquée (CONFIG_NAME, FW_VERSION, etc.). Les moteurs/servos n'y sont plus.

---

## Ce qui ne change pas

- Timeline sticky (play, vitesse, scrubber, phase strip)
- Filter bar (PLAGE : TOUT / VOL ARMÉ, boutons sessions)
- Toute la logique JS existante (seekTo, updateTelemetry, etc.)
- Le viewer HTML reste la source de vérité des calculs

---

## Implémentation — fichier cible

`web/viewer.html` — uniquement les sections :
1. CSS `/* ── TÉLÉMÉTRIE GRID ── */`
2. HTML `<!-- ══ TAB TÉLÉMÉTRIE ══ -->`
3. JS `toggleTelemConfig()` et les fonctions de mise à jour des cellules moteurs/servos

Pas de refactoring du reste du viewer.
