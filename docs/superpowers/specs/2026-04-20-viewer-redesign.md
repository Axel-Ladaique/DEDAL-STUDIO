# Viewer Redesign — Spec

Date: 2026-04-20  
Statut: validé par brainstorming

---

## Contexte

Le viewer HTML actuel (`web/viewer.html`) est monolithique (~10 000 lignes). L'utilisateur signale : trop de scroll pour trouver l'information, graphes trop rigides, pas de multi-panel. Ce redesign concerne l'**interface** du viewer — pas les calculs (le HTML reste source de vérité pour `flight_pack.json`).

---

## Direction artistique

**HUD militaire** — identique à ce qui existe déjà dans le viewer actuel :
- Background : `#050810` (quasi-noir bleu)
- Accent primaire : `#00ff9d` (vert phosphore) avec glow CSS
- Accent curseur : `#ffb340` (ambre)
- Info : `#00d4ff` (cyan)
- Police headers : **Orbitron** (Google Fonts)
- Police données/valeurs : **Share Tech Mono**
- Police UI générale : **DM Mono**
- Grille de fond CSS subtile, corner accents SVG sur les panels

---

## Structure globale — 3 onglets

```
┌─────────────────────────────────────────┐
│  DEDAL STUDIO  │  DEDAL-YYYYMMDD-NNN   │
├────────────────────────────────────────┤
│  ◈ TÉLÉMÉTRIE │ ◫ GRAPHES │ ◎ ANALYSE │ ⚙ HUD* │ ⇄ COMPARAISON* │
└────────────────────────────────────────┘
  * futurs onglets, désactivés pour l'instant
```

---

## Onglet 1 — TÉLÉMÉTRIE

Grille fixe 3×2, pas de scroll. Affichage "retour vol en direct" rejoué depuis le log via le curseur.

### Panels (6)

| Position | Contenu |
|----------|---------|
| Col 1, rows 1-2 | **Carte GPS** — OpenStreetMap, track animé, home marker, position drone synchronisée avec curseur |
| Col 2, row 1 | **État de vol** — grille 2×3 : alt GPS, mode (badge coloré HOVER/TRANS/PLANE), vitesse, vbat, sats GPS, dist home |
| Col 2, row 2 | **Attitude** — horizon artificiel SVG (sky/ground, pitch lines, crosshair orange) + vue fil-de-fer drone VTOL birotor côte à côte |
| Col 3, row 1 | **Radio RC** — 2 joysticks SVG (THR/YAW · ROLL/PITCH), position des sticks depuis CH1-CH4, badges switches CH5-CH10 (ARM/MODE/STAB/KILL/AUX) colorés selon état |
| — | (réservé pour extensions futures) |

### Comportement
- Tous les panels se mettent à jour en fonction de la position du curseur temporel global
- La carte montre la position GPS au curseur (point orange sur le track)

---

## Onglet 2 — GRAPHES

### Layout général

```
┌──────────┬──────────────────────────────────────────┐
│ SIGNAUX  │  TOOLBAR                                 │
│ (sidebar)│  LAYOUT [1×1][2×1][2×2][3×2]  🗺 CARTE  🔍 ✋ ↺  [+ PANEL] │
│ masquable│──────────────────────────────────────────│
│          │                                          │
│  Att. ▾  │   Panel grid (configurable)              │
│  roll_IMU│                                          │
│  roll_des│                                          │
│  pitch.. │                                          │
│  Mot. ▾  │                                          │
│  m1_PWM  │                                          │
│  m3_PWM  │                                          │
│  GPS ▾   │                                          │
│  vbat_V  │                                          │
└──────────┴──────────────────────────────────────────┘
```

### Sidebar signaux
- Largeur 130px, réductible à 28px (icône ≡)
- Signaux groupés par catégorie : ATTITUDE, PID, MOTEURS, SERVOS, GPS/BAT, IMU
- Drag & drop vers n'importe quel panel
- Indicateur couleur par signal (dot coloré)

### Toolbar
- **LAYOUT** : boutons 1×1 / 2×1 / 2×2 / 3×2 — reconfigure la grille CSS instantanément
- **🗺 CARTE** : toggle — ajoute/retire un panel Carte dans la grille
- **🔍 ZOOM** / **✋ PAN** / **↺ RESET** : modes d'interaction sur les graphes
- **＋ PANEL** : ajoute un panel vide en bas de la grille

### Panel graphe — header
Chaque panel a un header avec :
- Tags des courbes actives : `[● roll_IMU ×]` (× = retirer la courbe)
- Zone drop `+ drop` pour accueillir un nouveau signal par drag
- Boutons : `⇅` (axe Y), `⊕` (dupliquer panel), `✕` (fermer panel)

### Interactions graphe (style MATLAB)
- **Scroll molette** → zoom horizontal centré sur la souris
- **Drag** → pan
- **↺ Reset** → revenir à la vue complète
- **Curseur partagé** : ligne verticale ambre synchronisée sur tous les panels, affiche `t = XX.X s` en tooltip
- La carte (si visible) synchronise la position GPS avec le curseur

### Panel Carte (dans la grille graphes)
- Même fond map que l'onglet télémétrie
- Point orange = position drone à `t` curseur
- Bouton ✕ dans le header = cache la carte (équivalent au toggle toolbar)

---

## Onglet 3 — ANALYSE

### Sélecteur (chips)

```
A [📐 PID] [〰 VIBRATIONS] [🧭 EKF] [🌐 TRAJECTOIRE] [⚡ MOTEURS]  |  B [idem]
```

- **Slot A** (vert) : analyse principale
- **Slot B** (cyan) : analyse secondaire optionnelle
- 0 sélection → état vide avec invite
- 1 sélection → panel pleine largeur
- 2 sélections → côte à côte 50/50
- Cliquer un chip déjà sélectionné dans le même slot → désélectionne

### Analyses disponibles

| ID | Nom | Contenu |
|----|-----|---------|
| PID | Analyse PID | `roll_des` vs `roll_IMU` (et pitch, yaw) — erreur, step response, fréquence d'oscillation |
| FFT | Vibrations FFT | FFT sur AccX/Y/Z — spectre de fréquences, annotation des pics avec seuil |
| EKF | Analyse EKF | Innovation, variance, détection de divergence (si données EKF disponibles) |
| TRAJ | Trajectoire 3D | Tracé 3D lat/lon/alt avec Chart.js ou SVG, altitude colorée |
| MOTOR | Bilan moteurs | Différentiel M1 vs M3, corrélation microtilt S1/S2 vs attitude, saturation |

Chaque panel analyse a :
- Header coloré (vert pour A, cyan pour B) avec nom + paramètres + bouton `⬇ PNG`
- Corps : visualisation spécifique à l'analyse

---

## Ce qui ne change PAS

- Le HTML reste source de vérité des calculs (Madgwick, PID, etc.)
- `flight_pack.json` reste le format d'échange HTML → Python
- Les endpoints API existants ne changent pas
- La génération HUD (onglet futur) reste inchangée côté Python

---

## Implémentation

Le redesign se fait **dans `web/viewer.html`** existant, par réécriture progressive :
1. Mettre en place la structure onglets + CSS variables design system
2. Implémenter l'onglet Graphes (le plus utilisé)
3. Implémenter l'onglet Télémétrie
4. Implémenter l'onglet Analyse

Les calculs JS existants (Madgwick, buildFlightStats, etc.) sont conservés, seule la couche présentation change.

---

## Hors scope (pour l'instant)

- Sync vidéo automatique (étape 8 roadmap)
- Onglet Comparaison (multi-sessions)
- Onglet HUD (déjà implémenté séparément)
- Resize des panels par drag (trop complexe pour v1)
