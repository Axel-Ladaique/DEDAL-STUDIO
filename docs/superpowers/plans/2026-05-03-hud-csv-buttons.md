# HUD fix + boutons + modale CSV + file picker — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger le TypeError HUD, supprimer "Export Studio" en l'intégrant dans le workflow HUD, ajouter une modale CSV avec sélection colonnes/plage, et un file picker natif pour le chemin de sortie HUD.

**Architecture:** 4 tâches indépendantes dans l'ordre de dépendance — Python d'abord (testable via pytest), JS ensuite (viewer.html, pas de test automatisé). Les changements JS sont tous dans `web/viewer.html` ; les changements Python dans `dedal/hud/generator.py` et `dedal/server.py`.

**Tech Stack:** Python 3.13, FastAPI, pytest, pywebview 5+, JS ES5/vanilla, viewer.html (IIFE strict mode pour l'integration layer)

---

## Fichiers modifiés

| Fichier | Rôle |
|---------|------|
| `dedal/hud/generator.py` | Helpers `_f`/`_i`, refacto `load_pack` |
| `dedal/server.py` | Endpoints `GET /api/pick-folder/available` et `GET /api/pick-folder` |
| `tests/test_hud.py` | Test null-fields dans load_pack |
| `tests/test_api_sessions.py` | Tests endpoints pick-folder |
| `web/viewer.html` | Suppression Export Studio, intégration HUD, modale CSV, file picker |

---

## Tâche 1 — Fix TypeError HUD : null fields dans `load_pack`

**Fichiers :**
- Modifier : `dedal/hud/generator.py`
- Tester : `tests/test_hud.py`

- [ ] **Étape 1 : Écrire le test qui échoue**

Ajouter dans `tests/test_hud.py`, après `test_load_pack_ekf_fields` :

```python
def test_load_pack_null_fields(tmp_path: Path) -> None:
    """Null values (JSON null = None) must not raise TypeError in load_pack."""
    pack = {
        "version": 1,
        "frames": [{
            "t_us": 1000,
            "armed": None, "fm": None,
            "roll": None, "pitch": None, "yaw": None,
            "lat": None, "lon": None, "alt_m": None,
            "spd_ms": None, "sats": None, "gps_ok": None,
            "m1": None, "m3": None, "vbat": None,
            "Vfwd": None, "Vlat": None, "Vz": None, "Vh": None,
        }],
    }
    p = tmp_path / "pack_nulls.json"
    p.write_text(json.dumps(pack), encoding="utf-8")
    frames = load_pack(p)
    assert len(frames) == 1
    assert frames[0].timestamp_us == 1000
    assert frames[0].roll_deg == 0.0
    assert frames[0].pitch_deg == 0.0
    assert frames[0].flight_mode == 0
    assert frames[0].accel_z == 1.0  # default non-nul
```

- [ ] **Étape 2 : Vérifier que le test échoue**

```bash
source .venv/bin/activate && python -m pytest tests/test_hud.py::test_load_pack_null_fields -v
```

Résultat attendu : `FAILED` avec `TypeError: float() argument must be a string or a real number`

- [ ] **Étape 3 : Ajouter les helpers et refactoriser `load_pack`**

Dans `dedal/hud/generator.py`, remplacer le début du fichier (après les imports, avant `def load_pack`) pour ajouter :

```python
def _f(v, d: float = 0.0) -> float:
    return float(v) if v is not None else d


def _i(v, d: int = 0) -> int:
    return int(v) if v is not None else d
```

Puis dans `load_pack`, remplacer le bloc `frames.append(FlightFrame(...))` par :

```python
        frames.append(FlightFrame(
            timestamp_us = _i(fr.get("t_us")),
            armed        = _i(fr.get("armed")),
            flight_mode  = _i(fr.get("fm")),
            pitch_deg    = _f(fr.get("pitch")),
            roll_deg     = _f(fr.get("roll")),
            yaw_deg      = _f(fr.get("yaw")),
            gps_alt_m    = _f(fr.get("alt_m")),
            gps_speed_ms = _f(fr.get("spd_ms")),
            gps_lat      = _f(fr.get("lat")),
            gps_lon      = _f(fr.get("lon")),
            gps_sats     = _i(fr.get("sats")),
            gps_valid    = _i(fr.get("gps_ok")),
            m1_pwm       = _i(fr.get("m1")),
            m3_pwm       = _i(fr.get("m3")),
            vbat_v       = _f(fr.get("vbat")),
            accel_z      = _f(fr.get("accel_z"), 1.0),
            Vfwd         = _f(fr.get("Vfwd")),
            Vlat         = _f(fr.get("Vlat")),
            Vz           = _f(fr.get("Vz")),
            Vh           = _f(fr.get("Vh")),
        ))
```

- [ ] **Étape 4 : Vérifier que tous les tests passent**

```bash
python -m pytest tests/ -v
```

Résultat attendu : tous verts, notamment `test_load_pack_null_fields` PASSED.

- [ ] **Étape 5 : Commit**

```bash
git add dedal/hud/generator.py tests/test_hud.py
git commit -m "fix(hud): handle null fields in load_pack — float(None) TypeError"
```

---

## Tâche 2 — Endpoints `/api/pick-folder` dans `server.py`

**Fichiers :**
- Modifier : `dedal/server.py`
- Tester : `tests/test_api_sessions.py`

- [ ] **Étape 1 : Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_api_sessions.py` :

```python
# ── pick-folder (pywebview not available in test env) ─────────────────────

def test_pick_folder_available_no_pywebview(client: TestClient) -> None:
    """When pywebview has no open windows, available is False."""
    r = client.get("/api/pick-folder/available")
    assert r.status_code == 200
    data = r.json()
    assert "available" in data
    assert data["available"] is False


def test_pick_folder_no_window(client: TestClient) -> None:
    """When no pywebview window is open, returns 503."""
    r = client.get("/api/pick-folder")
    assert r.status_code == 503
```

- [ ] **Étape 2 : Vérifier que les tests échouent**

```bash
python -m pytest tests/test_api_sessions.py::test_pick_folder_available_no_pywebview tests/test_api_sessions.py::test_pick_folder_no_window -v
```

Résultat attendu : `FAILED` avec 404 (routes inexistantes).

- [ ] **Étape 3 : Ajouter les endpoints dans `create_app`**

Dans `dedal/server.py`, à l'intérieur de `create_app`, après le bloc `put_tag_colors` et avant `if WEB_DIR.exists():`, ajouter :

```python
    # ── Native folder picker (pywebview) ──────────────────────────────────
    @app.get("/api/pick-folder/available")
    def pick_folder_available() -> JSONResponse:
        try:
            import webview  # pywebview
            available = bool(webview.windows)
        except ImportError:
            available = False
        return JSONResponse({"available": available})

    @app.get("/api/pick-folder")
    async def pick_folder() -> JSONResponse:
        try:
            import webview  # pywebview
        except ImportError:
            return JSONResponse({"error": "pywebview not available"}, status_code=503)
        if not webview.windows:
            return JSONResponse({"error": "no pywebview window"}, status_code=503)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG),
        )
        path = result[0] if result else None
        return JSONResponse({"path": path})
```

- [ ] **Étape 4 : Vérifier que les tests passent**

```bash
python -m pytest tests/ -v
```

Résultat attendu : tous verts.

- [ ] **Étape 5 : Commit**

```bash
git add dedal/server.py tests/test_api_sessions.py
git commit -m "feat(server): add /api/pick-folder endpoints for pywebview folder dialog"
```

---

## Tâche 3 — viewer.html : suppression Export Studio + intégration HUD + file picker

Les 3 modifications ci-dessous touchent toutes l'integration layer (IIFE en bas de `viewer.html`).

**Fichiers :**
- Modifier : `web/viewer.html`

> **Note IIFE :** Tout le code ci-dessous est à l'intérieur de `(function() { 'use strict'; ... })()`. Ne pas sortir les fonctions de cet IIFE. Ne pas accéder à `gPanels` ou `gCharts` depuis ce bloc — utiliser les fonctions exportées via `window.fn = fn`.

### 3a — Supprimer l'injection du bouton "Export Studio"

- [ ] **Étape 1 : Supprimer le bloc `exportBtn`**

Trouver et supprimer entièrement ce bloc dans l'integration layer (environ ligne 11629) :

```javascript
  // ── Export pack button (only useful when a session is open) ───────────
  if (LID) {
    const exportBtn = document.createElement('button');
    exportBtn.id = 'ds-export-btn';
    exportBtn.textContent = '⬆ Export Studio';
    exportBtn.onclick = dsExportPack;
    if (hdrStats) hdrStats.appendChild(exportBtn);
    else document.body.appendChild(exportBtn);
  }
```

### 3b — Refactoriser `dsExportPack` → `dsExportPackAsync`

- [ ] **Étape 2 : Remplacer `dsExportPack` par la version Promise + wrapper**

Trouver la fonction `dsExportPack()` (environ ligne 11907) et la remplacer par :

```javascript
  function dsExportPackAsync() {
    return new Promise(function(resolve, reject) {
      if (typeof flightData === 'undefined' || !flightData.length) {
        reject(new Error('Aucune donnée — chargez un log d\'abord'));
        return;
      }

      var dur = (flightData[flightData.length-1].timestamp_us - flightData[0].timestamp_us) / 1e6;
      var maxAlt = 0, maxSpd = 0, armedUs = 0, totalDist = 0;
      var vbatMin = Infinity, vbatMax = -Infinity;
      var prevLat = null, prevLon = null, prevArmed = false, prevTs = null;
      for (var i = 0; i < flightData.length; i++) {
        var r = flightData[i];
        var alt = +r.gps_alt_m || 0;
        var spd = +r.gps_speed_ms || 0;
        var vb  = +r.vbat_V || 0;
        if (alt > maxAlt) maxAlt = alt;
        if (spd > maxSpd) maxSpd = spd;
        if (vb > 0 && vb < vbatMin) vbatMin = vb;
        if (vb > vbatMax) vbatMax = vb;
        var armed = r.armed === 1 || r.armed === '1';
        if (armed && prevTs !== null) armedUs += r.timestamp_us - prevTs;
        if (r.gps_valid && r.gps_lat && prevLat !== null) {
          var dLat = (r.gps_lat - prevLat) * Math.PI / 180;
          var dLon = (r.gps_lon - prevLon) * Math.PI / 180;
          var a = Math.sin(dLat/2)*Math.sin(dLat/2) +
                  Math.cos(prevLat*Math.PI/180)*Math.cos(r.gps_lat*Math.PI/180)*
                  Math.sin(dLon/2)*Math.sin(dLon/2);
          totalDist += 6371000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        }
        if (r.gps_valid && r.gps_lat) { prevLat = +r.gps_lat; prevLon = +r.gps_lon; }
        prevArmed = armed;
        prevTs = r.timestamp_us;
      }

      var ekf = (typeof ekfData !== 'undefined' && ekfData.length === flightData.length)
                ? ekfData : null;
      var frames = [];
      for (var j = 0; j < flightData.length; j++) {
        var fd = flightData[j];
        var ef = ekf ? ekf[j] : null;
        frames.push({
          t_us:   fd.timestamp_us,
          armed:  fd.armed === 1 || fd.armed === '1' ? 1 : 0,
          fm:     +(fd.flight_mode || 0),
          roll:   +(fd.roll_IMU  || 0),
          pitch:  +(fd.pitch_IMU || 0),
          yaw:    +(fd.yaw_IMU   || 0),
          lat:    +(fd.gps_lat   || 0),
          lon:    +(fd.gps_lon   || 0),
          alt_m:  +(fd.gps_alt_m || 0),
          spd_ms: +(fd.gps_speed_ms || 0),
          sats:   +(fd.gps_sats  || 0),
          gps_ok: fd.gps_valid === 1 || fd.gps_valid === '1' ? 1 : 0,
          m1:     +(fd.m1_PWM    || 0),
          m3:     +(fd.m3_PWM    || 0),
          vbat:   +(fd.vbat_V    || 0),
          Vfwd:   ef ? +ef.Vfwd.toFixed(3) : 0,
          Vlat:   ef ? +ef.Vlat.toFixed(3) : 0,
          Vz:     ef ? +ef.Vz.toFixed(3)   : 0,
          Vh:     ef ? +ef.Vh.toFixed(3)   : 0,
        });
      }

      var pack = {
        version:     1,
        exported_at: new Date().toISOString(),
        lid:         LID,
        meta: {
          duration_s:   Math.round(dur * 10) / 10,
          max_alt_m:    Math.round(maxAlt * 10) / 10,
          max_speed_ms: Math.round(maxSpd * 10) / 10,
          armed_s:      Math.round(armedUs / 1e4) / 100,
          total_dist_m: Math.round(totalDist),
          vbat_min_v:   vbatMin === Infinity ? null : Math.round(vbatMin * 100) / 100,
          vbat_max_v:   vbatMax < 0 ? null : Math.round(vbatMax * 100) / 100,
        },
        frames: frames,
      };

      fetch('/api/sessions/' + LID + '/pack', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(pack),
      })
      .then(function(r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function(d) {
        if (typeof showToast === 'function') showToast('Flight pack exporté — ' + d.frames + ' frames', 'ok');
        resolve(d);
      })
      .catch(function(err) {
        reject(err);
      });
    });
  }

  function dsExportPack() {
    dsExportPackAsync().catch(function(err) {
      if (typeof showToast === 'function') showToast('Erreur export : ' + err.message, 'warn');
    });
  }
```

### 3c — Modifier le handler de lancement HUD pour séquencer pack → HUD

- [ ] **Étape 3 : Remplacer le handler `ds-hud-modal-launch`**

Trouver le listener sur `ds-hud-modal-launch` (environ ligne 11688) et le remplacer par :

```javascript
  document.getElementById('ds-hud-modal-launch').addEventListener('click', function() {
    hudModalEl.classList.remove('open');
    var res = (document.getElementById('ds-hud-res').value || '1920x1080').split('x');
    var tStartVal = parseFloat(document.getElementById('ds-hud-tstart').value);
    var tEndVal   = parseFloat(document.getElementById('ds-hud-tend').value);
    var opts = {
      fps:         parseInt(document.getElementById('ds-hud-fps').value, 10) || 25,
      width:       parseInt(res[0], 10) || 1920,
      height:      parseInt(res[1], 10) || 1080,
      t_start_s:   isNaN(tStartVal) ? 0 : tStartVal,
      t_end_s:     isNaN(tEndVal)   ? null : tEndVal,
      output_path: document.getElementById('ds-hud-outpath').value.trim() || null,
    };
    var hudBtn = document.getElementById('ds-hud-btn');
    if (hudBtn && hudBtn.classList.contains('busy')) return;
    if (hudBtn) { hudBtn.classList.add('busy'); hudBtn.textContent = '⬆ Export pack…'; }
    dsExportPackAsync().then(function() {
      dsGenerateHUD(opts);
    }).catch(function(err) {
      if (hudBtn) {
        hudBtn.classList.remove('busy');
        hudBtn.classList.add('err');
        hudBtn.textContent = '✕ Erreur pack';
        setTimeout(function() {
          hudBtn.classList.remove('err');
          hudBtn.textContent = '🎬 Générer HUD';
        }, 3000);
      }
      if (typeof showToast === 'function') showToast('Erreur export pack : ' + err.message, 'warn');
    });
  });
```

### 3d — Ajouter le file picker pywebview dans la modale HUD

- [ ] **Étape 4 : Ajouter la vérification disponibilité et le bouton Parcourir**

Après `document.body.appendChild(hudModalEl);` (environ ligne 11681), ajouter :

```javascript
  // ── File picker for HUD output path (pywebview only) ──────────────────
  fetch('/api/pick-folder/available')
    .then(function(r) { return r.json(); })
    .then(function(info) {
      if (!info.available) return;
      var outpathInput = document.getElementById('ds-hud-outpath');
      if (!outpathInput) return;
      outpathInput.style.display = 'none';
      var pathDisplay = document.createElement('span');
      pathDisplay.id = 'ds-hud-outpath-display';
      pathDisplay.style.cssText = 'color:var(--dim);font-size:11px;font-family:var(--font-mono);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;';
      pathDisplay.textContent = 'défaut : hud_output/ dans la session';
      var browseBtn = document.createElement('button');
      browseBtn.textContent = '📁 Parcourir';
      browseBtn.className = 'btn';
      browseBtn.style.cssText = 'padding:4px 10px;font-size:11px;flex-shrink:0;';
      browseBtn.onclick = function() {
        fetch('/api/pick-folder')
          .then(function(r) { return r.json(); })
          .then(function(res) {
            if (res.path) {
              outpathInput.value = res.path;
              pathDisplay.textContent = res.path;
            }
          });
      };
      var row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:8px;margin-top:4px;';
      row.appendChild(pathDisplay);
      row.appendChild(browseBtn);
      outpathInput.parentNode.appendChild(row);
    });
```

- [ ] **Étape 5 : Commit**

```bash
git add web/viewer.html
git commit -m "feat(viewer): integrate pack export into HUD workflow, add file picker"
```

---

## Tâche 4 — viewer.html : modale export CSV

**Fichiers :**
- Modifier : `web/viewer.html`

La modale est créée en dehors de l'IIFE (script global), comme `exportCSV()` et `exportPIDReport()`.

- [ ] **Étape 1 : Modifier l'attribut `onclick` du bouton CSV**

Trouver (environ ligne 1330) :

```html
      <button class="btn" onclick="exportCSV()" title="Télécharger les données filtrées" style="padding:4px 10px;font-size:10px;opacity:0.7;" id="btn-export-csv">⬇ CSV</button>
```

Remplacer par :

```html
      <button class="btn" onclick="openCSVExportModal()" title="Exporter les données filtrées" style="padding:4px 10px;font-size:10px;opacity:0.7;" id="btn-export-csv">⬇ CSV</button>
```

- [ ] **Étape 2 : Remplacer `exportCSV()` par `openCSVExportModal()` + logique modale**

Trouver la fonction `exportCSV()` (environ ligne 5431) et la remplacer par :

```javascript
// ── Modale export CSV ─────────────────────────────────────────────────────
var _csvModal = null;

function _buildCSVModal() {
  var overlay = document.createElement('div');
  overlay.id = 'ds-csv-modal-overlay';
  overlay.style.cssText = [
    'display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);',
    'z-index:9000;align-items:center;justify-content:center;',
  ].join('');
  overlay.innerHTML = [
    '<div id="ds-csv-modal" style="',
      'background:#0e1218;border:1px solid #2a2a35;border-radius:6px;',
      'padding:20px 24px;min-width:360px;max-width:520px;width:90vw;',
      'max-height:80vh;overflow-y:auto;font-family:var(--font-hud);',
    '">',
    '  <div style="font-size:13px;letter-spacing:2px;color:var(--accent);margin-bottom:14px;">EXPORT CSV</div>',

    '  <div class="ds-hud-field">',
    '    <label style="font-size:10px;letter-spacing:1px;color:var(--dim);">PLAGE TEMPORELLE</label>',
    '    <div style="display:flex;flex-direction:column;gap:6px;margin-top:6px;">',
    '      <label style="font-size:11px;cursor:pointer;"><input type="radio" name="ds-csv-range" value="view" checked> Vue actuelle</label>',
    '      <label style="font-size:11px;cursor:pointer;"><input type="radio" name="ds-csv-range" value="all"> Tout le vol</label>',
    '      <label style="font-size:11px;cursor:pointer;"><input type="radio" name="ds-csv-range" value="custom"> Personnalisée',
    '        <span id="ds-csv-custom-inputs" style="display:none;margin-left:8px;">',
    '          <input type="number" id="ds-csv-tstart" placeholder="0.0" min="0" step="0.1"',
    '            style="width:64px;background:#0a0c10;border:1px solid #333;color:var(--text);padding:2px 4px;font-family:var(--font-mono);font-size:11px;">',
    '          <span style="color:var(--dim);margin:0 4px;">→</span>',
    '          <input type="number" id="ds-csv-tend" placeholder="fin" min="0" step="0.1"',
    '            style="width:64px;background:#0a0c10;border:1px solid #333;color:var(--text);padding:2px 4px;font-family:var(--font-mono);font-size:11px;">',
    '          <span style="color:var(--dim);margin-left:4px;font-size:10px;">s</span>',
    '        </span>',
    '      </label>',
    '    </div>',
    '  </div>',

    '  <div class="ds-hud-field" style="margin-top:12px;">',
    '    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">',
    '      <label style="font-size:10px;letter-spacing:1px;color:var(--dim);flex:1;">COLONNES</label>',
    '      <button id="ds-csv-sel-all" class="btn" style="padding:2px 8px;font-size:10px;">Tout</button>',
    '      <button id="ds-csv-sel-none" class="btn" style="padding:2px 8px;font-size:10px;">Rien</button>',
    '    </div>',
    '    <div id="ds-csv-cols" style="',
    '      max-height:180px;overflow-y:auto;',
    '      display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:3px;',
    '      background:#080a0e;border:1px solid #1a1a24;border-radius:3px;padding:8px;',
    '    "></div>',
    '  </div>',

    '  <div class="ds-hud-modal-actions" style="margin-top:14px;">',
    '    <button id="ds-csv-cancel" class="btn">Annuler</button>',
    '    <button id="ds-csv-export" class="btn primary">⬇ Exporter</button>',
    '  </div>',
    '</div>',
  ].join('');
  document.body.appendChild(overlay);

  // Radio: show/hide custom inputs
  overlay.querySelectorAll('input[name="ds-csv-range"]').forEach(function(radio) {
    radio.addEventListener('change', function() {
      document.getElementById('ds-csv-custom-inputs').style.display =
        radio.value === 'custom' ? 'inline' : 'none';
    });
  });

  document.getElementById('ds-csv-sel-all').addEventListener('click', function() {
    overlay.querySelectorAll('#ds-csv-cols input[type=checkbox]').forEach(function(cb) { cb.checked = true; });
  });
  document.getElementById('ds-csv-sel-none').addEventListener('click', function() {
    overlay.querySelectorAll('#ds-csv-cols input[type=checkbox]').forEach(function(cb) { cb.checked = false; });
  });
  document.getElementById('ds-csv-cancel').addEventListener('click', function() {
    overlay.style.display = 'none';
  });
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) overlay.style.display = 'none';
  });
  document.getElementById('ds-csv-export').addEventListener('click', function() {
    var selected = overlay.querySelectorAll('#ds-csv-cols input[type=checkbox]:checked');
    if (!selected.length) {
      if (typeof showToast === 'function') showToast('Sélectionnez au moins une colonne', 'warn');
      return;
    }
    overlay.style.display = 'none';
    _doCSVExport(overlay);
  });

  return overlay;
}

function openCSVExportModal() {
  if (!flightData || !flightData.length) {
    if (typeof showToast === 'function') showToast('Aucune donnée chargée', 'warn');
    return;
  }
  if (!_csvModal) _csvModal = _buildCSVModal();

  // Populate columns
  var cells      = +(flightConfig['CELLS'] || 6);
  var baseKeys   = Object.keys(flightData[0]);
  var extraKeys  = ['time_s', 'vbat_soc_pct'].concat(activeMotors.map(function(m) { return 'm' + m + '_pct'; }));
  var allKeys    = baseKeys.concat(extraKeys);
  var colsDiv    = document.getElementById('ds-csv-cols');
  colsDiv.innerHTML = '';
  allKeys.forEach(function(k) {
    var lbl = document.createElement('label');
    lbl.style.cssText = 'font-size:10px;cursor:pointer;display:flex;align-items:center;gap:4px;color:var(--text);';
    var cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.value = k;
    cb.checked = true;
    lbl.appendChild(cb);
    lbl.appendChild(document.createTextNode(k));
    colsDiv.appendChild(lbl);
  });

  // Reset range to "view"
  var viewRadio = _csvModal.querySelector('input[value="view"]');
  if (viewRadio) { viewRadio.checked = true; document.getElementById('ds-csv-custom-inputs').style.display = 'none'; }

  _csvModal.style.display = 'flex';
}

function _doCSVExport(overlay) {
  if (!flightData || !flightData.length) return;

  var cells     = +(flightConfig['CELLS'] || 6);
  var batType   = document.getElementById('bat-type-select') ? document.getElementById('bat-type-select').value : 'lipo';
  var span      = motorPWM_max - motorPWM_min || 1;

  // Determine row range
  var rangeVal = overlay.querySelector('input[name="ds-csv-range"]:checked').value;
  var iStart, iEnd;
  if (rangeVal === 'view') {
    iStart = viewStart; iEnd = viewEnd + 1;
  } else if (rangeVal === 'all') {
    iStart = 0; iEnd = flightData.length;
  } else {
    var t0us = flightData[0].timestamp_us;
    var tsVal = parseFloat(document.getElementById('ds-csv-tstart').value);
    var teVal = parseFloat(document.getElementById('ds-csv-tend').value);
    var startUs = t0us + (isNaN(tsVal) ? 0 : tsVal) * 1e6;
    var endUs   = isNaN(teVal) ? Infinity : t0us + teVal * 1e6;
    iStart = 0;
    while (iStart < flightData.length && flightData[iStart].timestamp_us < startUs) iStart++;
    iEnd = iStart;
    while (iEnd < flightData.length && flightData[iEnd].timestamp_us <= endUs) iEnd++;
  }

  // Selected columns
  var selectedKeys = [];
  overlay.querySelectorAll('#ds-csv-cols input[type=checkbox]:checked').forEach(function(cb) {
    selectedKeys.push(cb.value);
  });
  if (!selectedKeys.length) { if (typeof showToast === 'function') showToast('Sélectionnez au moins une colonne', 'warn'); return; }

  var baseKeys  = Object.keys(flightData[0]);
  var extraKeys = ['time_s', 'vbat_soc_pct'].concat(activeMotors.map(function(m) { return 'm' + m + '_pct'; }));

  var rows = [];
  for (var i = iStart; i < iEnd; i++) {
    var r   = flightData[i];
    var t   = (r.timestamp_us / 1e6).toFixed(3);
    var soc = r.vbat_V > 0 ? voltToPercent(r.vbat_V / cells, batType).toFixed(1) : '';
    var mPcts = activeMotors.map(function(m) {
      var v = +(r['m' + m + '_PWM'] || 0);
      return v >= motorPWM_min ? Math.max(0, Math.min(100, (v - motorPWM_min) / span * 100)).toFixed(1) : '0';
    });
    var rowObj = {};
    baseKeys.forEach(function(k) { rowObj[k] = r[k]; });
    rowObj['time_s']       = t;
    rowObj['vbat_soc_pct'] = soc;
    activeMotors.forEach(function(m, idx) { rowObj['m' + m + '_pct'] = mPcts[idx]; });

    rows.push(selectedKeys.map(function(k) {
      var v = rowObj[k];
      return v === undefined ? '' : v;
    }).join(','));
  }

  var csv  = selectedKeys.join(',') + '\n' + rows.join('\n');
  var blob = new Blob([csv], { type: 'text/csv' });
  var url  = URL.createObjectURL(blob);
  var a    = document.createElement('a');
  var name = (flightConfig['CONFIG_NAME'] || 'VTOL').replace(/[^a-zA-Z0-9_]/g, '_');
  a.href = url; a.download = name + '_export.csv';
  a.click(); URL.revokeObjectURL(url);
  if (typeof showToast === 'function') showToast('⬇ CSV exporté — ' + rows.length + ' lignes, ' + selectedKeys.length + ' colonnes', 'ok');
}
```

- [ ] **Étape 3 : Vérifier que les tests Python passent toujours**

```bash
python -m pytest tests/ -v
```

Résultat attendu : tous verts (les changements JS n'affectent pas les tests Python).

- [ ] **Étape 4 : Commit**

```bash
git add web/viewer.html
git commit -m "feat(viewer): modale export CSV avec sélection colonnes et plage temporelle"
```

---

## Vérification finale

- [ ] Lancer le serveur et ouvrir le viewer avec un log réel :

```bash
source .venv/bin/activate && python app.py --browser
```

- [ ] Vérifier dans la console que l'onglet ANALYSE charge sans erreur
- [ ] Cliquer "🎬 Générer HUD" : séquence "⬆ Export pack…" → "⏳ Génération…" → "✓ HUD généré"
- [ ] Cliquer "⬇ CSV" : modale s'ouvre, checkboxes toutes cochées, plage "Vue actuelle"
  - Décocher quelques colonnes et exporter → vérifier le fichier téléchargé
  - Changer la plage sur "Personnalisée" 10s→30s → vérifier les lignes
- [ ] En mode pywebview (`python app.py`) : bouton "📁 Parcourir" visible dans la modale HUD
- [ ] En mode navigateur : champ texte visible dans la modale HUD
- [ ] Vérifier que le bouton "⬆ Export Studio" n'existe plus dans le header
