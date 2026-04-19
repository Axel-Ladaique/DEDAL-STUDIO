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
  }
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
| PATCH | `/api/sessions/{lid}` | Modifier nickname / tags |
| DELETE | `/api/sessions/{lid}` | Supprimer session + dossier |
| POST | `/api/sessions/{lid}/video` | Attacher une vidéo |
| GET | `/api/sessions/{lid}/log` | Servir le CSV brut de la session |
| GET | `/api/sessions/{lid}/sync` | Lire sync.json |
| PUT | `/api/sessions/{lid}/sync` | Écrire offset vidéo dans sync.json |

À venir :
- `GET /api/sessions/{lid}/pack` — lire flight_pack.json (étape 4)
- `PUT /api/sessions/{lid}/pack` — recevoir flight_pack depuis le HTML (étape 4)
- `POST /api/sessions/{lid}/hud` — générer le HUD avec progression SSE (étape 5)

---

## Roadmap

| Étape | Objectif | Statut |
|-------|----------|--------|
| 1 | Skeleton : serveur + fenêtre + HTML statique | ✅ |
| 2 | Sessions : modèle, LID, import CSV, home page, API CRUD | ✅ |
| 2d | Reverse-géocodage Nominatim avec cache dans session.json | ⬜ |
| 3 | Viewer HTML intégré + player vidéo + sync manuel 2 curseurs | ✅ |
| 4 | Flight pack JSON (export HTML → endpoint serveur) | ✅ |
| 5 | HUD Python refactoré (lit flight_pack, widgets, progression SSE) | ← next |
| 6 | Carte Leaflet sur home page | ⬜ |
| 7 | Sync vidéo automatique | ⬜ |

---

## Conventions de travail

- Commits git à la fin de chaque étape : demander à l'utilisateur avant de pousser
- Lancer `python -m pytest` avant de déclarer une étape terminée
- Ne pas refactoriser le viewer HTML existant sans demander
- Ne pas ajouter de dépendances sans les ajouter à `requirements.txt` ET les installer dans `.venv`
- `INPUT_4_CLAUDE/` = dossier où l'utilisateur dépose des exemples de fichiers réels à analyser
- Mettre à jour ce fichier CLAUDE.md à chaque fin d'étape (roadmap + endpoints)

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
