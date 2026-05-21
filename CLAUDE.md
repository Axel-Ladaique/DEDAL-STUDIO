# CLAUDE.md — DEDAL Studio

Mémoire de projet pour Claude Code. Lire ce fichier au début de chaque session.
Communication : **français**. Code / docstrings : **anglais**.

---

## Projet

**DEDAL** = Drone Expérimental à Décollage et Atterrissage Localisé — VTOL birotor ~1m envergure, firmware dRehmFlight Beta 1.3 (customisé). Développeur solo.

**DEDAL Studio** = app desktop unifiée qui remplace :
- Un viewer HTML monolithique (`vtol_viewer-31.html`, ~9200 lignes, source de vérité des calculs)
- Un générateur HUD Python séparé (`hud_generator.py`)
- Zéro outil de gestion des logs

Les 3 fonctions cibles :
1. **Visualiser les logs** — réutilise le viewer HTML existant (pas à refactoriser)
2. **Générer un HUD** — superposition sur vidéo (refacto du hud_generator.py)
3. **Synchroniser vidéo** — player vidéo synchronisé avec le curseur du log

**Fil conducteur** : le HTML reste la source de vérité des calculs. Il écrit `flight_pack.json`, le HUD Python le consomme.

---

## Stack

| Composant | Choix |
|-----------|-------|
| Serveur local | FastAPI + uvicorn, `127.0.0.1:7860` (auto-increment si pris) |
| Fenêtre native | PyWebView (WebKit sur macOS, pas de Chromium) |
| Fallback | navigateur par défaut si pywebview absent |
| Frontend | HTML/JS vanilla, pas de framework |
| Encodage HUD | ffmpeg CLI (brew install, externe) |
| Plateforme cible | macOS d'abord |

---

## Architecture

```
dedal-studio/
├── app.py                  # launcher (PyWebView + FastAPI en thread daemon)
├── requirements.txt
├── README.md
├── CLAUDE.md               # ce fichier
├── dedal/
│   ├── __init__.py
│   ├── config.py           # ~/.config/dedal-studio/config.json
│   ├── server.py           # FastAPI app factory + routes
│   ├── sessions.py         # modèle Session + fonctions CRUD
│   └── hud/                # (étape 5) HUD generator refactoré
├── web/
│   ├── index.html          # home page sessions
│   ├── viewer.html         # (étape 3) viewer HTML adapté
│   └── assets/
├── flights/                # dossier par défaut si config absente
└── tests/
    ├── conftest.py
    ├── test_sessions.py    # unit tests sessions model
    └── test_api_sessions.py
```

### Layout d'une session sur disque

```
~/DEDAL/flights/
  flight_YYYYMMDD_NNN/
    session.json        ← métadonnées
    LOG_017.csv         ← copie du CSV original (nom d'origine conservé)
    video.mp4           ← optionnel
    sync.json           ← { video_offset_ms: int } (étape 3)
    flight_pack.json    ← calculs exportés par le viewer HTML (étape 4)
    hud_output/         ← séquence PNG transparente (étape 5)
```

### Format session.json

```json
{
  "lid":         "DEDAL-20260419-001",
  "nickname":    "Mission Alpha",
  "created_at":  "2026-04-19T14:32:00",
  "log_file":    "LOG_017.csv",
  "video_file":  null,
  "tags":        [],
  "location":    null,
  "log_meta": {
    "filename":    "LOG_017.csv",
    "config_name": "VTOL_CONFIG_v0.49",
    "fw_version":  "Beta 1.3",
    "row_count":   21543,
    "duration_s":  87.4
  },
  "imported_at":     "2026-04-27T10:15:00",
  "flight_date_utc": "2026-04-23T14:32:05",
  "tz_name":         "Europe/Paris",
  "tz_offset_s":     7200,
  "meta_ref": {
    "gps_utc_ref": "2026-04-23T14:32:05.67",
    "micros_ref":  1234567890,
    "log_file":    "LOG_017.csv"
  },
  "notes": ""
}
```

### LID

Format : `DEDAL-YYYYMMDD-NNN`
- Date = mtime du fichier CSV source (le CSV n'a pas de timestamp absolu — `timestamp_us` est µs depuis power-on du MCU)
- NNN = compteur du jour, 3 chiffres, incrémenté en scannant les dossiers `flight_YYYYMMDD_*` existants
- Dossier = `flight_YYYYMMDD_NNN` (dérivé du LID de façon déterministe)

---

## Décisions figées (ne pas remettre en cause sans demander)

| Décision | Valeur |
|----------|--------|
| Plateforme cible | macOS d'abord |
| Import CSV | Copie (jamais déplace) le fichier source |
| LID | `DEDAL-YYYYMMDD-NNN`, date = mtime CSV |
| Dossier session | `flight_YYYYMMDD_NNN/` |
| Save session.json | Atomique : `.tmp` puis `os.replace` |
| Calculs | HTML source de vérité, écrit flight_pack.json |
| Sync vidéo v1 | Manuel 2 curseurs, offset stocké dans sync.json |
| Sync vidéo v2 | Automatique (métadonnées GoPro/DJI ou audio) — plus tard |
| HUD sortie | Séquence PNG transparente |
| Reverse géocode | Nominatim/OSM avec cache dans session.json (étape 2d) |

---

## Firmware dRehmFlight — spécificités DEDAL

Convention IMU : `X+` = arrière, `Y+` = droite, `Z+` = haut (BRU).
Remap firmware vers FRD avant Madgwick : `Madgwick(GyroX, -GyroY, -GyroZ, -AccX, AccY, AccZ, ...)`
`roll_IMU/pitch_IMU/yaw_IMU` = convention aéronautique standard.

Birotor :
- **M1 = moteur DROIT**, **M3 = moteur GAUCHE** (M2/M4/M5/M6 idle)
- **S1 = microtilt gauche**, **S2 = microtilt droit**
- S3/S4 = ailerons (flaps en hover), S5 = élevateur, S6 = mode, S7 = dérive

Batterie : alerte 3.6V/cellule (LiPo 6S → 21.6V).

---

## Endpoints API (état actuel)

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/api/health` | Santé + version + flights_root |
| GET | `/api/sessions` | Liste toutes les sessions (desc par date) |
| POST | `/api/sessions` | Créer session vide (body: {nickname, tags}) |
| POST | `/api/sessions/import` | Importer CSV → crée session (query: nickname) |
| GET | `/api/sessions/{lid}` | Lire une session |
| PATCH | `/api/sessions/{lid}` | Modifier nickname / tags / notes |
| DELETE | `/api/sessions/{lid}` | Supprimer session + dossier |
| POST | `/api/sessions/{lid}/video` | Attacher une vidéo |
| POST | `/api/sessions/{lid}/hud` | Générer séquence PNG HUD (SSE progress) — params: fps, width, height, cells, min_gps_sats, t_start_s, t_end_s, output_path |
| GET | `/api/sessions/{lid}/log` | Servir le CSV brut de la session |
| GET | `/api/sessions/{lid}/sync` | Lire sync.json |
| PUT | `/api/sessions/{lid}/sync` | Écrire offset vidéo dans sync.json |

| GET | `/api/sessions/{lid}/pack` | Lire flight_pack.json |
| PUT | `/api/sessions/{lid}/pack` | Recevoir flight_pack depuis le HTML |
| GET | `/api/panel-templates` | Lire les templates de panels sauvegardés |
| PUT | `/api/panel-templates` | Écrire les templates de panels |
| POST | `/api/sessions/{lid}/reload-meta` | Recharger les métadonnées depuis `log.meta` sur disque |
| GET | `/api/pick-folder/available` | Vérifie si pywebview a une fenêtre ouverte |
| GET | `/api/pick-folder` | Ouvre le sélecteur de dossier natif (pywebview) |
| GET | `/api/live/ports` | Liste ports série disponibles (filtre usbmodem/ttyACM/COM) |
| POST | `/api/live/connect` | Démarre CRSFReader sur le port donné (body: {port, baud}) |
| POST | `/api/live/disconnect` | Arrête le CRSFReader, libère le port |
| GET | `/api/live/state` | Snapshot JSON télémétrie + stats (pour reconnexion) |
| GET | `/api/live/stream` | SSE — events `telemetry` + `stats` toutes les 100ms |

---

## Roadmap

| Étape | Objectif | Statut |
|-------|----------|--------|
| 1 | Skeleton : serveur + fenêtre + HTML statique | ✅ |
| 2 | Sessions : modèle, LID, import CSV, home page, API CRUD | ✅ |
| 2d | Reverse-géocodage Nominatim avec cache dans session.json | ⬜ |
| 3 | Viewer HTML intégré + player vidéo + sync manuel 2 curseurs | ✅ |
| 4 | Flight pack JSON (export HTML → endpoint serveur) | ✅ |
| 5 | HUD Python refactoré (lit flight_pack, widgets, progression SSE) | ✅ |
| 5b | Bug fix : auto-load viewer (TDZ `dsGenerateHUD` dans IIFE strict) | ✅ |
| 6 | Carte Leaflet sur home page | ✅ |
| 7 | HUD — options avancées (fps UI, t_start/t_end, output_path) | ✅ |
| 8 | Sync vidéo automatique | ⬜ |
| 9 | Graph explorer — améliorations UX (panels, templates, drag-to-swap) | ✅ |
| 10 | Support fichiers .meta (timezone, dates, onglet INFOS, notes) | ✅ |
| 11 | Télémétrie live CRSF (TX16S USB → SSE → live.html) | ✅ |

---

## Graph Explorer — améliorations UX (étape 9, en cours)

### Implémenté (session 2026-04-25)

- **Zoom/pan** : réécrit avec AbortController, re-setup à chaque switch d'onglet
- **Axe X Chart.js** : `x.min/max` forcés = signal remplit toute la largeur, zoom précis
- **Zoom-box** : calcul `x1pct/x2pct` via `chart.chartArea` (exclut zone axe Y)
- **Drag signal → vide** : créé un nouveau panel automatiquement
- **Clic droit sur légende** : popup couleur (`input[type=color]`) + 4 styles de ligne
  - `solid` `[]`, `dashed` `[6,3]`, `dotted` `[2,4]`, `dashdot` `[8,3,2,3]`
  - `curve.style` (string) dans `panel.curves`, lu dans `refreshPanelChart` → `borderDash`
- **Bouton 💾 sur chaque panel** : `savePanelTemplate(pid)` — prompt nom, stocke via API
- **Bouton ⊞ SAVED** (à droite de ＋ PANEL) : `toggleSavedMenu()` — dropdown des templates
- **Persistance templates** : `GET/PUT /api/panel-templates` → `~/.config/dedal-studio/panel_templates.json`

### Bugs connus / non résolus (à reprendre)

- **Popup couleur / savePanelTemplate ne fonctionnent pas** : les fonctions qui accèdent à `gPanels` sont maintenant dans l'IIFE (bonne approche), mais le comportement n'a pas été vérifié après refactoring. Vérifier dans la console si `showCurvePopup` est appelé et si `_cpopState` est bien renseigné.
- **Attitude 3D shift** : canvas AHI passé à taille fixe `width:130px;height:130px` + setTimeout 50ms pour resizeDrone3D — non vérifié visuellement.
- **Panels sauvegardés** : le flux save→load via `/api/panel-templates` a été codé mais non testé end-to-end.

### Architecture IIFE / scope — piège critique

Le graph explorer est dans une IIFE strict (`(function() { 'use strict'; ... })()`). Les fonctions qui accèdent à `gPanels`, `gCharts`, `refreshPanelChart` DOIVENT être déclarées **à l'intérieur** de cette IIFE et exportées via `window.fn = fn`. Ne JAMAIS essayer d'accéder à `gPanels` depuis un script extérieur via `window.gPanels = gPanels` — ça ne reste pas synchronisé si `gPanels` est réassigné (ex: `gPanels = gPanels.filter(...)`).

Fonctions actuellement dans l'IIFE et exportées :
- `showCurvePopup`, `onCurvePopupColor`, `onCurvePopupStyle`, `closeCurvePopup`
- `savePanelTemplate`, `applyPanelTemplate`

Fonctions dans le script externe (pas besoin de gPanels) :
- `toggleSavedMenu`, `deletePanelTemplate`, `loadPanelTemplates`, `storePanelTemplates`
- Fermeture popup/menu sur clic extérieur (mousedown listener)

---

## Conventions de travail

- Commits git à la fin de chaque étape : demander à l'utilisateur avant de pousser
- Lancer `python -m pytest` avant de déclarer une étape terminée
- Ne pas refactoriser le viewer HTML existant sans demander
- Ne pas ajouter de dépendances sans les ajouter à `requirements.txt` ET les installer dans `.venv`
- `INPUT_4_CLAUDE/` = dossier où l'utilisateur dépose des exemples de fichiers réels à analyser
- Mettre à jour ce fichier CLAUDE.md à chaque fin d'étape (roadmap + endpoints)

## Pièges connus (à ne pas reproduire)

- **TDZ dans IIFE strict** : dans la couche d'intégration de `viewer.html`, toutes les fonctions (`dsGenerateHUD`, etc.) sont déclarées avec `function` (hoistées) mais si on les référence dans `onclick = fnName` avant leur définition dans le code source, Safari lève `ReferenceError: Can't find variable`. Toujours utiliser `onclick = function() { fn(); }` comme wrapper, ou s'assurer que les fonctions sont déclarées avant d'être référencées.
- **Plusieurs instances du serveur** : si `python app.py` est lancé plusieurs fois, les instances s'empilent sur des ports 7860, 7861… Le navigateur peut se connecter à une vieille instance qui sert du code périmé. Toujours vérifier avec `lsof -ti:7860` et tuer les instances parasites avant de relancer.

## Playwright / checks visuels

- MCP Playwright est installé mais cherche Google Chrome système (`/Applications/Google Chrome.app`)
- Chromium + Firefox téléchargés via `npx playwright install` mais disque plein au moment de WebKit
- Si Chrome système présent, les checks visuels sont possibles avec `mcp__playwright__browser_*`
- Contournement possible : `npx playwright install chrome` (alias vers Chrome système)

---

## Notes techniques

### Parsing du CSV log

- Ligne 1 : header `timestamp_us,dt_us,armed,...`
- Lignes `# ...` : config (CONFIG_NAME, FW_VERSION, etc.)
- Lignes de données : valeurs séparées par virgules
- `timestamp_us` : µs depuis power-on MCU (pas epoch)
- `gps_valid` = 1 quand GPS lock acquis ; `gps_lat/lon` en degrés décimaux
- Fréquence log typique : 500 Hz

### Lancer l'app

```bash
source .venv/bin/activate
python app.py --browser    # ouvre dans le navigateur par défaut
python app.py              # fenêtre native PyWebView
python app.py --no-window  # serveur seul
```

### Lancer les tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```
