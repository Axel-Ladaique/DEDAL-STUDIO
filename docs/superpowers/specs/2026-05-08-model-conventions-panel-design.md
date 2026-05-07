# Design Spec — Panneau flottant "MODÈLE"

**Date :** 2026-05-08  
**Statut :** Approuvé

---

## Objectif

Ajouter un bouton **⊹ MODÈLE** accessible depuis la page d'accueil (`index.html`) et le viewer (`viewer.html`). Ce bouton ouvre/ferme un panneau flottant affichant les conventions de référence du drone DEDAL : nomenclature des actionneurs, repères, schémas SVG, conventions angulaires.

---

## Bouton déclencheur

- **Label :** `⊹ MODÈLE`
- **Position :** à droite du logo DEDAL Studio dans la barre de titre, sur les deux pages
- **Comportement :** toggle — clic ouvre le panneau s'il est fermé, le ferme s'il est ouvert
- **Style :** cohérent avec les boutons existants (border cyan tenu, background rgba cyan faible, font monospace, 10px)
- **État :** indépendant entre les deux pages (pas de persistance cross-page)

### Placement dans `index.html`

Le `<div class="topbar">` contient actuellement uniquement le logo. Le bouton est ajouté directement après le `<div class="logo">`.

### Placement dans `viewer.html`

Le `<header>` contient le logo (à gauche) et `<div class="header-stats">` (à droite). Le bouton est inséré **directement dans `<header>`, entre le `<div class="logo">` et le `<div class="header-stats">`**, de façon à ne pas bousculer les stat-pills.

---

## Panneau flottant

### Dimensions et position initiale

| Propriété | Valeur |
|---|---|
| Largeur initiale | `900px` |
| Hauteur initiale | `580px` |
| Largeur min | `500px` |
| Hauteur min | `300px` |
| Position à l'ouverture | centré horizontalement, `top: 60px` |
| z-index | `9000` (au-dessus de tout le contenu existant) |

### Comportements

- **Drag :** la barre de titre est une poignée de déplacement (mousedown → mousemove sur `document`)
- **Resize :** CSS `resize: both; overflow: hidden` — poignée native en bas à droite
- **Fermeture :** bouton ✕ dans la barre de titre OU re-clic sur le bouton MODÈLE
- **Persistance de position :** la position et la taille sont conservées pendant la session (le panneau ne se recentre pas à chaque ouverture)

### Structure DOM

```
div#conv-panel
  div.conv-titlebar          ← drag handle
    div.conv-titlebar-left
      div.conv-titlebar-icon  (✈)
      h2                      (MODÈLE)
      span                    (CONVENTIONS DE RÉFÉRENCE)
    button.conv-close         (✕)
  div.conv-columns
    div.conv-left             ← colonne schémas (52%)
      div.conv-schema-viewport  ← scroll vertical
        div.conv-schema-block   (vue dessus)
          div.conv-schema-label
          svg (inline)
        div.conv-schema-block   (vue côté)
          div.conv-schema-label
          svg (inline)
    div.conv-right            ← colonne info (flex:1, scroll vertical)
      sections...
```

---

## Contenu du panneau

### Colonne gauche — Schémas SVG

Deux schémas empilés verticalement, scrollable indépendamment :

1. **VUE DE DESSUS** — `schema_vue_dessus.svg` (viewBox 0 0 680 780)  
   Montre : M1/M3, microtilts S1/S2, ailerons S3/S4, tilt S6, empennage S5/S7, repère xy
   
2. **VUE DE CÔTÉ · CONVENTION α** — `schema_vue_cote_alpha.svg` (viewBox 0 0 680 400)  
   Montre : fuselage, boom, T-tail S5/S7, convention α (cabré/piqué), repère xz

Les SVGs sont intégrés **inline** dans le JS (template literal). Fond `#f5f3ec` (les SVGs ont été conçus sur fond clair).

### Colonne droite — Informations textuelles

Sections titrées, scrollable indépendamment :

| Section | Contenu |
|---|---|
| NOMENCLATURE | Table Réf / Désignation (M1, M3, S1–S7) |
| MICROTILTS S1 / S2 | Table position physique / angles PWM + note miroir + warning ratio 1:4 |
| REPÈRES | Table vue dessus (xy) / vue côté (xz) |
| CONVENTION ANGLE α | Table signe / attitude + warning convention non-standard |
| SERVOS (7 actionneurs) | Table complète Servo / Désignation / Fonction |

---

## Implémentation

### Fichier unique partagé

Tout le code (DOM, styles, SVGs, logique drag) est dans **`web/assets/conventions-panel.js`**.

Les deux pages l'incluent :
```html
<script src="/assets/conventions-panel.js"></script>
```

Et appellent dans leur script d'initialisation :
```js
initConventionsPanel();
```

`initConventionsPanel()` :
1. Injecte un `<style>` dans `<head>` avec tous les styles du panneau (scoped par `#conv-panel`, `.conv-*`)
2. Crée et append `div#conv-panel` au `<body>` (caché par défaut, `display:none`)
3. Expose `window.toggleConventionsPanel()` — alterne `display:none` ↔ `display:flex` et mémorise position/taille entre ouvertures

Le bouton MODÈLE dans chaque page appelle `window.toggleConventionsPanel()` via `onclick`.

### Styles

- Thème sombre cohérent avec DEDAL Studio : bg `#0a1018`, border `#1e3050`, accent cyan `#00d4ff`, accent vert `#00ff9d`
- Pas de dépendance à une feuille de style externe
- Scrollbars fines (4px, style webkit)

### Pas de dépendance nouvelle

Aucune bibliothèque supplémentaire. Vanilla JS + CSS natif uniquement.

---

## Fichiers modifiés / créés

| Fichier | Action |
|---|---|
| `web/assets/conventions-panel.js` | **Créer** — composant complet |
| `web/index.html` | **Modifier** — ajouter `<script>` + bouton MODÈLE dans topbar |
| `web/viewer.html` | **Modifier** — ajouter `<script>` + bouton MODÈLE dans header |

---

## Hors scope

- Persistance de l'état ouvert/fermé entre sessions (localStorage)
- Synchronisation de l'état entre les deux pages
- Zoom sur les schémas SVG
- Mode plein écran du panneau
