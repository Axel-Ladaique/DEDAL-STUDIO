# Live Telemetry — Design Spec
**Date :** 2026-05-21  
**Étape :** 11 (nouvelle)  
**Statut :** Approuvé, prêt pour implémentation

---

## Résumé

Page `live.html` dédiée à la télémétrie temps réel depuis le drone via ELRS + TX16S branchée en USB.  
Le CRSFReader (déjà développé dans `INPUT_4_CLAUDE/CRSF_test_standalone/dedal_crsf.py`) est intégré comme module dans le package `dedal/`. Les données sont streamées vers le frontend via SSE.

---

## Flux de données

```
DEDAL (Teensy) ──ELRS 2.4GHz──► TX16S ──USB CDC──► PC

TX16S (USB passthrough CLI) ──serial──► CRSFReader thread
                                                │
                                    TELEMETRY_STATE dict (thread-safe)
                                                │
                          FastAPI GET /api/live/stream (SSE, 100ms)
                                                │
                                     live.html EventSource (JS)
                                                │
                               update DOM + stats accumulator
```

---

## Fichiers

### Nouveaux
| Fichier | Rôle |
|---------|------|
| `dedal/crsf.py` | Copie de `dedal_crsf.py` intégrée dans le package — CRSFReader, décodeurs, TELEMETRY_STATE |
| `dedal/live.py` | LiveSession : lifecycle du reader, accumulation des stats armed |
| `web/live.html` | Page HTML autonome, même style que viewer.html |

### Modifiés
| Fichier | Changement |
|---------|-----------|
| `dedal/server.py` | +5 routes `/api/live/*` + mount `live.html` |
| `web/index.html` | Bouton `⚡ LIVE` dans la topbar, à droite de `⊹ MODÈLE` |
| `requirements.txt` | Ajout `pyserial>=3.5` |

---

## API Endpoints

| Méthode | Route | Corps / Réponse | Rôle |
|---------|-------|-----------------|------|
| GET | `/api/live/ports` | `[{port, description}]` | Liste ports série disponibles (filtre usbmodem / ttyACM / COM) |
| POST | `/api/live/connect` | body: `{port: str, baud: int=921600}` | Démarre CRSFReader, 400 si déjà connecté |
| POST | `/api/live/disconnect` | — | Arrête reader, libère port |
| GET | `/api/live/stream` | SSE — events `telemetry` + `stats` toutes les 100ms | Stream continu |
| GET | `/api/live/state` | snapshot JSON de TELEMETRY_STATE + stats | One-shot pour reconnexion |

### Format SSE

```
event: telemetry
data: {"battery_voltage":24.65,"battery_current":5.42,"battery_percent":78,...}

event: stats
data: {"armed":true,"armed_duration_s":222,"gps_alt_max":87,"gps_alt_avg":52,"gps_speed_max":42,...}
```

---

## Module `dedal/live.py`

```python
class LiveSession:
    reader: CRSFReader | None
    stats: ArmedStats        # accumulateur max/moy période armée

    def connect(port, baud) -> None
    def disconnect() -> None
    def is_connected() -> bool
    def get_state() -> dict          # snapshot TELEMETRY_STATE
    def get_stats() -> dict          # stats période armée courante

class ArmedStats:
    # Reset à chaque nouveau cycle armement (disarmé→armé)
    # Calcul moy incrémental, pas de stockage historique

    gps_alt_max, gps_alt_avg
    gps_speed_max, gps_speed_avg
    distance_home_max, distance_home_avg
    battery_current_max, battery_current_avg
    battery_voltage_min
    loop_time_max, loop_time_avg
    roll_abs_max
    pitch_abs_max
    vario_max, vario_min
    sample_count: int
    armed_start_ts: float
    armed_duration_s: float   # calculé à chaque update : time.time() - armed_start_ts
```

Singleton `_live_session = LiveSession()` instancié à l'import, utilisé par les routes.

---

## Layout `live.html`

Même structure CSS que l'onglet TÉLÉMÉTRIE du viewer (`#telem-grid`, `.telem-cell`, `.data-value`, etc.).  
Grid : `grid-template-columns: 1.4fr 1fr 1fr` — `grid-template-rows: 1fr 1fr 0.55fr`.

### Topbar
```
⚡ LIVE  [select port ▾]  [↻ SCANNER]  [● CONNECTÉ]  [ARMED · 03:42]
                                         ← margin auto →
[LQ 99%]  [RSSI −34dBm]  [SNR +12dB]  [250Hz]  [⏺ ENREGISTRER]  [✕ DÉCONNECTER]
```

### Panels (identiques au viewer sauf indiqué)
| Position | Panel | Delta vs viewer |
|----------|-------|-----------------|
| Col 1, rows 1–2 | CARTE GPS + coords/sats/alt/dist home/vario | Identique |
| Col 2, row 1 | ÉTAT DE VOL | MODE et temps armé en `font-size:28px` (vs 13px) |
| Col 3, row 1 | BATTERIE *(remplace Stats vol)* | Tension 30px, barre %, 6 cellules |
| Col 2, rows 2–3 | ATTITUDE | Identique + section baro/cap mag en bas |
| Col 3, rows 2–3 | RADIO RC | Identique |
| Col 1, row 3 | MOTEURS & SERVOS | Identique |

### Bande stats (sous la grille)
Bande horizontale fine `border-top: 1px solid rgba(0,255,157,0.12)`.  
Stats affichées : alt GPS max/moy, vitesse GPS max/moy, dist home max/moy, courant max/moy, vbat min, loop max/moy, roll max, vario max/min.  
Mise à jour en temps réel pendant le vol armé. Reset à chaque nouveau armement.

---

## État de connexion — comportement

| État | Topbar | Panels |
|------|--------|--------|
| Déconnecté | bouton `CONNECTER`, select port actif | panels vides `--` |
| Connecté, désarmé | `● CONNECTÉ` vert, `DISARMED` orange | données live, stats vides |
| Connecté, armé | `● CONNECTÉ` + `ARMED · MM:SS` | données live, stats s'accumulent |
| Erreur port | badge rouge `⚠ ERREUR PORT` | message d'erreur dans topbar |

---

## Stats accumulées (période armée uniquement)

Toutes les stats sont reset quand `flag_armed` passe de `True` → `False` → `True`.  
Calcul moy incrémental : `avg = avg + (new - avg) / n`.

| Champ stat | Source CRSF |
|-----------|-------------|
| `gps_alt_max` / `_avg` | `gps_alt_m` |
| `gps_speed_max` / `_avg` | `gps_speed_kmh` |
| `distance_home_max` / `_avg` | `distance_home_m` |
| `battery_current_max` / `_avg` | `battery_current` |
| `battery_voltage_min` | `battery_voltage` |
| `loop_time_max` / `_avg` | `loop_time_us` |
| `roll_abs_max` | `abs(attitude_roll_deg)` |
| `pitch_abs_max` | `abs(attitude_pitch_deg)` |
| `vario_max` / `_min` | `vario_m_s` |

---

## Hors scope (pour plus tard)

- **Envoi de commandes** : architecture bidirectionnelle (WebSocket ou endpoint POST → écriture sur port série)
- **Transfert fichiers SD** : transmission des logs depuis la carte SD via liaison radio
- **Enregistrement vol live** : bouton `⏺ ENREGISTRER` présent dans l'UI mais non câblé v1
- **Sync vidéo live** : non prévu

---

## Dépendances

- `pyserial>=3.5` — à ajouter dans `requirements.txt`
- `dedal_crsf.py` existant (`INPUT_4_CLAUDE/`) — copié dans `dedal/crsf.py`
- Pas de nouvelle dépendance frontend

---

## Tests

- `tests/test_live.py` : test `GET /api/live/ports` (toujours 200), test `POST /api/live/connect` avec port invalide (400/422), test `ArmedStats` accumulation et reset.
- Pas de test d'intégration série (matériel requis).
