# Design — Support des fichiers .meta dans DEDAL Studio

**Date :** 2026-04-27  
**Scope :** étape 10 de la roadmap

---

## Contexte

Le firmware DEDAL génère désormais un fichier `LOG_NNN.meta` optionnel à côté de chaque `LOG_NNN.csv`. Ce fichier contient une référence horaire GPS permettant de reconstruire l'horodatage UTC absolu de chaque ligne du log.

Format `.meta` :
```
# DEDAL flight log metadata
GPS_UTC_REF=2026-04-23T14:32:05.67
MICROS_REF=1234567890
LOG_FILE=LOG_023.csv
```

---

## Objectifs

1. Parser le `.meta` automatiquement à l'import du CSV (si présent dans le même répertoire).
2. Permettre l'ajout d'un `.meta` après coup via dépôt manuel dans le session folder + bouton "Recharger".
3. Afficher deux dates sur la home page : date du vol + date d'import.
4. Ajouter un onglet "INFOS" dans le viewer avec récap du vol et zone de commentaires.
5. Afficher l'heure locale du vol en tenant compte du fuseau horaire GPS.

---

## Approche retenue

**Approche "Tout dans session.json"** : les données .meta sont parsées et les champs calculés (`flight_date_utc`, `tz_name`, `tz_offset_s`) sont mis en cache dans `session.json`. Cohérent avec le pattern `gps_home` déjà en place (lazy-populate).

---

## Modèle de données

### Nouveaux champs dans `session.json`

Tous optionnels (null si .meta absent) :

```json
{
  "imported_at":     "2026-04-27T10:15:00",
  "flight_date_utc": "2026-04-23T14:32:05",
  "tz_name":         "Europe/Paris",
  "tz_offset_s":     7200,
  "meta_ref": {
    "gps_utc_ref": "2026-04-23T14:32:05.67",
    "micros_ref":  1234567890
  },
  "notes": ""
}
```

- `imported_at` : `datetime.now()` au moment de l'import dans l'app. Fallback `created_at` pour les sessions existantes.
- `flight_date_utc` : ISO string de `GPS_UTC_REF` (précision à la seconde). Null si pas de .meta.
- `tz_name` : IANA timezone name résolu depuis `gps_home` via `timezonefinder`. Null si pas de coords.
- `tz_offset_s` : offset UTC en secondes à la date du vol (DST-aware). Utilisé côté JS sans lib.
- `meta_ref` : valeurs brutes du .meta pour recalcul futur (toggle UTC/local dans graph explorer — hors scope v1).
- `notes` : texte libre éditable dans l'onglet INFOS.

### Nouveau fichier dans le session folder

`log.meta` — copie du fichier `.meta` source (même logique que `log.csv`).

### Champ `created_at` inchangé

Reste le mtime du CSV (meilleure estimation de la date de vol sans .meta). `flight_date_utc` le complète/remplace pour l'affichage quand disponible.

---

## Backend Python

### `dedal/sessions.py`

**Nouvelle fonction `parse_meta_file(path: Path) -> dict | None`**
- Lit le fichier ligne par ligne, ignore les lignes `#` et les clés inconnues.
- Retourne `{"gps_utc_ref": str, "micros_ref": int, "log_file": str}` ou `None` si absent/malformé.
- Si `LOG_FILE` ne correspond pas au CSV chargé : parse quand même, log un warning.

**Nouvelle fonction `_resolve_timezone(lat: float, lon: float, dt_utc: datetime) -> tuple[str, int]`**
- Utilise `timezonefinder.TimezoneFinder().timezone_at(lat=lat, lng=lon)`.
- Calcule l'offset DST-aware avec `zoneinfo.ZoneInfo` à la date `dt_utc`.
- Fallback `("UTC", 0)` si coordonnées absentes, timezone non trouvée, ou exception.

**`import_log()` étendu**
1. Copie du CSV comme avant.
2. Cherche `{csv_stem}.meta` dans le répertoire source du CSV.
3. Si trouvé : copie vers `session_folder/log.meta`, parse, remplit `meta_ref`, `flight_date_utc`, résout timezone si `gps_home` disponible.
4. Remplit toujours `imported_at = datetime.now()`.

**`Session` dataclass**
6 nouveaux champs : `imported_at`, `flight_date_utc`, `tz_name`, `tz_offset_s`, `meta_ref`, `notes`.
`to_dict()` et `load_session()` mis à jour.

### `dedal/server.py`

**Nouveau endpoint `POST /api/sessions/{lid}/reload-meta`**
- Relit `log.meta` depuis le session folder (si présent).
- Recalcule timezone depuis `gps_home`.
- Met à jour `session.json` atomiquement.
- Retourne le session dict mis à jour ou `{"warning": "no log.meta found"}` si absent.

**`PATCH /api/sessions/{lid}` étendu**
- Accepte le champ `notes: str | None` en plus de `nickname` et `tags`.

### Nouvelle dépendance

`timezonefinder` — à ajouter dans `requirements.txt` et installer dans `.venv`.

---

## Frontend

### `web/index.html` — Home page

**Grid de colonnes** : la colonne "Date" actuelle (1 col) est remplacée par 2 colonnes :
- **"VOL"** : `flight_date_utc` converti en heure locale via `tz_offset_s` si disponible, sinon `created_at` (mtime CSV). Indicateur discret `[tz_name]` ou `UTC` affiché à côté.
- **"IMPORT"** : `imported_at` si présent, sinon `created_at` (fallback sessions existantes).

**Bouton "⟳ META"** : discret (style `.btn.sm`), visible sur chaque ligne ayant un `log_file`. Appelle `POST /api/sessions/{lid}/reload-meta`, rafraîchit la ligne. Utile après dépôt manuel d'un `.meta` dans le session folder.

Le modal d'import n'est pas modifié — le .meta est détecté silencieusement.

### `web/viewer.html` — Onglet INFOS

**Nouvel onglet** `◉ INFOS` entre ANALYSE et HUD (disabled). Activé dès qu'un log est chargé.

**Contenu :**

*Bloc Vol*
- Date UTC (depuis `flight_date_utc` ou `created_at`)
- Heure locale (UTC + `tz_offset_s`, label `[tz_name]`)
- Durée du vol, nombre de points

*Bloc Système*
- Firmware, config name (depuis `log_meta`)
- GPS home (lat/lon)

*Bloc Référence temporelle*
- Si .meta : affiche `GPS_UTC_REF` + `MICROS_REF` (pour debug/info)
- Si pas de .meta : message discret "Horodatage absolu non disponible"

*Bloc Commentaires*
- `<textarea>` pré-remplie avec `notes`
- Bouton "Sauvegarder" → `PATCH /api/sessions/{lid}` `{notes: "..."}`
- Feedback visuel (saved / error)

**Chargement :** lazy au premier clic sur l'onglet, via `GET /api/sessions/{lid}`. Le LID est déjà dans `?lid=` dans l'URL.

---

## Hors scope (roadmap future)

- Toggle UTC ↔ heure locale dans le graph explorer (Chart.js) — requiert de passer `meta_ref` + `tz_offset_s` au code IIFE, chantier non trivial.
- Affichage du timestamp absolu au survol des courbes.
- Tri/filtrage par date de vol sur la home page.

---

## Tests à mettre à jour

- `tests/test_sessions.py` : tester `parse_meta_file` (présent, absent, malformé, clé inconnue, LOG_FILE mismatch), `import_log` avec/sans .meta, `_resolve_timezone`.
- `tests/test_api_sessions.py` : tester `POST /reload-meta`, `PATCH notes`.

---

## Endpoints API mis à jour

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/api/sessions/{lid}/reload-meta` | Recharger depuis `log.meta` sur disque |
| PATCH | `/api/sessions/{lid}` | + champ `notes` |
