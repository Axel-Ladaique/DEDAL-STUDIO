/* Floating "MODÈLE" conventions panel — shared by index.html and viewer.html */
(function () {
  'use strict';

  /* ── Styles ─────────────────────────────────────────────────────────────── */
  const CSS = `
#conv-panel {
  position: fixed;
  top: 60px; left: 50%; transform: translateX(-50%);
  width: 900px; height: 580px;
  min-width: 500px; min-height: 300px;
  background: #0a1018;
  border: 1px solid #1e3050;
  border-radius: 8px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.7), 0 0 0 1px rgba(0,212,255,0.07);
  display: none;
  flex-direction: column;
  resize: both; overflow: hidden;
  z-index: 9000;
  font-family: 'JetBrains Mono','Fira Mono','Courier New',monospace;
  font-size: 11px; color: #c8d8e8;
}
.conv-titlebar {
  background: #0d1825; border-bottom: 1px solid #1e3050;
  padding: 7px 14px; display: flex; align-items: center;
  justify-content: space-between; cursor: move;
  user-select: none; flex-shrink: 0;
}
.conv-titlebar-left { display: flex; align-items: center; gap: 10px; }
.conv-titlebar-icon {
  width: 22px; height: 22px; border: 1px solid rgba(0,255,157,0.4);
  border-radius: 3px; display: flex; align-items: center;
  justify-content: center; font-size: 11px; color: #00ff9d;
}
.conv-title { font-size: 11px; font-weight: 600; letter-spacing: 3px; color: #00ff9d; margin: 0; }
.conv-subtitle { font-size: 9px; letter-spacing: 1.5px; color: #4a6070; }
.conv-close {
  width: 20px; height: 20px; border: 1px solid #1e3050; border-radius: 3px;
  background: transparent; color: #4a6070; font-size: 11px; line-height: 1;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  font-family: inherit; transition: border-color .15s, color .15s;
}
.conv-close:hover { border-color: #ff4d4d; color: #ff4d4d; }
.conv-columns { flex: 1; display: flex; overflow: hidden; min-height: 0; }
.conv-left {
  width: 52%; flex-shrink: 0; display: flex; flex-direction: column;
  border-right: 1px solid #1e3050; background: #080d12; min-width: 0;
}
.conv-schema-viewport {
  flex: 1; overflow-y: auto; overflow-x: hidden;
  padding: 12px; display: flex; flex-direction: column; gap: 14px;
}
.conv-schema-viewport::-webkit-scrollbar { width: 4px; }
.conv-schema-viewport::-webkit-scrollbar-thumb { background: #1e3050; border-radius: 2px; }
.conv-schema-block { width: 100%; }
.conv-schema-label {
  font-size: 9px; letter-spacing: 2px; color: #4a6070;
  padding-bottom: 5px; border-bottom: 1px solid #1e3050; margin-bottom: 6px;
}
.conv-schema-block svg { width: 100%; height: auto; background: #f5f3ec; border-radius: 6px; padding: 8px; display: block; }
.conv-right {
  flex: 1; overflow-y: auto; padding: 18px 20px; min-width: 0;
}
.conv-right::-webkit-scrollbar { width: 4px; }
.conv-right::-webkit-scrollbar-thumb { background: #1e3050; border-radius: 2px; }
.conv-section { margin-bottom: 26px; }
.conv-section-title {
  font-size: 9px; letter-spacing: 2.5px; color: #00d4ff;
  border-bottom: 1px solid #1e3050; padding-bottom: 5px; margin-bottom: 12px;
}
.conv-section-title::before { content: '▸ '; opacity: 0.6; }
.conv-table { width: 100%; border-collapse: collapse; font-size: 10.5px; margin-bottom: 8px; }
.conv-table th {
  background: #0d1825; color: #4a8090; padding: 5px 9px;
  text-align: left; font-weight: 500; letter-spacing: 1px;
  border-bottom: 1px solid #1e3050; font-size: 9px;
}
.conv-table td { padding: 5px 9px; border-bottom: 1px solid #0f1a25; color: #9ab0c0; vertical-align: top; }
.conv-table tr:last-child td { border-bottom: none; }
.conv-table tr:hover td { background: rgba(0,212,255,0.03); }
.conv-ref { color: #00d4ff; font-weight: 600; }
.conv-warn {
  background: rgba(255,179,64,0.07); border: 1px solid rgba(255,179,64,0.2);
  border-radius: 4px; padding: 7px 10px; font-size: 9.5px;
  color: #b88020; margin: 8px 0; line-height: 1.6;
}
.conv-info {
  background: rgba(0,212,255,0.05); border: 1px solid rgba(0,212,255,0.12);
  border-radius: 4px; padding: 7px 10px; font-size: 9.5px;
  color: #5a8090; margin: 8px 0; line-height: 1.6;
}
.conv-code { color: #a0c8e0; font-family: inherit; }
`;

  /* ── SVG vue de dessus (marker IDs: conv-da, conv-dasm) ─────────────────── */
  const SVG_DESSUS = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 780" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <defs>
    <marker id="conv-da" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker>
    <marker id="conv-dasm" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker>
  </defs>
  <text x="340" y="24" text-anchor="middle" font-size="14" font-weight="500" fill="#2C2C2A">Vue de dessus</text>
  <line x1="40" y1="60" x2="40" y2="100" stroke="#5F5E5A" stroke-width="0.8" marker-end="url(#conv-da)"/>
  <line x1="40" y1="60" x2="76" y2="60" stroke="#5F5E5A" stroke-width="0.8" marker-end="url(#conv-da)"/>
  <text x="82" y="64" font-size="12" fill="#5F5E5A">y</text>
  <text x="40" y="115" text-anchor="middle" font-size="12" fill="#5F5E5A">x</text>
  <text x="640" y="60" text-anchor="end" font-size="12" fill="#5F5E5A">avant</text>
  <text x="640" y="755" text-anchor="end" font-size="12" fill="#5F5E5A">arrière</text>
  <path d="M 340 60 C 308 100, 300 150, 300 200 L 300 220 L 380 220 L 380 200 C 380 150, 372 100, 340 60 Z" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
  <rect x="109" y="210" width="462" height="146" rx="4" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
  <ellipse cx="340" cy="285" rx="36" ry="80" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
  <rect x="335" y="356" width="10" height="342" fill="#5F5E5A" opacity="0.85"/>
  <rect x="233" y="700" width="214" height="36" rx="2" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
  <rect x="333" y="690" width="14" height="56" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
  <circle cx="109" cy="283" r="22" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.8"/>
  <text x="109" y="287" text-anchor="middle" font-size="14" font-weight="500" fill="#0C447C">M3</text>
  <circle cx="571" cy="283" r="22" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.8"/>
  <text x="571" y="287" text-anchor="middle" font-size="14" font-weight="500" fill="#0C447C">M1</text>
  <rect x="35" y="178" width="148" height="216" rx="6" fill="none" stroke="#185FA5" stroke-width="0.8" stroke-dasharray="4 3" opacity="0.6"/>
  <text x="109" y="172" text-anchor="middle" font-size="12" font-weight="500" fill="#0C447C">microtilt S1 (M3)</text>
  <line x1="109" y1="261" x2="109" y2="200" stroke="#185FA5" stroke-width="2" marker-end="url(#conv-dasm)"/>
  <rect x="62" y="180" width="94" height="18" rx="3" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
  <text x="109" y="193" text-anchor="middle" font-size="11" font-weight="500" fill="#0C447C">S1 = 0° (avant)</text>
  <line x1="109" y1="305" x2="109" y2="366" stroke="#185FA5" stroke-width="2" marker-end="url(#conv-dasm)"/>
  <rect x="58" y="370" width="102" height="18" rx="3" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
  <text x="109" y="383" text-anchor="middle" font-size="11" font-weight="500" fill="#0C447C">S1 = 180° (arrière)</text>
  <line x1="79" y1="283" x2="86" y2="283" stroke="#185FA5" stroke-width="1"/>
  <text x="74" y="280" text-anchor="end" font-size="10" fill="#185FA5">90°</text>
  <text x="74" y="293" text-anchor="end" font-size="10" fill="#185FA5">neutre</text>
  <rect x="497" y="178" width="148" height="216" rx="6" fill="none" stroke="#185FA5" stroke-width="0.8" stroke-dasharray="4 3" opacity="0.6"/>
  <text x="571" y="172" text-anchor="middle" font-size="12" font-weight="500" fill="#0C447C">microtilt S2 (M1)</text>
  <line x1="571" y1="261" x2="571" y2="200" stroke="#185FA5" stroke-width="2" marker-end="url(#conv-dasm)"/>
  <rect x="520" y="180" width="102" height="18" rx="3" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
  <text x="571" y="193" text-anchor="middle" font-size="11" font-weight="500" fill="#0C447C">S2 = 180° (avant)</text>
  <line x1="571" y1="305" x2="571" y2="366" stroke="#185FA5" stroke-width="2" marker-end="url(#conv-dasm)"/>
  <rect x="524" y="370" width="94" height="18" rx="3" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
  <text x="571" y="383" text-anchor="middle" font-size="11" font-weight="500" fill="#0C447C">S2 = 0° (arrière)</text>
  <line x1="601" y1="283" x2="594" y2="283" stroke="#185FA5" stroke-width="1"/>
  <text x="606" y="280" text-anchor="start" font-size="10" fill="#185FA5">90°</text>
  <text x="606" y="293" text-anchor="start" font-size="10" fill="#185FA5">neutre</text>
  <circle cx="340" cy="240" r="14" fill="#FAECE7" stroke="#993C1D" stroke-width="0.8"/>
  <text x="340" y="244" text-anchor="middle" font-size="12" font-weight="500" fill="#712B13">S6</text>
  <line x1="354" y1="234" x2="430" y2="135" stroke="#888780" stroke-width="0.5" stroke-dasharray="3 3"/>
  <circle cx="354" cy="234" r="2" fill="#5F5E5A"/>
  <rect x="427" y="118" width="195" height="32" rx="4" fill="#FAECE7" stroke="#993C1D" stroke-width="0.5"/>
  <text x="524" y="132" text-anchor="middle" font-size="12" font-weight="500" fill="#712B13">S6 — tilt 90°</text>
  <text x="524" y="145" text-anchor="middle" font-size="11" fill="#993C1D">basculement HOVER ↔ PLANE</text>
  <rect x="131" y="335" width="160" height="20" rx="2" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.5"/>
  <text x="211" y="349" text-anchor="middle" font-size="13" font-weight="500" fill="#3C3489">S3 — aileron G</text>
  <rect x="389" y="335" width="160" height="20" rx="2" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.5"/>
  <text x="469" y="349" text-anchor="middle" font-size="13" font-weight="500" fill="#3C3489">S4 — aileron D</text>
  <line x1="345" y1="500" x2="445" y2="500" stroke="#888780" stroke-width="0.5" stroke-dasharray="3 3"/>
  <text x="450" y="497" text-anchor="start" font-size="11" fill="#5F5E5A">boom carbone</text>
  <text x="450" y="510" text-anchor="start" font-size="11" fill="#888780">(~700 mm)</text>
  <text x="340" y="724" text-anchor="middle" font-size="13" font-weight="500" fill="#3C3489">S5</text>
  <line x1="447" y1="718" x2="500" y2="704" stroke="#888780" stroke-width="0.5" stroke-dasharray="3 3"/>
  <text x="505" y="708" text-anchor="start" font-size="11" fill="#5F5E5A">S5 — profondeur</text>
  <line x1="347" y1="697" x2="500" y2="675" stroke="#888780" stroke-width="0.5" stroke-dasharray="3 3"/>
  <text x="505" y="679" text-anchor="start" font-size="11" fill="#5F5E5A">S7 — dérive</text>
</svg>`;

  /* ── SVG vue de côté (marker ID: conv-ca) ───────────────────────────────── */
  const SVG_COTE = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 400" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <defs>
    <marker id="conv-ca" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker>
  </defs>
  <text x="340" y="22" text-anchor="middle" font-size="14" font-weight="500" fill="#2C2C2A">Vue de côté — convention α</text>
  <g transform="translate(60,80)">
    <line x1="36" y1="40" x2="0" y2="40" stroke="#5F5E5A" stroke-width="0.8" marker-end="url(#conv-ca)"/>
    <line x1="36" y1="40" x2="36" y2="0" stroke="#5F5E5A" stroke-width="0.8" marker-end="url(#conv-ca)"/>
    <text x="-6" y="44" text-anchor="end" font-size="12" fill="#5F5E5A">x</text>
    <text x="36" y="-6" text-anchor="middle" font-size="12" fill="#5F5E5A">z</text>
  </g>
  <text x="40" y="80" font-size="12" fill="#888780">← arrière</text>
  <text x="640" y="80" text-anchor="end" font-size="12" fill="#888780">avant →</text>
  <line x1="20" y1="240" x2="660" y2="240" stroke="#888780" stroke-width="0.5" stroke-dasharray="4 4" opacity="0.5"/>
  <path d="M 620 240 Q 590 226, 550 224 L 410 224 Q 395 224, 395 232 L 395 248 Q 395 256, 410 256 L 550 256 Q 590 254, 620 240 Z" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
  <path d="M 510 224 Q 490 210, 470 224" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
  <ellipse cx="445" cy="240" rx="48" ry="6" fill="none" stroke="#185FA5" stroke-width="0.5" stroke-dasharray="3 2" opacity="0.7"/>
  <text x="445" y="278" text-anchor="middle" font-size="10" fill="#185FA5">aile (corde 200 mm)</text>
  <rect x="71" y="237" width="324" height="6" fill="#5F5E5A" opacity="0.85"/>
  <line x1="235" y1="246" x2="235" y2="278" stroke="#888780" stroke-width="0.5" stroke-dasharray="3 3"/>
  <text x="235" y="290" text-anchor="middle" font-size="11" fill="#5F5E5A">boom carbone (~700 mm)</text>
  <path d="M 71 240 L 60 175 L 86 175 L 86 240 Z" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.6"/>
  <line x1="40" y1="172" x2="100" y2="172" stroke="#534AB7" stroke-width="3.5"/>
  <line x1="73" y1="200" x2="160" y2="170" stroke="#888780" stroke-width="0.5" stroke-dasharray="3 3"/>
  <rect x="160" y="158" width="120" height="20" rx="3" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.5"/>
  <text x="220" y="172" text-anchor="middle" font-size="11" font-weight="500" fill="#3C3489">S7 — dérive</text>
  <line x1="70" y1="172" x2="160" y2="118" stroke="#888780" stroke-width="0.5" stroke-dasharray="3 3"/>
  <rect x="160" y="106" width="155" height="20" rx="3" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.5"/>
  <text x="237" y="120" text-anchor="middle" font-size="11" font-weight="500" fill="#3C3489">S5 — profondeur (T-tail)</text>
  <circle cx="500" cy="240" r="2" fill="#5F5E5A"/>
  <line x1="500" y1="240" x2="630" y2="190" stroke="#534AB7" stroke-width="1.5"/>
  <polygon points="630,190 621,190 626,198" fill="#534AB7"/>
  <path d="M 580 240 A 80 80 0 0 0 595 220" fill="none" stroke="#534AB7" stroke-width="1"/>
  <text x="600" y="216" font-size="12" font-weight="500" fill="#534AB7">α</text>
  <rect x="465" y="55" width="190" height="34" rx="4" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.5"/>
  <text x="560" y="76" text-anchor="middle" font-size="13" font-weight="500" fill="#3C3489">α &lt; 0  cabré (nez en haut)</text>
  <line x1="500" y1="240" x2="630" y2="290" stroke="#D4537E" stroke-width="1.5"/>
  <polygon points="630,290 621,290 626,282" fill="#D4537E"/>
  <path d="M 580 240 A 80 80 0 0 1 595 260" fill="none" stroke="#D4537E" stroke-width="1"/>
  <text x="600" y="270" font-size="12" font-weight="500" fill="#D4537E">α</text>
  <rect x="465" y="330" width="190" height="34" rx="4" fill="#FBEAF0" stroke="#D4537E" stroke-width="0.5"/>
  <text x="560" y="351" text-anchor="middle" font-size="13" font-weight="500" fill="#72243E">α &gt; 0  piqué (nez en bas)</text>
  <text x="340" y="388" text-anchor="middle" font-size="11" fill="#888780">⚠ Convention non-standard : pitch positif = nose down</text>
</svg>`;

  /* ── Panel HTML ─────────────────────────────────────────────────────────── */
  const PANEL_HTML = `
<div class="conv-titlebar" id="conv-titlebar">
  <div class="conv-titlebar-left">
    <div class="conv-titlebar-icon">✈</div>
    <h2 class="conv-title">MODÈLE</h2>
    <span class="conv-subtitle">CONVENTIONS DE RÉFÉRENCE</span>
  </div>
  <button class="conv-close">✕</button>
</div>
<div class="conv-columns">
  <div class="conv-left">
    <div class="conv-schema-viewport">
      <div class="conv-schema-block">
        <div class="conv-schema-label">VUE DE DESSUS</div>
        ${SVG_DESSUS}
      </div>
      <div class="conv-schema-block">
        <div class="conv-schema-label">VUE DE CÔTÉ · CONVENTION α</div>
        ${SVG_COTE}
      </div>
    </div>
  </div>
  <div class="conv-right">
    <div class="conv-section">
      <div class="conv-section-title">NOMENCLATURE</div>
      <table class="conv-table">
        <thead><tr><th>Réf.</th><th>Désignation</th></tr></thead>
        <tbody>
          <tr><td class="conv-ref">M1</td><td>Moteur Droit</td></tr>
          <tr><td class="conv-ref">M3</td><td>Moteur Gauche</td></tr>
          <tr><td class="conv-ref">S1</td><td>Microtilt Moteur Gauche</td></tr>
          <tr><td class="conv-ref">S2</td><td>Microtilt Moteur Droit</td></tr>
          <tr><td class="conv-ref">S3</td><td>Aileron Gauche</td></tr>
          <tr><td class="conv-ref">S4</td><td>Aileron Droit</td></tr>
          <tr><td class="conv-ref">S5</td><td>Profondeur</td></tr>
          <tr><td class="conv-ref">S6</td><td><span style="color:#e07040;">Tilt 90°</span> — basculement HOVER ↔ PLANE</td></tr>
          <tr><td class="conv-ref">S7</td><td>Dérive (gouvernail)</td></tr>
        </tbody>
      </table>
    </div>
    <div class="conv-section">
      <div class="conv-section-title">MICROTILTS S1 / S2</div>
      <div class="conv-info">ℹ S1 et S2 câblés en miroir — PWM antagonistes, tilt physique dans le même sens.</div>
      <table class="conv-table">
        <thead><tr><th>Position physique</th><th>S1 (M3 — G)</th><th>S2 (M1 — D)</th></tr></thead>
        <tbody>
          <tr><td>Vers l'avant</td><td>0°</td><td>180°</td></tr>
          <tr><td>Neutre</td><td>90°</td><td>90°</td></tr>
          <tr><td>Vers l'arrière</td><td>180°</td><td>0°</td></tr>
        </tbody>
      </table>
      <div class="conv-warn">⚠ Rapport de réduction 1:4 servo→moteur. 180° servo = 45° tilt physique (±22.5° autour du neutre). Applicable aux colonnes <span class="conv-code">s1_command_PWM</span> / <span class="conv-code">s2_command_PWM</span> du log.</div>
    </div>
    <div class="conv-section">
      <div class="conv-section-title">REPÈRES</div>
      <table class="conv-table">
        <thead><tr><th>Vue</th><th>Axes</th></tr></thead>
        <tbody>
          <tr><td>Dessus</td><td>x longitudinal, y latéral (→ droite du drone)</td></tr>
          <tr><td>Côté</td><td>z vers le haut, x longitudinal, y latéral</td></tr>
        </tbody>
      </table>
    </div>
    <div class="conv-section">
      <div class="conv-section-title">CONVENTION ANGLE α</div>
      <table class="conv-table">
        <thead><tr><th>Signe</th><th>Attitude</th></tr></thead>
        <tbody>
          <tr><td style="color:#6a8abb;">α &lt; 0</td><td>Cabré — nez vers le haut</td></tr>
          <tr><td style="color:#c06080;">α &gt; 0</td><td>Piqué — nez vers le bas</td></tr>
        </tbody>
      </table>
      <div class="conv-warn">⚠ Convention non-standard vs aéronautique classique (pitch+ = nose up). Vérifier le signe de <span class="conv-code">pitch_IMU</span> / <span class="conv-code">pitch_des</span> avant toute analyse d'attitude.</div>
    </div>
    <div class="conv-section">
      <div class="conv-section-title">SERVOS (7 actionneurs)</div>
      <table class="conv-table">
        <thead><tr><th>Servo</th><th>Désignation</th><th>Fonction</th></tr></thead>
        <tbody>
          <tr><td class="conv-ref">S1</td><td>Microtilt G</td><td>Inclinaison fine M3 — attitude en hover</td></tr>
          <tr><td class="conv-ref">S2</td><td>Microtilt D</td><td>Inclinaison fine M1 — attitude en hover</td></tr>
          <tr><td class="conv-ref">S3</td><td>Aileron G</td><td>Roulis en mode PLANE</td></tr>
          <tr><td class="conv-ref">S4</td><td>Aileron D</td><td>Roulis en mode PLANE</td></tr>
          <tr><td class="conv-ref">S5</td><td>Profondeur</td><td>Tangage en mode PLANE (T-tail)</td></tr>
          <tr><td class="conv-ref" style="color:#e07040;">S6</td><td>Tilt 90°</td><td>Basculement HOVER ↔ PLANE</td></tr>
          <tr><td class="conv-ref">S7</td><td>Dérive</td><td>Lacet en mode PLANE (T-tail)</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>`;

  /* ── Drag logic ─────────────────────────────────────────────────────────── */
  function setupDrag(panel, titlebar) {
    let dx = 0, dy = 0, dragging = false;
    titlebar.addEventListener('mousedown', function (e) {
      if (e.target.closest('.conv-close')) return;
      const r = panel.getBoundingClientRect();
      panel.style.left = r.left + 'px';
      panel.style.top  = r.top  + 'px';
      panel.style.transform = 'none';
      dx = e.clientX - r.left;
      dy = e.clientY - r.top;
      dragging = true;
      e.preventDefault();
    });
    document.addEventListener('mousemove', function (e) {
      if (!dragging) return;
      panel.style.left = (e.clientX - dx) + 'px';
      panel.style.top  = (e.clientY - dy) + 'px';
    });
    document.addEventListener('mouseup', function () { dragging = false; });
  }

  /* ── State & public API ─────────────────────────────────────────────────── */
  let _panel = null;
  let _open  = false;

  function toggleConventionsPanel() {
    if (!_panel) return;
    _open = !_open;
    _panel.style.display = _open ? 'flex' : 'none';
  }

  window.toggleConventionsPanel = toggleConventionsPanel;

  /* ── Boot ───────────────────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    const style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);

    _panel = document.createElement('div');
    _panel.id = 'conv-panel';
    _panel.innerHTML = PANEL_HTML;
    document.body.appendChild(_panel);

    setupDrag(_panel, document.getElementById('conv-titlebar'));
    _panel.querySelector('.conv-close').addEventListener('click', toggleConventionsPanel);
  });

})();
