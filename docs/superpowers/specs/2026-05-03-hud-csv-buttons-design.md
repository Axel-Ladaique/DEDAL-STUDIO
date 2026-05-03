# Design — HUD fix + rationalisation boutons + modale CSV + file picker

**Date :** 2026-05-03  
**Branch :** feature/analyse-redesign  
**Scope :** 4 changements indépendants livrés ensemble

---

## 1. Fix TypeError HUD (`dedal/hud/generator.py`)

### Problème
Dans `load_pack`, `dict.get(key, default)` retourne `None` si la clé existe mais vaut `null` (JSON null). Le JS peut sérialiser `NaN` en `null` (ex : champ GPS absent dans le CSV). Résultat : `float(None)` → `TypeError: float() argument must be a string or a real number`.

### Fix
Ajouter deux helpers en tête de `generator.py` :

```python
def _f(v, d=0.0): return float(v) if v is not None else d
def _i(v, d=0):   return int(v)   if v is not None else d
```

Remplacer tous les `float(fr.get(...))` et `int(fr.get(...))` dans `load_pack` par ces helpers. La logique de `generate_hud` ne change pas.

---

## 2. Suppression "Export Studio" + intégration dans le workflow HUD (`web/viewer.html`)

### Problème
Le bouton `⬆ Export Studio` dans le header n'est pas compréhensible. Il sert uniquement à préparer le `flight_pack.json` avant la génération HUD. L'utilisateur doit le cliquer manuellement avant le HUD.

### Changements
- **Supprimer** l'injection de `exportBtn` (`ds-export-btn`) dans le header (bloc `if (LID)` de l'integration layer).
- **Refactoriser** `dsExportPack()` en `dsExportPackAsync()` qui retourne une `Promise<void>` (résout si PUT réussit, rejette si erreur).
- **Conserver** `dsExportPack()` comme wrapper `dsExportPackAsync().catch(...)` pour toute invocation standalone éventuelle.
- **Modifier** le handler du bouton "🎬 Générer HUD" pour exécuter la séquence :
  1. Ferme la modale
  2. Bouton → `"⬆ Export pack…"`, classe `busy`
  3. Appelle `dsExportPackAsync()`
  4. Si OK → bouton → `"⏳ Génération…"` → appelle `dsGenerateHUD(opts)` (inchangé)
  5. Si échec pack → bouton → `"✕ Erreur pack"`, toast, reset après 3 s

### Ce qui ne change pas
- L'API `PUT /api/sessions/{lid}/pack` est inchangée.
- La fonction `dsGenerateHUD()` est inchangée.
- Le bouton `⬇ CSV` et `⬇ PID` dans le header : le PID reste tel quel (hors scope).

---

## 3. Modale export CSV (`web/viewer.html`)

### Problème
Le bouton `⬇ CSV` déclenche directement un téléchargement sans contrôle (colonnes fixes, plage = vue courante).

### Changements
Le clic sur `⬇ CSV` ouvre une modale HTML (créée une fois à l'init, réutilisée).

#### Structure de la modale
```
┌─ EXPORT CSV ──────────────────────────────┐
│ PLAGE TEMPORELLE                           │
│  ● Vue actuelle                            │
│  ○ Tout le vol                             │
│  ○ Personnalisée  [  0.0 ] → [     ]       │
│                                            │
│ COLONNES                           [Tout] [Rien] │
│  ☑ timestamp_us   ☑ roll_IMU  ☑ pitch_IMU │
│  ☑ gps_lat        ☑ gps_lon   ☑ vbat_V    │
│  … (liste scrollable, toutes cochées)     │
│                                            │
│          [Annuler]   [⬇ Exporter]          │
└────────────────────────────────────────────┘
```

#### Colonnes disponibles
- `baseKeys` = `Object.keys(flightData[0])` (colonnes brutes du CSV)
- `extraKeys` = `['time_s', 'vbat_soc_pct', ...activeMotors.map(m => \`m${m}_pct\`)]`
- Toutes cochées par défaut

#### Logique d'export
Réutilise la logique de `exportCSV()` existante, avec :
- Plage calculée selon le choix radio (indices `viewStart/viewEnd`, `0/flightData.length-1`, ou conversion `t_s → index`)
- Filtrage des colonnes selon les cases cochées
- Nom de fichier : `{CONFIG_NAME}_export.csv`

#### Implémentation
- Modale créée via `document.createElement` / `innerHTML` dans le script extérieur (hors IIFE) — pas besoin d'accéder à `gPanels`.
- La fonction `exportCSV()` existante est remplacée par `openCSVExportModal()` (appelée par `onclick` du bouton `btn-export-csv`).

---

## 4. File picker pour le chemin de sortie HUD

### Problème
Le champ texte `ds-hud-outpath` dans la modale HUD est difficile à utiliser (chemin absolu à taper à la main).

### Changements

#### Serveur — `dedal/server.py`
Deux endpoints montés sur le routeur principal (pas sur `_sessions`) :

```
GET /api/pick-folder/available   → vérifie si pywebview est dispo (pas de dialog)
GET /api/pick-folder             → ouvre le dialog natif et retourne le chemin
```

`/api/pick-folder/available` :
- Retourne `{"available": true}` si `webview` est importable et `webview.windows` non vide
- Retourne `{"available": false}` sinon

`/api/pick-folder` :
- Appelle `webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)` via `loop.run_in_executor(None, ...)`.
- Réponses :
  - `{"path": null}` si l'utilisateur annule
  - `{"path": "/chemin/absolu"}` si choix effectué
  - HTTP 503 si pywebview non disponible

#### Client — `web/viewer.html` (integration layer)
Au moment de la création de la modale HUD, appeler `/api/pick-folder/available` :

```javascript
fetch('/api/pick-folder/available').then(r => r.json()).then(function(info) {
  if (info.available) {
    // Masquer le champ texte, afficher : [label chemin] + [📁 Parcourir]
    // Le bouton appelle fetch('/api/pick-folder') et met à jour le label
  }
  // Sinon : garder le champ texte tel quel (browser mode)
});
```

Le champ texte `ds-hud-outpath` reste dans le DOM comme source de la valeur finale ; il est masqué si pywebview est disponible, visible sinon.

---

## Fichiers modifiés

| Fichier | Changement |
|---------|------------|
| `dedal/hud/generator.py` | Helpers `_f` / `_i`, refacto `load_pack` |
| `dedal/server.py` | Nouvel endpoint `GET /api/pick-folder` |
| `web/viewer.html` | Suppression `ds-export-btn`, refacto `dsExportPack`, modale CSV, file picker HUD |

## Fichiers non modifiés
- `app.py` — aucun changement
- `dedal/sessions.py` — aucun changement
- `dedal/hud/renderer.py` — aucun changement
- Tests existants — non cassés (pas de changement d'API publique)

---

## Tests à vérifier
- `python -m pytest tests/ -v` doit passer
- Générer un HUD avec un flight_pack contenant des `null` → plus de TypeError
- Bouton HUD : séquence pack → HUD visible dans le statut du bouton
- Modale CSV : export avec sélection partielle + plage personnalisée
- File picker : fonctionne en mode pywebview, fallback texte en mode `--browser`
