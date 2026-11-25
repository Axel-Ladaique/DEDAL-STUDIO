# Reprise — extension PX4 / vidéo live / synchro (branche `px4`)

Document de passation écrit le 2026-11-25 à la fin d'une discussion de cadrage.
Il sert à reprendre le travail depuis un autre poste (Windows, au travail) avec une
autre session Claude.

**État : cadrage en cours. Rien n'est conçu, rien n'est codé dans le produit.**
Le seul code de cette branche est un script de test jetable (`spikes/goggles3_probe.py`).

Lire aussi `CLAUDE.md` à la racine : il décrit DEDAL Studio tel qu'il existe aujourd'hui.

---

## 1. Ce que l'utilisateur veut

DEDAL Studio doit gérer un **deuxième appareil** : un avion du travail, sous PX4.
DEDAL (le VTOL birotor) **reste sur dRehmFlight** et doit continuer à fonctionner à
l'identique.

### Matériel du nouvel appareil

| Élément | Choix |
|---|---|
| Contrôleur de vol | Pixhawk 6X |
| Firmware | PX4 |
| Radiocommande | ELRS, récepteur XR4 (à confirmer), TX16S Mark III, Gemini activé |
| Télémétrie | Module RFD900 (modèle exact inconnu) branché en USB sur l'ordinateur |
| Vidéo FPV | DJI O4 (Pro ou Lite : inconnu) + lunettes DJI Goggles 3 |
| Caméra embarquée | GoPro Max 2 (360°, GPS et accéléromètre intégrés) |

Le pilote vole **en immersion aux lunettes**. L'écran de Studio est donc pour une
personne à la station sol, pas pour piloter.

### En vol (vérification pendant le vol)

Un écran qui mélange la vidéo de l'O4 et la télémétrie du RFD900, avec deux modes :

- **Mode télémétrie (mode de base)** : le tableau de bord de télémétrie, avec la vidéo
  dans un coin, comme une information parmi les autres.
- **Mode FPV** : la vidéo seule en plein écran, **sans** l'affichage DJI (réservé aux
  lunettes), avec un affichage à nous dessiné par-dessus à partir de la télémétrie.

Le passage de l'un à l'autre n'a pas de bouton dédié : **on met la vidéo en plein écran
pour entrer en mode FPV, on quitte le plein écran pour revenir au mode de base.**

### Hors vol (analyse des logs)

- Faire collaborer les logs avec le rush de l'O4 et avec la vidéo de la GoPro Max 2.
- Pouvoir **se déplacer dans la vidéo 360** (plusieurs angles à configurer).
- **Synchronisation automatique** des logs avec les vidéos, à la manière de Gyroflow.

---

## 2. Décisions prises

| Sujet | Décision |
|---|---|
| Deux appareils | Chaque session porte son type : dRehmFlight (CSV + CRSF, inchangé) ou PX4 (ULog + MAVLink). Vidéo, synchro et lecteur 360 sont communs. *Proposition de Claude, non contestée.* |
| Vidéo live | **Intégration native** : Studio parle directement aux lunettes. Aucune application tierce, aucun téléphone. Décision ferme de l'utilisateur (« je ne dois pas être dépendant de quelque chose d'autre »). |
| Bascule de mode | Plein écran = mode FPV ; sortie du plein écran = mode de base. |
| Plateforme | **Windows compte autant que macOS** : le poste du travail est sous Windows. La décision figée « macOS d'abord » de `CLAUDE.md` ne tient plus pour cette branche. |

## 3. Questions ouvertes (à poser à l'utilisateur, une à la fois)

1. **Station sol** : le poste utilisé pendant les vols de l'avion, c'est le Windows du
   travail uniquement, ou aussi le Mac ? Si Windows seul au début, on commence par
   Windows et on repousse la partie Mac, qui est la plus difficile (voir §5).
2. **Contenu de l'affichage FPV** : que veut-il voir par-dessus la vidéo en mode FPV ?
   (Question posée, pas encore de réponse. La poser de façon ouverte.)
3. **Modèle d'O4** : Pro ou Lite ? Cela décide si le fichier vidéo contient les données
   gyro nécessaires à la synchro automatique (Pro : oui ; Lite : à vérifier).
4. **Modèle exact du RFD900** et débit série.
5. Le RFD900 transporte-t-il du MAVLink standard de PX4 ? (Hypothèse de travail : oui.)

---

## 4. Les chantiers

Ce sont des projets distincts. À concevoir un par un.

| # | Chantier | Faisabilité | Notes |
|---|---|---|---|
| A | Import des logs PX4 (`.ulg`) | Bonne | Tout le reste hors vol en dépend. Le viewer HTML est construit autour des colonnes dRehmFlight : il faut décider comment y faire entrer les données PX4. |
| B | Télémétrie live MAVLink (RFD900) | Bonne | Remplace le lecteur CRSF pour l'appareil PX4. La page live et le flux SSE existants restent le modèle. |
| C | Vidéo live des Goggles 3 + les deux modes | Faisable, non officiel | Voir §5. Simple sous Windows, difficile sous macOS. |
| D | Synchro automatique logs ↔ vidéos | Bonne | Heure GPS pour le calage grossier, corrélation des gyros pour le calage fin. Même méthode pour l'O4 et la GoPro. C'est l'étape 8 de la roadmap. |
| E | Lecteur 360 (GoPro Max 2) | Faisable mais lourd | Convertir les `.360` en équirectangulaire, afficher sur une sphère WebGL, probablement via un proxy allégé. |
| F | Portage Windows de Studio | À évaluer | Studio n'a jamais tourné sous Windows : chemins de configuration (`~/.config/...`), ffmpeg, fenêtre native (PyWebView utilise WebView2 sous Windows). |

Ordre suggéré par Claude, non validé : C (test matériel d'abord, car c'est le seul
point incertain), puis F et B pour avoir l'écran en vol, puis A, D, E.

**Correction d'une idée de départ** : l'O4 n'est pas synchronisé avec le contrôleur de
vol. Au mieux il démarre l'enregistrement à l'armement. La synchro passera par le gyro
embarqué dans le fichier vidéo.

---

## 5. Vidéo live des Goggles 3 — ce qu'on sait

Rien de ce qui suit n'a été testé sur le matériel de l'utilisateur. Tout vient de la
lecture de projets open source, en novembre 2026.

### Faits

- Les Goggles 3 n'ont pas de sortie HDMI. Le partage officiel passe par un téléphone
  (application DJI Fly). L'utilisateur ne veut pas de téléphone.
- Un réglage des lunettes ouvre une autre voie : **Paramètres → À propos → « OTG Wired
  Connection to Computer »**. À activer câble débranché.
- Dans ce mode, les lunettes sont un périphérique USB `2CA3:0020` qui se présente comme
  une **carte réseau USB (RNDIS)**. Lunettes : `192.168.60.2`. Ordinateur : `192.168.60.1`.
- Un petit message UDP vers le port `9003` démarre le flux. La vidéo arrive en UDP,
  découpée en morceaux à réassembler : **H.264 Annex-B, 1920×1080**, 30 à 60 images
  par seconde selon le mode d'encodage des lunettes. Pas de son.
- Ce protocole n'est **pas officiel**. Une mise à jour du firmware DJI peut le casser.
- Par défaut, l'affichage DJI est incrusté dans l'image envoyée. Il se coupe dans les
  lunettes : Paramètres → Caméra → Réglages caméra avancés → « Camera View Recording »
  désactivé. **À vérifier : que cela ne le coupe pas dans les lunettes du pilote.**
- Obtenir une image clé peut demander de couper puis relancer le partage dans les
  lunettes. Un identifiant de session aléatoire par connexion est nécessaire.

### Windows et macOS ne se ressemblent pas

| | Windows | macOS |
|---|---|---|
| Pilote RNDIS du système | Fonctionne (pilote Microsoft d'origine). **Ne pas le remplacer par WinUSB / Zadig.** | Ne monte pas le lien (`media inactive`, pas de DHCP). |
| Travail pour Studio | De simples sockets UDP. Aucun code USB. | Refaire un pilote RNDIS en espace utilisateur par-dessus l'USB, plus ARP, IP et UDP construits à la main. |
| Droits administrateur | Une fois, pour donner l'adresse `192.168.60.1/24` à la carte. | Incertain : un projet dit que réclamer les interfaces USB exige root ; un autre passe par IOKit sans rien demander dans son code. |

### Projets de référence

| Projet | Licence | Utilité |
|---|---|---|
| [knpuma/goggle-3-liveview](https://github.com/knpuma/goggle-3-liveview) | MIT | Référence réutilisable. Protocole UDP (`Windows/Goggles3.Core/LiveProtocol.cs`) et pilote RNDIS macOS via IOKit (`Sources/GogglesRNDISProbe/main.c`). Le script de test en est un portage Python. |
| [Kristian-Buriasco/gogglecast](https://github.com/Kristian-Buriasco/gogglecast) (GogglesView) | GPL-3.0 | Meilleure documentation du protocole (`docs/design.md`). **Lire, ne pas copier le code** (GPL). |
| [wllm-rbnt/third-eye](https://github.com/wllm-rbnt/third-eye) | MIT | Autre voie (se faire passer pour un téléphone, sur Raspberry Pi). Hors sujet pour Studio, utile pour comprendre. |
| [Cosmostreamer GD1](https://www.getfpv.com/cosmostreamer-gd1-box-for-dji-hd-output.html) | Commercial, ~320 $ | Plan B matériel (HDMI + RTSP). Écarté tant que la voie native marche. |

Retours d'utilisateurs : quasi inexistants. Ces projets ont deux à trois mois, peu
d'étoiles, presque aucun ticket. **Aucune mesure indépendante du retard n'existe.**
Un développeur annonce environ 0,2 s ; c'est son propre chiffre.

### Point technique à trancher à la conception

La fenêtre de Studio (WebKit sur macOS, WebView2 sous Windows) ne lit pas un flux
H.264 brut. Il faudra un relais côté serveur. Pistes évoquées, aucune choisie :
envoyer les unités H.264 par WebSocket et décoder avec WebCodecs (pas de réencodage,
retard minimal), ou réencoder en MJPEG avec ffmpeg (simple, plus lourd). HLS est exclu
(plusieurs secondes de retard).

---

## 6. Le test à faire en premier

Le script `spikes/goggles3_probe.py` répond à une seule question : ce poste reçoit-il
la vidéo des lunettes par USB, et avec quelle qualité ? Bibliothèque standard
uniquement, Python 3.9 ou plus récent. Il ne modifie rien dans Studio.

### Préparation

1. Lunettes allumées et liées à l'O4 **alimenté** (image visible dans les lunettes).
2. Câble débranché : activer « OTG Wired Connection to Computer ». Rebrancher.
3. Lancer le partage de l'image (live view sharing) dans les lunettes.
4. Câble USB-C qui transporte les données.

### Lancement

```bash
python spikes/goggles3_probe.py --selftest
```

```bash
python spikes/goggles3_probe.py
```

```bash
python spikes/goggles3_probe.py --seconds 600 --play
```

- `--selftest` vérifie le code du protocole sans matériel.
- Sans option : capture de 20 secondes, écrit `goggles3_capture.h264` et
  `goggles3_report.txt`.
- `--play` affiche l'image en direct si `ffplay` est installé.

Sous Windows, si le script dit que l'adresse `192.168.60.1` manque, il affiche la
commande PowerShell (administrateur) à lancer une fois, et celle pour l'annuler.
Si le pare-feu Windows demande une autorisation pour Python, l'accepter pour les
réseaux privés.

Sous macOS, la capture **échouera** (pilote RNDIS du système) : c'est attendu. Le
script indique tout de même si les lunettes sont vues sur l'USB.

### À noter pendant le test

1. **Retard** : filmer un chronomètre avec le drone, comparer l'écran de l'ordinateur
   au chronomètre réel (une photo des deux suffit).
2. **Stabilité** : dix minutes sans coupure ni saccade ? (Le rapport donne le plus long
   trou et le débit minimal.)
3. **Enregistrement dans les lunettes** : continue-t-il pendant le partage ?
4. **Partage** : faut-il le relancer à la main à chaque branchement ?
5. **Affichage DJI** : le couper pour le flux le coupe-t-il aussi dans les lunettes ?
6. **Modèle d'O4** : Pro ou Lite.

Coller ensuite le contenu de `goggles3_report.txt` dans la conversation.

---

## 7. Comment reprendre

1. Lire ce fichier et `CLAUDE.md`.
2. Demander à l'utilisateur les résultats du test (§6) et poser les questions du §3,
   une à la fois.
3. Ne rien construire avant d'avoir un document de conception approuvé par
   l'utilisateur, chantier par chantier. Les documents de conception vont dans
   `docs/superpowers/specs/`.
4. L'utilisateur préfère des réponses courtes et parle parfois par dictée vocale : les
   noms propres peuvent arriver déformés (« Dédale », « Dreamflight » pour dRehmFlight,
   « Giroflow » pour Gyroflow).
5. Le script de test est jetable. Le code produit de la vidéo live sera réécrit
   proprement, avec des tests, une fois la conception approuvée.
