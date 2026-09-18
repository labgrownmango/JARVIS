// Oberflaeche fuer Jarvis. Kein Framework - das hier ist klein genug.

const $ = (w) => document.querySelector(w);
const $$ = (w) => document.querySelectorAll(w);
let laeuft = false;
let letzteProtokollNummer = 0;

// --- Navigation ------------------------------------------------------------
$$("nav button").forEach((knopf) => {
  knopf.onclick = () => {
    $$("nav button").forEach((k) => k.classList.remove("an"));
    $$("main section").forEach((s) => s.classList.remove("an"));
    knopf.classList.add("an");
    $("#bereich-" + knopf.dataset.bereich).classList.add("an");
    if (knopf.dataset.bereich === "werkzeuge") werkzeugeLaden();
    if (knopf.dataset.bereich === "einstellungen") einstellungenLaden();
    if (knopf.dataset.bereich === "agenten") agentenLaden();
    if (knopf.dataset.bereich === "protokoll") protokollLaden(true);
  };
});

// --- Anzeigemodus ----------------------------------------------------------
// text     = alles steht da, Lautsprecher liest auf Klick vor
// mischung = kein Verlauf, nur die drei Striche, alles wird vorgelesen
// frei     = wie mischung, das Mikrofon läuft nach jeder Antwort weiter
let modus = "text";
const HINWEISE = {
  text: "Antworten stehen da; der Lautsprecher liest vor.",
  mischung: "Antworten werden vorgelesen, die Striche folgen der Stimme.",
  frei: "Nach jeder Antwort hört Jarvis von selbst weiter zu.",
};

// Kann dieser Browser ueberhaupt ein Mikrofon oeffnen? Ueber http:// von
// einem anderen Geraet aus nicht - dort gibt es navigator.mediaDevices gar
// nicht. Die Sprachmodi wurden trotzdem angeboten und taten dann nichts;
// "Freies Sprechen" sah aus wie "Stimme", weil beide nichts taten.
const MIKRO_MOEGLICH = !!(navigator.mediaDevices
                          && navigator.mediaDevices.getUserMedia);

function modusSetzen(neu) {
  if (neu !== "text" && !MIKRO_MOEGLICH) {
    $("#modushinweis").textContent =
      `Kein Mikrofon über ${location.protocol}//${location.host} - `
      + "Browser geben es nur über HTTPS frei. Tippen geht weiter, und "
      + "\"Hey Jarvis\" hört ohnehin am Rechner selbst mit.";
    $("#modushinweis").classList.add("warnung");
    return;                                  // Modus NICHT umschalten
  }
  $("#modushinweis").classList.remove("warnung");
  modus = neu;
  $$("button.modus").forEach((k) => k.classList.toggle("an", k.dataset.modus === neu));
  $("#modushinweis").textContent = HINWEISE[neu];

  // Beim freien Sprechen tippt niemand - dort steht statt der Eingabezeile,
  // was verstanden wurde. Sonst redet man und weiss nicht, ob und wie es
  // angekommen ist, bis die Antwort da ist.
  const frei = neu === "frei";
  $("#eingabezeile").hidden = frei;
  $("#gehoertes").hidden = !frei;
  if (frei) gehoertSetzen("", "wartet");
  const stumm = neu !== "text";
  $("#verlauf").hidden = stumm;
  $("#striche").hidden = !stumm;
  if (stumm) { Stimme.starten(); Stimme.ruhen(); strichetext("bereit"); }
  else { Stimme.stopp(); if (Ohren.laeuft()) Ohren.stoppen(); }
}

function strichetext(t) { $("#strichetext").textContent = t; }

// Was beim freien Sprechen statt der Eingabezeile steht.
const GEHOERT_LAGE = {
  wartet: "bereit - sprich einfach",
  hoert: "hört zu …",
  denkt: "verstanden:",
  nichts: "nichts verstanden - noch einmal?",
};

function gehoertSetzen(text, lage) {
  const feld = $("#gehoertes");
  feld.className = "lage-" + lage;
  $("#gehoertlage").textContent = GEHOERT_LAGE[lage] || lage;
  $("#gehoerttext").textContent = text || "";
}

$$("button.modus").forEach((k) => (k.onclick = () => modusSetzen(k.dataset.modus)));

// Geht kein Mikrofon, sollen die Knöpfe auch danach aussehen - statt sie
// anzubieten und beim Klick nichts zu tun.
if (!MIKRO_MOEGLICH) {
  $$("button.modus").forEach((k) => {
    if (k.dataset.modus !== "text") {
      k.classList.add("geht-nicht");
      k.title = "Braucht HTTPS - der Browser gibt das Mikrofon sonst nicht frei";
    }
  });
}

// --- Chat ------------------------------------------------------------------
function lautsprecherSvg() {
  return `<svg viewBox="0 0 24 24" width="15" height="15" fill="none"
     stroke="currentColor" stroke-width="2" stroke-linejoin="round">
     <path d="M11 5 6 9H3v6h3l5 4V5z"/><path d="M16 9a4 4 0 0 1 0 6"/></svg>`;
}

function kopierSvg() {
  return `<svg viewBox="0 0 24 24" width="15" height="15" fill="none"
     stroke="currentColor" stroke-width="2" stroke-linejoin="round">
     <rect x="9" y="9" width="11" height="11" rx="2"/>
     <path d="M5 15V5a2 2 0 0 1 2-2h8"/></svg>`;
}

// Zwei Wege, und der zweite wird gebraucht: navigator.clipboard gibt es nur
// in einem "sicheren Kontext" - also ueber https oder auf 127.0.0.1. Wer die
// Oberflaeche im Heimnetz unter http://jarvis aufmacht, hat ihn NICHT, und
// der Knopf taete dort wortlos nichts.
async function inZwischenablage(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (e) { /* dann eben der alte Weg */ }
  try {
    const feld = document.createElement("textarea");
    feld.value = text;
    // Ausserhalb des Sichtfelds, aber nicht display:none - sonst laesst
    // sich nichts markieren, und execCommand kopiert ins Leere.
    feld.style.position = "fixed";
    feld.style.left = "-9999px";
    document.body.appendChild(feld);
    feld.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(feld);
    return ok;
  } catch (e) {
    return false;
  }
}

// --- Bilder in der Antwort --------------------------------------------------
// Jarvis darf Bilder zeigen, indem er ![Beschreibung](https://...) schreibt.
// Der Browser holt das Bild und zeigt es an - auf der Platte landet nichts,
// das Download-Verbot bleibt also gewahrt.
//
// Was NICHT passiert: der Text des Modells wird niemals als HTML eingesetzt.
// Er kommt mittelbar aus dem Netz (Suchtreffer, Seiteninhalte), und ein
// innerHTML damit waere die klassische Luecke. Stattdessen wird der Text
// zerlegt, und das <img> baut diese Funktion selbst - mit geprueften Werten.
const BILD_MUSTER = /!\[([^\]\n]{0,140})\]\((https:\/\/[^\s)"'<>]{1,500})\)/g;
const BILD_ENDUNG = /\.(jpe?g|png|gif|webp|avif)(?:[?#]|$)/i;

// Bilder, zwischen denen nur Leerraum steht, kommen NEBENEINANDER in eine
// Reihe - bis zu drei. Darueber beginnt eine neue Reihe, statt sie immer
// schmaler zu quetschen: vier Bilder nebeneinander sind auf diesem Bildschirm
// briefmarkengross und zeigen nichts mehr.
//
// Steht ECHTER Text dazwischen, ist die Reihe zu Ende. Damit ergibt sich das
// Muster von selbst, um das es geht: zwei Fotos, ein Absatz dazu, darunter
// eine Karte, wieder ein Absatz. Das Modell muss dafuer nichts ueber Reihen
// wissen - es schreibt seine Zeilen hin, der Abstand entscheidet.
const BILDER_JE_REIHE = 3;

function bildErlaubt(adresse) {
  let u;
  try { u = new URL(adresse); } catch (e) { return false; }
  if (u.protocol !== "https:") return false;   // kein data:, kein javascript:
  if (!u.hostname) return false;
  // SVG kann Skripte enthalten - und Skripte sind hier verboten
  if (/\.svgz?(?:[?#]|$)/i.test(u.pathname)) return false;
  return BILD_ENDUNG.test(u.pathname);
}

// --- Formeln lesbar machen ---------------------------------------------------
// Gemeldet aus dem Betrieb, so stand es im Fenster:
//
//     Dann nutzt du die Formel
//     \[
//     A = \pi \times r^{2}
//     \]
//     ... multipliziere mit \(\pi\) (≈ 3,14159).
//
// Das ist LaTeX. Eine Formelbibliothek (KaTeX, MathJax) waere der uebliche
// Weg und kommt hier nicht in Frage: fremdes Skript, und die
// Sicherheitsrichtlinie laesst nur eigene zu. Herunterladen und mitliefern
// waere ein halbes Megabyte fuer eine Formel im Monat.
//
// Also umrechnen statt darstellen. "A = π × r²" ist in einem Chatfenster
// ohnehin besser lesbar als gesetzter Formelsatz - und die Stimme kann es
// vorlesen, was sie bei "\pi" nicht kann.
const HOCH = { "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵",
               "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻",
               "(": "⁽", ")": "⁾", "n": "ⁿ", "i": "ⁱ" };
const TIEF = { "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅",
               "6": "₆", "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋",
               "(": "₍", ")": "₎" };
const ZEICHEN = {
  pi: "π", alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε",
  theta: "θ", lambda: "λ", mu: "μ", sigma: "σ", phi: "φ", omega: "ω",
  Delta: "Δ", Sigma: "Σ", Omega: "Ω",
  times: "×", cdot: "·", div: "÷", pm: "±", mp: "∓",
  leq: "≤", le: "≤", geq: "≥", ge: "≥", neq: "≠", ne: "≠",
  approx: "≈", equiv: "≡", propto: "∝", infty: "∞",
  rightarrow: "→", to: "→", leftarrow: "←", Rightarrow: "⇒",
  sum: "∑", prod: "∏", int: "∫", partial: "∂", nabla: "∇",
  in: "∈", subset: "⊂", cup: "∪", cap: "∩", forall: "∀", exists: "∃",
  circ: "°", degree: "°", ldots: "…", dots: "…",
};

function hochtief(inhalt, tabelle) {
  // Nur umstellen, wenn JEDES Zeichen eine Entsprechung hat - sonst wird
  // aus "r^{2n+1}" ein Flickenteppich aus halb hochgestellten Zeichen.
  const zeichen = [...inhalt];
  if (!zeichen.length || !zeichen.every((z) => tabelle[z])) return null;
  return zeichen.map((z) => tabelle[z]).join("");
}

// Klammern nur, wo sie gebraucht werden: "3/4" liest sich besser als
// "(3)/(4)", aber "(-b + √(...))/(2a)" braucht sie, sonst aendert sich die
// Bedeutung.
function klammern(teil) {
  const t = teil.trim();
  return /^[\wäöüÄÖÜß.,'⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉π]+$/.test(t) ? t : `(${t})`;
}

function formelnLesbar(text) {
  if (!text || (!text.includes("\\") && !text.includes("$"))) return text;
  let t = text;

  // Die Umgebungen selbst weg. \[...\] steht fuer sich, \(...\) im Satz.
  t = t.replace(/\\\[\s*([\s\S]*?)\s*\\\]/g, (_, m) => "\n" + m.trim() + "\n");
  t = t.replace(/\\\(\s*([\s\S]*?)\s*\\\)/g, (_, m) => m.trim());
  t = t.replace(/\$\$\s*([\s\S]*?)\s*\$\$/g, (_, m) => "\n" + m.trim() + "\n");
  // Einzelnes $...$ NUR, wenn wirklich LaTeX drinsteht - also ein
  // Backslash. Ohne diese Bedingung frisst die Regel Geldbetraege:
  // "Kosten $19 bis $25" wurde zu "Kosten 19 bis25", weil "19 bis $"
  // als Formel galt. Im eigenen Test aufgefallen, bevor es jemand sah.
  t = t.replace(/\$([^$\n]{1,120})\$/g,
                (m, inhalt) => (inhalt.includes("\\") ? inhalt.trim() : m));

  t = t.replace(/\\left|\\right/g, "");
  t = t.replace(/\\(?:text|mathrm|mathit|mathbf|operatorname)\{([^{}]*)\}/g,
                "$1");
  // Mehrere Durchgaenge, INNEN nach AUSSEN. Ein \frac, dessen Zaehler ein
  // \sqrt enthaelt, passt beim ersten Mal auf kein Muster - die inneren
  // geschweiften Klammern stehen noch da. Gemessen an
  // "\frac{-b + \sqrt{b^2 - 4ac}}{2a}": ohne die Wiederholung blieb das
  // \frac stehen und nur die Wurzel wurde ersetzt.
  for (let runde = 0; runde < 4; runde++) {
    const vorher = t;
    t = t.replace(/\\sqrt\{([^{}]*)\}/g, (_, a) => `√(${a})`);
    t = t.replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g,
                  (_, a, b) => `${klammern(a)}/${klammern(b)}`);
    if (t === vorher) break;
  }
  t = t.replace(/\\[a-zA-Z]+/g, (m) => {
    const name = m.slice(1);
    return ZEICHEN[name] !== undefined ? ZEICHEN[name] : m;
  });

  // Hoch- und Tiefstellung, mit und ohne geschweifte Klammern.
  t = t.replace(/\^\{([^{}]*)\}/g, (m, i) => hochtief(i, HOCH) || `^${i}`);
  t = t.replace(/\^(\w)/g, (m, i) => hochtief(i, HOCH) || m);
  t = t.replace(/_\{([^{}]*)\}/g, (m, i) => hochtief(i, TIEF) || `_${i}`);
  t = t.replace(/_(\w)/g, (m, i) => hochtief(i, TIEF) || m);

  // Abstandsbefehle und was an leeren Klammern uebrig bleibt.
  t = t.replace(/\\[,;:!]|\\quad|\\qquad/g, " ");
  t = t.replace(/\\\\/g, "\n");
  return t.replace(/[ \t]{2,}/g, " ").replace(/\n{3,}/g, "\n\n");
}

// --- Markdown ---------------------------------------------------------------
// Das Modell schreibt Markdown: **fett**, `Code`, Aufzählungen, Tabellen,
// Überschriften. Ungerendert stand das alles roh im Fenster - "- **/help** –
// Zeigt diese Hilfe an." - und war schlechter lesbar als gar keine Auszeichnung.
//
// Selbst geschrieben, nicht eingebunden: die Sicherheitsrichtlinie der Seite
// lässt nur eigene Skripte zu, eine Bibliothek von einem fremden Server käme
// gar nicht erst an. Und der wichtigere Grund steht schon oben: der Text des
// Modells wird NIE als HTML eingesetzt. Jedes Element hier wird einzeln
// gebaut, jeder Textknoten ist ein Textknoten. Damit ist das, was eine fremde
// Webseite in einen Suchtreffer schreibt, Text und bleibt Text.
const MD_FETT_KURSIV = /(\*\*\*|___)(?=\S)([\s\S]*?\S)\1/;
const MD_FETT = /(\*\*|__)(?=\S)([\s\S]*?\S)\1/;
const MD_KURSIV = /(?<![*\w])(\*|_)(?=\S)([^*_\n]*?\S)\1(?![*\w])/;
const MD_CODE = /`([^`\n]+)`/;
const MD_LINK = /\[([^\]\n]{1,160})\]\((https?:\/\/[^\s)"'<>]{1,500})\)/;

function linkErlaubt(adresse) {
  try {
    const u = new URL(adresse);
    return u.protocol === "https:" || u.protocol === "http:";
  } catch (e) { return false; }
}

// Eine Zeile Markdown in Textknoten und kleine Elemente zerlegen.
function mdZeile(ziel, text) {
  // Reihenfolge zählt: Code zuerst, damit `**` in Code nicht fett wird.
  const regeln = [
    [MD_CODE, (t) => { const e = document.createElement("code");
                       e.textContent = t[1]; return e; }],
    [MD_LINK, (t) => {
      if (!linkErlaubt(t[2])) return document.createTextNode(t[1]);
      const a = document.createElement("a");
      a.href = t[2];
      a.textContent = t[1];
      a.target = "_blank";
      a.rel = "noopener noreferrer nofollow";
      return a;
    }],
    [MD_FETT_KURSIV, (t) => { const e = document.createElement("strong");
                              const i = document.createElement("em");
                              mdZeile(i, t[2]); e.appendChild(i); return e; }],
    [MD_FETT, (t) => { const e = document.createElement("strong");
                       mdZeile(e, t[2]); return e; }],
    [MD_KURSIV, (t) => { const e = document.createElement("em");
                         mdZeile(e, t[2]); return e; }],
  ];

  let frueheste = null, bauen = null;
  for (const [muster, baue] of regeln) {
    const t = muster.exec(text);
    if (t && (frueheste === null || t.index < frueheste.index)) {
      frueheste = t; bauen = baue;
    }
  }
  if (!frueheste) { ziel.appendChild(document.createTextNode(text)); return; }

  if (frueheste.index > 0) {
    ziel.appendChild(document.createTextNode(text.slice(0, frueheste.index)));
  }
  ziel.appendChild(bauen(frueheste));
  mdZeile(ziel, text.slice(frueheste.index + frueheste[0].length));
}

function mdTabelle(zeilen) {
  const teile = (z) => z.replace(/^\s*\|/, "").replace(/\|\s*$/, "")
                        .split("|").map((s) => s.trim());
  const tabelle = document.createElement("table");
  tabelle.className = "mdtabelle";
  const kopf = document.createElement("thead");
  const kz = document.createElement("tr");
  for (const feld of teile(zeilen[0])) {
    const th = document.createElement("th");
    mdZeile(th, feld);
    kz.appendChild(th);
  }
  kopf.appendChild(kz);
  tabelle.appendChild(kopf);
  const koerper = document.createElement("tbody");
  for (const zeile of zeilen.slice(2)) {
    const tr = document.createElement("tr");
    for (const feld of teile(zeile)) {
      const td = document.createElement("td");
      mdZeile(td, feld);
      tr.appendChild(td);
    }
    koerper.appendChild(tr);
  }
  tabelle.appendChild(koerper);
  // Breite Tabellen dürfen scrollen, statt das Fenster zu sprengen
  const rahmen = document.createElement("div");
  rahmen.className = "mdtabellerahmen";
  rahmen.appendChild(tabelle);
  return rahmen;
}

function markdownSetzen(ziel, text) {
  const zeilen = text.split("\n");
  let i = 0;

  const istTrenner = (z) => /^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$/.test(z)
                            && z.includes("-");

  while (i < zeilen.length) {
    const zeile = zeilen[i];

    if (/^\s*```/.test(zeile)) {                       // Codeblock
      const sprache = zeile.replace(/^\s*```/, "").trim();
      const inhalt = [];
      i++;
      while (i < zeilen.length && !/^\s*```/.test(zeilen[i])) {
        inhalt.push(zeilen[i]); i++;
      }
      i++;
      const pre = document.createElement("pre");
      pre.className = "mdcode";
      if (sprache) pre.dataset.sprache = sprache;
      const code = document.createElement("code");
      code.textContent = inhalt.join("\n");
      pre.appendChild(code);
      ziel.appendChild(pre);
      continue;
    }

    if (!zeile.trim()) { i++; continue; }

    const ueber = /^(#{1,4})\s+(.*)$/.exec(zeile);
    if (ueber) {
      const h = document.createElement("h" + (ueber[1].length + 2));
      h.className = "mdueber";
      mdZeile(h, ueber[2]);
      ziel.appendChild(h);
      i++;
      continue;
    }

    if (/^\s*([-*_])\s*\1\s*\1[\s\S]*$/.test(zeile.trim())
        && zeile.trim().replace(/[\s]/g, "").length >= 3
        && /^[-*_]+$/.test(zeile.trim().replace(/\s/g, ""))) {
      ziel.appendChild(document.createElement("hr"));
      i++;
      continue;
    }

    // Tabelle: Kopfzeile, Trennzeile, dann Inhalt
    if (zeile.includes("|") && i + 1 < zeilen.length
        && istTrenner(zeilen[i + 1])) {
      const block = [zeilen[i], zeilen[i + 1]];
      i += 2;
      while (i < zeilen.length && zeilen[i].includes("|")) {
        block.push(zeilen[i]); i++;
      }
      ziel.appendChild(mdTabelle(block));
      continue;
    }

    const punkt = /^\s*([-*+]|\d{1,3}[.)])\s+/;
    if (punkt.test(zeile)) {
      const geordnet = /^\s*\d/.test(zeile);
      const liste = document.createElement(geordnet ? "ol" : "ul");
      liste.className = "mdliste";
      while (i < zeilen.length && punkt.test(zeilen[i])) {
        const li = document.createElement("li");
        mdZeile(li, zeilen[i].replace(punkt, ""));
        liste.appendChild(li);
        i++;
      }
      ziel.appendChild(liste);
      continue;
    }

    if (/^\s*>/.test(zeile)) {
      const zitat = document.createElement("blockquote");
      zitat.className = "mdzitat";
      const inhalt = [];
      while (i < zeilen.length && /^\s*>/.test(zeilen[i])) {
        inhalt.push(zeilen[i].replace(/^\s*>\s?/, "")); i++;
      }
      markdownSetzen(zitat, inhalt.join("\n"));
      ziel.appendChild(zitat);
      continue;
    }

    // Normaler Absatz - zusammenhängende Zeilen gehören zusammen
    const absatz = [];
    while (i < zeilen.length && zeilen[i].trim()
           && !/^\s*```/.test(zeilen[i]) && !punkt.test(zeilen[i])
           && !/^\s*>/.test(zeilen[i]) && !/^#{1,4}\s/.test(zeilen[i])) {
      absatz.push(zeilen[i]); i++;
    }
    if (absatz.length) {
      const p = document.createElement("p");
      p.className = "mdabsatz";
      absatz.forEach((z, n) => {
        if (n) p.appendChild(document.createElement("br"));
        mdZeile(p, z);
      });
      ziel.appendChild(p);
    }
  }
}

function inhaltSetzen(feld, text) {
  feld.textContent = "";
  // Formeln VOR allem anderen lesbar machen - dann greifen Anzeige,
  // Kopieren und Vorlesen auf denselben Text zu. Waere es nur die Anzeige,
  // bekaeme der Kopierknopf "\pi" und die Stimme laese "Backslash pi".
  text = formelnLesbar(text);
  // Der Rohtext bleibt liegen - der Kopierknopf soll das Markdown geben,
  // nicht den dargestellten Text. Wer eine Antwort weiterschickt, will die
  // Sternchen und Striche behalten, sonst ist die Gliederung beim Einfuegen
  // verloren.
  feld.dataset.roh = text || "";
  BILD_MUSTER.lastIndex = 0;
  let pos = 0, t, reihe = null;
  while ((t = BILD_MUSTER.exec(text)) !== null) {
    const davor = text.slice(pos, t.index);
    if (davor.trim() !== "") {
      // Echter Text zwischen zwei Bildern beendet die Reihe.
      markdownSetzen(feld, davor);
      reihe = null;
    }
    const beschreibung = t[1] || "Bild", adresse = t[2];
    if (bildErlaubt(adresse)) {
      if (!reihe || reihe.childElementCount >= BILDER_JE_REIHE) {
        reihe = document.createElement("div");
        reihe.className = "bildreihe";
        feld.appendChild(reihe);
      }
      const bild = document.createElement("img");
      bild.className = "chatbild";
      bild.alt = beschreibung;
      bild.title = beschreibung;
      bild.loading = "lazy";
      bild.decoding = "async";
      // Die fremde Seite soll nicht erfahren, von wo aus gefragt wurde
      bild.referrerPolicy = "no-referrer";
      bild.src = adresse;
      bild.onerror = () => {
        const ersatz = document.createElement("span");
        ersatz.className = "bildfehler";
        ersatz.textContent = "[Bild nicht erreichbar: " + beschreibung + "]";
        bild.replaceWith(ersatz);
      };
      reihe.appendChild(bild);
    } else {
      // Nicht kommentarlos verschlucken - sonst wundert man sich
      feld.appendChild(document.createTextNode("[" + beschreibung + "]"));
      reihe = null;
    }
    pos = t.index + t[0].length;
  }
  if (pos < text.length) {
    markdownSetzen(feld, text.slice(pos));
  }
  // Vorgelesen wird die Beschreibung, nicht die Adresse - und ohne die
  // Auszeichnungszeichen, sonst liest die Stimme "Sternchen Sternchen".
  feld.dataset.gesprochen = text
    .replace(BILD_MUSTER, "$1")
    .replace(/```[\s\S]*?```/g, " Codeblock. ")
    // Von einem Link wird der Text gesprochen, nicht die Adresse - eine
    // vorgelesene URL ist für niemanden zu gebrauchen.
    .replace(/\[([^\]\n]{1,160})\]\([^\s)]{1,500}\)/g, "$1")
    .replace(/[*_`#>|]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function blase(wer, text, klasse) {
  const div = document.createElement("div");
  div.className = "blase " + (klasse || wer.toLowerCase());
  div.innerHTML = `<div class="wer">${wer}</div><div class="inhalt"></div>`;
  inhaltSetzen(div.querySelector(".inhalt"), text || "");

  if (wer === "JARVIS") {
    // Eine Leiste UNTER der Antwort statt eines Knopfes oben an der
    // Sprecherzeile: dort sucht man sie, wenn man sie braucht - man hat die
    // Antwort ja gerade zu Ende gelesen.
    const fuss = document.createElement("div");
    fuss.className = "antwortfuss";

    const knopf = document.createElement("button");
    knopf.className = "fussknopf vorlesen";
    knopf.type = "button";
    knopf.title = "Vorlesen";
    knopf.innerHTML = lautsprecherSvg();
    knopf.onclick = () => {
      if (knopf.classList.contains("laeuft")) {
        Stimme.stopp(); knopf.classList.remove("laeuft"); return;
      }
      knopf.classList.add("laeuft");
      const feld = div.querySelector(".inhalt");
      Stimme.sprich(feld.dataset.gesprochen || feld.textContent,
                    () => knopf.classList.remove("laeuft"));
    };

    const kopieren = document.createElement("button");
    kopieren.className = "fussknopf";
    kopieren.type = "button";
    kopieren.title = "Kopieren";
    kopieren.innerHTML = kopierSvg();
    kopieren.onclick = async () => {
      const feld = div.querySelector(".inhalt");
      const text = feld.dataset.roh || feld.textContent;
      const geschafft = await inZwischenablage(text);
      kopieren.title = geschafft ? "Kopiert" : "Kopieren ging nicht";
      kopieren.classList.toggle("geschafft", geschafft);
      setTimeout(() => {
        kopieren.title = "Kopieren";
        kopieren.classList.remove("geschafft");
      }, 1500);
    };

    fuss.append(knopf, kopieren);
    div.appendChild(fuss);
  }

  $("#verlauf").appendChild(div);
  $("#verlauf").scrollTop = $("#verlauf").scrollHeight;
  return div.querySelector(".inhalt");
}

// --- Der Arc-Reaktor --------------------------------------------------------
// Er steht da, wo gleich die Antwort steht - nicht unten am Rand. Dadurch
// wandert der Blick nicht hin und her, und man sieht am selben Fleck, dass
// dort etwas entsteht.
function arcSvg() {
  return `
  <svg class="arc" viewBox="0 0 40 40" width="22" height="22" aria-hidden="true">
    <circle class="arc-huelle" cx="20" cy="20" r="17"/>
    <g class="arc-spulen">
      ${[0, 45, 90, 135, 180, 225, 270, 315].map((grad) =>
        `<rect class="arc-spule" x="19" y="4" width="2" height="6" rx="1"
               transform="rotate(${grad} 20 20)"/>`).join("")}
    </g>
    <circle class="arc-ring" cx="20" cy="20" r="10"/>
    <circle class="arc-kern" cx="20" cy="20" r="5.5"/>
  </svg>`;
}

// Immer "Jarvis denkt" zu schreiben klingt nach einer Ladeanzeige, die nur
// so tut. Was er gerade WIRKLICH macht, weiss die Oberflaeche aber: das
// Modell meldet jeden Werkzeugaufruf. Also wird das gesagt - und wo es
// nichts Genaueres gibt, wechseln wenigstens die Worte.
const DENKWORTE = [
  "Jarvis denkt nach", "Jarvis überlegt", "Jarvis sortiert das",
  "Jarvis geht das durch", "Jarvis sucht die Antwort",
  "Jarvis wägt ab", "Jarvis formuliert",
];

// Was welches Werkzeug tut - in Worten, nicht als Funktionsname. "Werkzeug:
// get_weather" sagt einem Menschen nichts.
//
// DREI Formulierungen je Werkzeug, und es wird reihum gewechselt. Grund:
// wer zweimal hintereinander dasselbe liest, haelt es fuer eine Anzeige,
// die haengt - dieselbe Ueberlegung, die es bei DENKWORTE schon gab. Wer
// eine vierte hinzufuegt, stoert nichts; der Test unten verlangt aber
// mindestens drei, damit es nicht bei einer bleibt.
//
// Die Liste war ausserdem veraltet: post, code, bild, set_reminder und
// browser gibt es als Werkzeug gar nicht mehr, und zehn andere fehlten -
// darunter search_images und pubmed. Dort stand dann "Jarvis benutzt
// search_images …", der Funktionsname also, den diese Liste gerade
// vermeiden soll. Ein Test haelt sie jetzt an der echten Werkzeugliste fest.
const WERKZEUGWORTE = {
  agent_bericht: ["hört sich den Bericht an", "nimmt den Bericht entgegen", "liest, was der Agent gefunden hat"],
  agenten_status: ["sieht im Hangar nach", "fragt die Agenten ab", "schaut, wer noch arbeitet"],
  ask_user: ["hat eine Rückfrage", "fragt kurz nach", "braucht eine Auskunft"],
  benachrichtigungen: ["sieht die Meldungen durch", "prüft, was gemeldet wurde", "schaut nach neuen Hinweisen"],
  bildschirm_vorlesen: ["liest vom Bildschirm ab", "liest vor, was da steht", "gibt den Text an die Stimme"],
  close_app: ["schließt ein Programm", "beendet ein Programm", "räumt ein Fenster weg"],
  erinnerung: ["sieht in den Erinnerungen nach", "geht die Erinnerungen durch", "prüft, was ansteht"],
  gedaechtnis: ["kramt im Gedächtnis", "sieht im Gedächtnis nach", "erinnert sich"],
  get_location: ["sieht nach dem Standort", "bestimmt den Standort", "schaut, wo wir sind"],
  get_news: ["sieht die Nachrichten durch", "liest die Schlagzeilen", "holt die Nachrichtenlage"],
  get_price: ["holt den Kurs", "fragt den Preis ab", "sieht nach dem Kurs"],
  get_time: ["sieht auf die Uhr", "prüft die Uhrzeit", "schaut, wie spät es ist"],
  get_weather: ["sieht nach dem Wetter", "fragt das Wetter ab", "holt die Vorhersage"],
  idle_time: ["sieht auf die Uhr", "prüft, wie lange es still war", "schaut nach der Leerlaufzeit"],
  livivo: ["schlägt LIVIVO auf", "öffnet die LIVIVO-Suche", "holt die deutsche Fachliteratur herauf"],
  mail_lesen: ["holt die Mail herauf", "schlägt die Mail auf", "legt die Mail ins Fenster"],
  look_at_screen: ["sieht auf den Bildschirm", "wirft einen Blick auf den Schirm", "schaut sich an, was da steht"],
  open_app: ["startet ein Programm", "fährt ein Programm hoch", "öffnet ein Programm"],
  open_with: ["öffnet eine Datei", "schlägt eine Datei auf", "gibt die Datei ans richtige Programm"],
  ort_info: ["sieht auf die Karte", "schlägt den Ort nach", "sucht die Gegend heraus"],
  postfach: ["sieht in den Briefkasten", "prüft die Post", "schaut, ob Post da ist"],
  pubmed: ["durchsucht PubMed", "sieht in der Fachliteratur nach", "holt die Studienlage"],
  read_page: ["liest eine Seite", "arbeitet sich durch die Seite", "holt den Text der Seite"],
  rechnen: ["rechnet", "rechnet es durch", "macht die Rechnung"],
  search_images: ["sucht Bilder", "sieht sich nach Bildern um", "holt ein paar Aufnahmen"],
  search_web: ["durchsucht das Netz", "sucht im Internet", "geht die Treffer durch"],
  set_brightness: ["regelt die Helligkeit", "dreht die Helligkeit", "stellt den Bildschirm ein"],
  set_night_mode: ["schaltet den Nachtmodus", "stellt auf Nacht um", "nimmt das Blau heraus"],
  set_volume: ["regelt die Lautstärke", "dreht die Lautstärke", "stellt den Ton ein"],
  start_agent: ["schickt einen Agenten los", "setzt einen Agenten an", "gibt die Aufgabe weiter"],
  system_info: ["liest die Hardware aus", "sieht sich den Rechner an", "holt die Gerätedaten"],
  system_status: ["prüft den Rechner", "sieht nach dem System", "misst Last und Speicher"],
  uebersetzen: ["übersetzt", "überträgt es", "sucht die richtige Formulierung"],
  vorlesen: ["liest vor", "gibt es an die Stimme", "spricht es aus"],
  was_laeuft: ["sieht nach, was läuft", "geht die Programme durch", "prüft die offenen Fenster"],
  wikipedia: ["schlägt in der Wikipedia nach", "sieht in der Wikipedia nach", "holt den Artikel"],
  write_code: ["schreibt Code", "tippt ein paar Zeilen", "baut das Programmstück"],
};

// Welche Formulierung war zuletzt dran? Je Werkzeug eigens, sonst springt
// der Zaehler beim Wechsel zwischen zwei Werkzeugen wild herum.
const werkzeugZaehler = {};

function werkzeugwort(name) {
  const worte = WERKZEUGWORTE[name];
  if (!worte) return `benutzt ${name}`;
  const i = werkzeugZaehler[name] === undefined
    ? Math.floor(Math.random() * worte.length)
    : (werkzeugZaehler[name] + 1) % worte.length;
  werkzeugZaehler[name] = i;
  return worte[i];
}

// Fuer die Beschriftung im Nachhinein - dort soll es NICHT wechseln, sonst
// heisst dasselbe Werkzeug in der Liste anders als eben im Reaktor.
function werkzeugName(name) {
  const worte = WERKZEUGWORTE[name];
  return worte ? worte[0] : name;
}

// Auch das Warten und das Nachschlagen im Archiv bekommen Abwechslung -
// alles ausser dem Denken, das hat seine eigene Liste.
const WARTEWORTE = [
  (s) => `Modell belegt, neuer Versuch in ${s} s …`,
  (s) => `Die Leitung ist voll - in ${s} s noch einmal …`,
  (s) => `Der Anbieter bremst. Zweiter Anlauf in ${s} s …`,
];
let warteIndex = Math.floor(Math.random() * WARTEWORTE.length);

function wartewort(sekunden) {
  warteIndex = (warteIndex + 1) % WARTEWORTE.length;
  return WARTEWORTE[warteIndex](sekunden);
}

let denkblase = null;      // die Blase, die den Reaktor gerade zeigt
let denkwortIndex = Math.floor(Math.random() * DENKWORTE.length);
let gedanken = [];         // das laute Denken dieser Anfrage
let benutzteWerkzeuge = [];

function denkenZeigen(text) {
  if (!denkblase) {
    const div = document.createElement("div");
    div.className = "blase denken";
    div.innerHTML = `<div class="wer">JARVIS</div>
      <div class="inhalt">${arcSvg()}<span class="denktext"></span></div>`;
    $("#verlauf").appendChild(div);
    denkblase = div;
  }
  denkblase.querySelector(".denktext").textContent = text;
  $("#verlauf").scrollTop = $("#verlauf").scrollHeight;
}

// Der Gedankengang des Modells. Er gehört nicht in die Antwort - dort stand
// er früher mitten drin -, ist aber auch nicht wertlos: man sieht, warum
// Jarvis etwas nachgeschlagen hat und worauf er hinauswollte.
function gedankeDazu(text) {
  gedanken.push(text);
}

// --- Woher die Auskunft stammt ---------------------------------------------
// Zwei Wege, und der erste geht vor:
//
//   1. Bekannte Seiten bekommen ein HIER GEZEICHNETES Zeichen. Es ist
//      sofort da, braucht keine Verbindung und sieht in beiden Themen gut
//      aus - ein Favicon ist oft ein 16x16-Pixelbild von 2009.
//   2. Alle uebrigen bekommen ihr echtes Favicon ueber ein <img>, mit dem
//      Anfangsbuchstaben darunter als Rueckfall.
//
// Zum zweiten Punkt, weil hier frueher das Gegenteil stand: ein <img>
// LAEDT nichts herunter, es zeigt an. Das ist dasselbe Argument, mit dem
// Jarvis ueberhaupt Bilder in die Antwort setzen darf, und es hier anders
// zu behaupten war schlicht widerspruechlich.
const QUELLZEICHEN = {
  wikipedia:
    '<svg viewBox="0 0 16 16" aria-hidden="true"><text x="8" y="12" '
    + 'text-anchor="middle" font-size="12" font-family="Georgia,serif" '
    + 'fill="currentColor">W</text></svg>',
  seite:
    '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" '
    + 'stroke="currentColor" stroke-width="1.3">'
    + '<circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c1.8 2 1.8 10 0 12'
    + 'M8 2c-1.8 2-1.8 10 0 12"/></svg>',
};
QUELLZEICHEN.web = QUELLZEICHEN.seite;

// Bekannte Seiten bekommen ihr eigenes Zeichen statt eines Buchstabens.
// Gemeldet: unter den Quellen stand ein "I" auf farbigem Grund - fuer
// Instagram, das nun wirklich ein Zeichen hat.
//
// Auch diese sind GEZEICHNET und nicht geholt. Der Grund ist derselbe wie
// oben: ein echtes Favicon hiesse ein Web-Download je Quelle, und die Seite
// erfuehre nebenbei, dass hier nach ihr gefragt wurde. Was hier steht,
// kostet keinen einzigen Zugriff.
//
// Der Schluessel ist die Basisadresse, wie wirt() sie liefert. Wer eine
// Seite hinzufuegt, braucht nur eine Zeile - und der Buchstabe bleibt die
// Rueckfallebene fuer alles Uebrige.
const SEITENZEICHEN = {
  "instagram.com": {
    farbe: "#c13584",
    svg: '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" '
      + 'stroke="#fff" stroke-width="1.35">'
      + '<rect x="2.3" y="2.3" width="11.4" height="11.4" rx="3.6"/>'
      + '<circle cx="8" cy="8" r="2.9"/>'
      + '<circle cx="11.5" cy="4.5" r="0.85" fill="#fff" stroke="none"/>'
      + '</svg>',
  },
  "youtube.com": {
    farbe: "#c4302b",
    svg: '<svg viewBox="0 0 16 16" aria-hidden="true">'
      + '<rect x="1.4" y="3.6" width="13.2" height="8.8" rx="2.6" '
      + 'fill="#fff"/><path d="M6.6 6.1l4 1.9-4 1.9z" fill="#c4302b"/>'
      + '</svg>',
  },
  "github.com": {
    farbe: "#24292f",
    svg: '<svg viewBox="0 0 16 16" aria-hidden="true" fill="#fff">'
      + '<path d="M8 1.6a6.4 6.4 0 00-2 12.5c.3.06.42-.14.42-.31v-1.1c-1.8'
      + '.39-2.16-.85-2.16-.85-.3-.74-.72-.94-.72-.94-.58-.4.05-.39.05-.39'
      + '.64.05.98.66.98.66.57.98 1.5.7 1.87.53.06-.41.22-.7.4-.86-1.43-.16'
      + '-2.94-.72-2.94-3.2 0-.7.25-1.28.66-1.73-.07-.16-.29-.82.06-1.7 0 0'
      + '.54-.17 1.76.66a6.1 6.1 0 013.2 0c1.22-.83 1.76-.66 1.76-.66.35.88'
      + '.13 1.54.06 1.7.41.45.66 1.03.66 1.73 0 2.49-1.51 3.04-2.95 3.2'
      + '.23.2.44.6.44 1.21v1.8c0 .17.12.38.44.31A6.4 6.4 0 008 1.6z"/>'
      + '</svg>',
  },
  "reddit.com": {
    farbe: "#ff4500",
    svg: '<svg viewBox="0 0 16 16" aria-hidden="true" fill="#fff">'
      + '<circle cx="8" cy="9.2" r="5.2"/>'
      + '<circle cx="12.6" cy="3.6" r="1.3"/>'
      + '<circle cx="6.2" cy="8.6" r="0.85" fill="#ff4500"/>'
      + '<circle cx="9.8" cy="8.6" r="0.85" fill="#ff4500"/>'
      + '<path d="M5.9 11.2c1.2.9 3 .9 4.2 0" stroke="#ff4500" '
      + 'stroke-width="0.9" fill="none" stroke-linecap="round"/></svg>',
  },
  "pubmed.ncbi.nlm.nih.gov": {
    farbe: "#20558a",
    svg: '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" '
      + 'stroke="#fff" stroke-width="1.25" stroke-linejoin="round">'
      + '<path d="M2.4 3.4h4.3c.8 0 1.3.4 1.3 1v8c0-.6-.5-1-1.3-1H2.4z"/>'
      + '<path d="M13.6 3.4H9.3c-.8 0-1.3.4-1.3 1v8c0-.6.5-1 1.3-1h4.3z"/>'
      + '</svg>',
  },
  "stackoverflow.com": {
    farbe: "#f48024",
    svg: '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" '
      + 'stroke="#fff" stroke-width="1.4" stroke-linecap="round">'
      + '<path d="M4 11.4v2.2h8v-2.2"/>'
      + '<path d="M5.4 10.6l6-.7M5.6 8.4l5.8-1.4M6.3 6.2l5.3-2.3"/></svg>',
  },
  "tagesschau.de": {
    farbe: "#1b4f9c",
    svg: '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" '
      + 'stroke="#fff" stroke-width="1.3" stroke-linecap="round">'
      + '<rect x="2" y="4.2" width="12" height="8.4" rx="1.4"/>'
      + '<path d="M5.6 2.2L8 4.2l2.4-2"/></svg>',
  },
  "heise.de": {
    farbe: "#c00000",
    svg: '<svg viewBox="0 0 16 16" aria-hidden="true" fill="#fff">'
      + '<path d="M3.4 3h2v3.6h5.2V3h2v10h-2V8.6H5.4V13h-2z"/></svg>',
  },
};

// Zwei Adressen, ein Zeichen: de.wikipedia.org und en.wikipedia.org sollen
// dasselbe W bekommen, nicht ein "D" und ein "E".
function seitenzeichen(wirtname) {
  if (/(^|\.)wikipedia\.org$/i.test(wirtname)) return "wikipedia";
  return SEITENZEICHEN[wirtname.toLowerCase()] ? wirtname.toLowerCase() : "";
}

// Ein Schild je Seite. Fuer Wikipedia das W, sonst der Anfangsbuchstabe der
// Adresse auf farbigem Grund - so, wie es andere Dienste machen, wenn sie
// kein Favicon haben.
//
// Der Farbton wird aus dem Namen GERECHNET, nicht ausgewuerfelt: heise.de
// bekommt damit immer denselben Ton, und zwei verschiedene Seiten
// unterscheiden sich fast immer. Geladen wird dabei nichts.
function quellfarbe(name) {
  let summe = 0;
  for (let i = 0; i < name.length; i++) {
    summe = (summe * 31 + name.charCodeAt(i)) % 360;
  }
  return summe;
}

// geholt=true nur fuer Seiten, die Jarvis wirklich aufgemacht hat. Nur die
// duerfen ein Favicon nachladen; siehe die Begruendung weiter unten.
function quellschild(schluessel, geholt) {
  const schild = document.createElement("span");
  schild.className = "quellzeichen";
  schild.title = schluessel;
  const bekannt = schluessel === "wikipedia"
    ? "wikipedia" : seitenzeichen(schluessel);
  if (bekannt === "wikipedia") {
    schild.classList.add("wiki");
    schild.innerHTML = QUELLZEICHEN.wikipedia;
    return schild;
  }
  if (bekannt) {
    // innerHTML mit einer festen Zeichenkette AUS DIESER DATEI - nichts
    // davon kommt aus dem Netz oder aus dem Modell. Der Schluessel dient
    // nur als Nachschlagewort und wird nirgends eingesetzt.
    schild.classList.add("gezeichnet");
    schild.style.background = SEITENZEICHEN[bekannt].farbe;
    schild.innerHTML = SEITENZEICHEN[bekannt].svg;
    return schild;
  }
  // Fuer alles Uebrige: der Buchstabe steht SOFORT da, und darueber wird
  // das echte Favicon der Seite gelegt, sobald es da ist.
  //
  // Warum das doch geht, obwohl oben steht, es werde nichts geholt: ein
  // <img> LAEDT nichts herunter, es zeigt an - genau dasselbe Argument, mit
  // dem Jarvis Bilder in die Antwort setzen darf. Auf der Platte landet
  // nichts, der Virenschutz sieht keine Datei.
  //
  // Der ernstzunehmende Einwand war ein anderer: die Seite erfaehrt, dass
  // hier nach ihr gefragt wurde. Nur stimmt das schon vorher - Jarvis hat
  // sie ja gerade erst gelesen, vom selben Anschluss aus. Das Zeichen
  // verraet nichts, was die Seite nicht laengst weiss. referrerPolicy
  // sorgt dafuer, dass sie nicht auch noch erfaehrt, von welcher Seite aus.
  //
  // UND GENAU DA ENDET DIE BEGRUENDUNG - Einwand von Mini-Jost, und er
  // trifft. Sie gilt fuer Seiten, die Jarvis GEHOLT hat. Fuer blosse
  // SUCHTREFFER gilt sie nicht: search_web meldet jeden Treffer als
  // Quelle, auch die ungeprueften, und von denen kennt Jarvis nur den
  // Ausriss der Suchmaschine. Dort war niemand.
  //
  // Ein <img> an jeden Treffer haenge hiesse: eine Frage, fuenf
  // Verbindungen zu Seiten, die nie jemand geoeffnet hat. Die erfahren IP
  // und Zeitpunkt und koennen daraus schliessen, wonach gefragt wurde - bei
  // einer Medizinfrage genau die Sorte Angabe, die man nicht streut. Es
  // haette nebenbei aufgehoben, wofuer DuckDuckGo hier ueberhaupt benutzt
  // wird: dass die Suche selbst nichts protokolliert.
  //
  // Bei einem ungeprueften Treffer ist der Buchstabe ausserdem die
  // ehrlichere Anzeige - wir kennen die Seite ja nicht.
  //
  // KEIN Favicon-Dienst (google.com/s2/favicons und dergleichen): der
  // bekaeme jede besuchte Adresse gemeldet, und das waere deutlich
  // schlechter als der direkte Weg zur Seite selbst.
  schild.classList.add("buchstabe");
  const ton = quellfarbe(schluessel);
  schild.style.background = `hsl(${ton} 55% 38%)`;
  const initiale = document.createElement("span");
  initiale.className = "initiale";
  // Kein innerHTML mit dem Namen: der kommt aus einem Suchtreffer, also
  // mittelbar aus dem Netz.
  initiale.textContent = (schluessel[0] || "?").toUpperCase();
  schild.appendChild(initiale);

  // Nur echte Rechnernamen, und nur geholte Seiten. Der Wert kommt aus
  // wirt(), also aus new URL() - trotzdem geprueft, bevor er in eine
  // Adresse geschrieben wird.
  if (geholt
      && /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9-]+)+$/i.test(schluessel)) {
    const bild = document.createElement("img");
    bild.className = "quellfavicon";
    bild.alt = "";
    bild.loading = "lazy";
    bild.decoding = "async";
    bild.referrerPolicy = "no-referrer";
    // Der Buchstabe bleibt liegen und wird nur verdeckt: kommt nichts,
    // faellt es auf ihn zurueck, ohne dass ein Loch entsteht.
    bild.onload = () => {
      if (bild.naturalWidth > 1) schild.classList.add("hatzeichen");
      else bild.remove();
    };
    bild.onerror = () => bild.remove();
    bild.src = "https://" + schluessel + "/favicon.ico";
    schild.appendChild(bild);
  }
  return schild;
}

let quellen = [];

function quelleNotieren(roh) {
  let q;
  try { q = JSON.parse(roh); } catch (e) { return; }
  if (!q || typeof q.titel !== "string") return;
  // Nur http und https. Die Adressen kommen aus Suchtreffern, also aus dem
  // Netz - ein "javascript:" daraus in ein href zu schreiben waere genau
  // die Luecke, die verbote.py sonst schliesst.
  const ziel = typeof q.url === "string" ? q.url : "";
  const erlaubt = /^https?:\/\//i.test(ziel) ? ziel : "";
  if (quellen.some((a) => a.titel === q.titel && a.url === erlaubt)) return;
  // Die ART bleibt erhalten, und das ist keine Kosmetik. "seite" und
  // "wikipedia" hat Jarvis wirklich geholt; "web" ist ein blosser
  // Suchtreffer, von dem er nur den Ausriss der Suchmaschine kennt - dort
  // war niemand. Weiter unten entscheidet genau das, ob ein Favicon
  // nachgeladen werden darf.
  //
  // Vorher wurde hier alles auf "seite" eingedampft. Der Unterschied war
  // damit weg, noch bevor ihn jemand auswerten konnte.
  const art = q.art === "wikipedia" ? "wikipedia"
            : q.art === "seite" ? "seite" : "web";
  quellen.push({ art, titel: q.titel, url: erlaubt });
}

function wirt(url) {
  try { return new URL(url).hostname.replace(/^www\./, ""); }
  catch (e) { return ""; }
}

// Unter die fertige Antwort, eingeklappt. Ausgeklappt steht dort, worauf
// sich Jarvis gestuetzt hat - mit Verweis, damit man es nachlesen kann.
function quellenZeigen(inhaltEl) {
  if (!inhaltEl || !quellen.length) return;
  const blaseEl = inhaltEl.closest(".blase");
  const fuss = blaseEl && blaseEl.querySelector(".antwortfuss");
  if (!fuss) return;

  const kopf = document.createElement("button");
  kopf.className = "fussknopf quellenkopf";
  kopf.type = "button";
  kopf.setAttribute("aria-expanded", "false");

  const pfeil = document.createElement("span");
  pfeil.className = "gedachtpfeil";
  pfeil.textContent = "▸";
  const wort = document.createElement("span");
  wort.textContent = quellen.length === 1
    ? "1 Quelle" : `${quellen.length} Quellen`;
  kopf.append(pfeil, wort);

  // Eine Vorschau im eingeklappten Zustand - man sieht auf einen Blick, ob
  // er nachgeschlagen hat und wo. Gestapelt, wie man es von anderen
  // Diensten kennt.
  //
  // Die erste Fassung fasste nach ART zusammen, und es gibt nur zwei Arten
  // ("wikipedia" und "seite"). Fuenf verschiedene Webseiten bekamen also
  // denselben Globus, und mehr als zwei Zeichen gab es nie. Jetzt wird nach
  // SEITE unterschieden - drei Treffer von heise.de bleiben ein Zeichen,
  // heise.de und golem.de werden zwei.
  const vorschau = document.createElement("span");
  vorschau.className = "quellvorschau";
  // Je Seite EIN Eintrag. Wurde dieselbe Seite einmal geholt und einmal nur
  // als Treffer gemeldet, gilt "geholt" - dann war jemand dort, und das
  // Favicon verraet nichts Neues.
  const gezeigt = [];
  for (const q of quellen) {
    const schluessel = q.art === "wikipedia" ? "wikipedia" : wirt(q.url);
    if (!schluessel) continue;
    const geholt = q.art !== "web";
    const da = gezeigt.find((g) => g.schluessel === schluessel);
    if (da) da.geholt = da.geholt || geholt;
    else gezeigt.push({ schluessel, geholt });
  }
  for (const g of gezeigt.slice(0, 4)) {
    vorschau.appendChild(quellschild(g.schluessel, g.geholt));
  }
  if (gezeigt.length > 4) {
    const rest = document.createElement("span");
    rest.className = "quellrest";
    rest.textContent = "+" + (gezeigt.length - 4);
    vorschau.appendChild(rest);
  }
  kopf.appendChild(vorschau);

  const liste = document.createElement("ul");
  liste.className = "quellenliste";
  liste.hidden = true;

  for (const q of quellen) {
    const punkt = document.createElement("li");
    punkt.appendChild(quellschild(
      q.art === "wikipedia" ? "wikipedia" : (wirt(q.url) || "?"),
      q.art !== "web"));

    if (q.url) {
      const verweis = document.createElement("a");
      verweis.href = q.url;
      verweis.target = "_blank";
      // noopener: die geoeffnete Seite darf sonst ueber window.opener auf
      // diese hier zugreifen. referrer: sie soll nicht erfahren, von wo aus
      // sie geoeffnet wurde.
      verweis.rel = "noopener noreferrer";
      verweis.textContent = q.titel;
      punkt.appendChild(verweis);
      const ort = wirt(q.url);
      if (ort && ort !== q.titel) {
        const klein = document.createElement("span");
        klein.className = "quellort";
        klein.textContent = ort;
        punkt.appendChild(klein);
      }
    } else {
      const nur = document.createElement("span");
      nur.textContent = q.titel;
      punkt.appendChild(nur);
    }
    liste.appendChild(punkt);
  }

  kopf.addEventListener("click", () => {
    liste.hidden = !liste.hidden;
    kopf.setAttribute("aria-expanded", String(!liste.hidden));
    pfeil.textContent = liste.hidden ? "▸" : "▾";
  });

  // Der Knopf in die Leiste, die Liste darunter - sonst schoebe sie beim
  // Ausklappen die anderen Knoepfe zur Seite.
  fuss.appendChild(kopf);
  fuss.insertAdjacentElement("afterend", liste);
}

function werkzeugNotieren(name) {
  if (name && !benutzteWerkzeuge.includes(name)) benutzteWerkzeuge.push(name);
}

// Aus "Jarvis denkt" wird "Jarvis hat gedacht" - zugeklappt, ohne Reaktor,
// anklickbar. Wer es nicht braucht, sieht eine Zeile; wer wissen will, wie
// die Antwort zustande kam, klappt sie auf.
// Die Zeile erscheint IMMER - auch wenn es nichts aufzuklappen gibt.
//
// Vorher verschwand sie, sobald das Modell ohne Werkzeug und ohne lautes
// Denken geantwortet hatte. Das war als Zurückhaltung gemeint und wirkte
// wie ein Wackelkontakt: bei "wer ist dein Entwickler" stand sie da, bei
// "wer ist er?" nicht, und niemand konnte sagen warum. Eine Anzeige, die
// mal da ist und mal nicht, ist schlechter als eine, die immer dasteht -
// selbst wenn sie manchmal nur "direkt beantwortet" sagt.
function denkenAbschliessen() {
  if (!denkblase) return;

  const div = denkblase;
  denkblase = null;
  div.className = "blase gedacht";
  div.innerHTML = "";
  const leer = !gedanken.length && !benutzteWerkzeuge.length;
  if (leer) div.classList.add("still");

  const kopf = document.createElement("button");
  kopf.className = "gedachtkopf";
  kopf.setAttribute("aria-expanded", "false");
  const pfeil = document.createElement("span");
  pfeil.className = "gedachtpfeil";
  pfeil.textContent = "▸";
  const beschriftung = document.createElement("span");
  const anzahl = benutzteWerkzeuge.length;
  if (leer) {
    beschriftung.textContent = "Direkt beantwortet";
    kopf.title = "Kein Werkzeug, kein Zwischenschritt - "
      + "die Antwort stand sofort fest";
  } else {
    beschriftung.textContent = "Jarvis hat gedacht"
      + (anzahl ? ` · ${anzahl} ${anzahl === 1 ? "Werkzeug" : "Werkzeuge"}` : "");
  }
  kopf.append(pfeil, beschriftung);

  const koerper = document.createElement("div");
  koerper.className = "gedachtkoerper";
  koerper.hidden = true;

  if (leer) {
    const p = document.createElement("p");
    p.className = "gedanke";
    p.textContent = "Ohne Werkzeug und ohne Zwischenschritt beantwortet. "
      + "Das kommt bei kurzen Rückfragen vor, deren Antwort schon im "
      + "Gespräch stand.";
    koerper.appendChild(p);
  }

  if (benutzteWerkzeuge.length) {
    const zeile = document.createElement("div");
    zeile.className = "werkzeugzeile";
    for (const name of benutzteWerkzeuge) {
      const marke = document.createElement("code");
      marke.className = "werkzeug";
      marke.textContent = name;
      marke.title = werkzeugName(name);
      zeile.appendChild(marke);
    }
    koerper.appendChild(zeile);
  }

  for (const stueck of gedanken) {
    const p = document.createElement("p");
    p.className = "gedanke";
    gedankeSetzen(p, stueck);
    koerper.appendChild(p);
  }

  kopf.addEventListener("click", () => {
    koerper.hidden = !koerper.hidden;
    pfeil.textContent = koerper.hidden ? "▸" : "▾";
    kopf.setAttribute("aria-expanded", String(!koerper.hidden));
  });

  div.append(kopf, koerper);
}

// Werkzeugnamen im Gedankengang hervorheben - sie sind die Stellen, an denen
// aus Ueberlegung eine Handlung wird.
function gedankeSetzen(ziel, text) {
  const namen = Object.keys(WERKZEUGWORTE);
  const muster = new RegExp(`\\b(${namen.join("|")})\\b`, "g");
  let pos = 0, treffer;
  while ((treffer = muster.exec(text)) !== null) {
    if (treffer.index > pos) {
      ziel.appendChild(document.createTextNode(text.slice(pos, treffer.index)));
    }
    const marke = document.createElement("code");
    marke.className = "werkzeug";
    marke.textContent = treffer[0];
    marke.title = WERKZEUGWORTE[treffer[0]] || "";
    ziel.appendChild(marke);
    pos = treffer.index + treffer[0].length;
  }
  if (pos < text.length) {
    ziel.appendChild(document.createTextNode(text.slice(pos)));
  }
}

function denkenWeg() {
  if (denkblase) { denkblase.remove(); denkblase = null; }
}

function naechstesDenkwort() {
  // Reihum statt zufaellig: zweimal hintereinander dasselbe Wort sieht aus
  // wie ein haengengebliebener Bildschirm.
  denkwortIndex = (denkwortIndex + 1) % DENKWORTE.length;
  return DENKWORTE[denkwortIndex];
}

function status(text) {
  const feld = $("#status");
  feld.textContent = text || "";
  feld.classList.toggle("leer", !text);
}

// --- Bilder im Eingabefeld -------------------------------------------------
// Ein eingefügtes Bild wird vom Bildmodell beschrieben; die Beschreibung geht
// als Text mit an Jarvis. So versteht auch ein reines Textmodell, was drauf ist.
let anhaenge = [];

function anhaengeZeichnen() {
  const ziel = $("#anhaenge");
  ziel.innerHTML = "";
  anhaenge.forEach((a, i) => {
    const kasten = document.createElement("div");
    kasten.className = "anhang";
    kasten.innerHTML = `<img src="${a.uri}"><button title="Entfernen">×</button>`;
    kasten.querySelector("button").onclick = () => {
      anhaenge.splice(i, 1); anhaengeZeichnen();
    };
    ziel.appendChild(kasten);
  });
}

function bildAufnehmen(datei) {
  const leser = new FileReader();
  leser.onload = () => { anhaenge.push({ uri: leser.result }); anhaengeZeichnen(); };
  leser.readAsDataURL(datei);
}

$("#eingabe").addEventListener("paste", (e) => {
  for (const stueck of e.clipboardData.items)
    if (stueck.type.startsWith("image/")) { bildAufnehmen(stueck.getAsFile()); e.preventDefault(); }
});
document.addEventListener("dragover", (e) => e.preventDefault());
document.addEventListener("drop", (e) => {
  e.preventDefault();
  for (const datei of e.dataTransfer.files)
    if (datei.type.startsWith("image/")) bildAufnehmen(datei);
});

async function bilderBeschreiben() {
  if (!anhaenge.length) return "";
  status("Jarvis sieht sich das Bild an …");
  const teile = [];
  for (const a of anhaenge) {
    try {
      const r = await (await fetch("/api/bild", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bild: a.uri }),
      })).json();
      teile.push(r.beschreibung || r.fehler || "(nicht erkannt)");
    } catch (e) { teile.push("(Bild nicht auswertbar)"); }
  }
  return teile.join(" ");
}

async function senden() {
  const eingegeben = $("#eingabe").value.trim();
  if ((!eingegeben && !anhaenge.length) || laeuft) return;

  const bilder = anhaenge.slice();
  $("#eingabe").value = "";
  $("#eingabe").style.height = "auto";

  const duZiel = blase("DU", eingegeben);
  for (const a of bilder) {
    const img = document.createElement("img");
    img.className = "bild"; img.src = a.uri;
    duZiel.appendChild(img);
  }

  laeuft = true;
  $("#senden").disabled = true;
  $("#stopp").disabled = false;

  let beschreibung = "";
  if (bilder.length) {
    beschreibung = await bilderBeschreiben();
    anhaenge = []; anhaengeZeichnen();
  }
  const text = beschreibung
    ? `${eingegeben || "Was ist auf diesem Bild?"}\n\n[Auf dem mitgeschickten `
      + `Bild ist zu sehen: ${beschreibung}]`
    : eingegeben;
  await fragen(text);
}

async function fragen(text) {
  laeuft = true;
  $("#senden").disabled = true;
  $("#stopp").disabled = false;
  gedanken = [];
  benutzteWerkzeuge = [];
  quellen = [];
  denkenZeigen(naechstesDenkwort() + " …");

  let ziel = null;
  // Waehrend des Stroms bleibt es reiner Text - Bilder werden erst am Ende
  // eingesetzt, wenn die Adresse vollstaendig da ist. Auf halbem Weg waere
  // "![Dom](https://beispiel.de/bi" nur eine kaputte Anfrage.
  let rohtext = "";
  try {
    const antwort = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // Wird diese Antwort gleich vorgelesen? Danach richtet sich, ob
      // Jarvis knapp und zeichenlos antwortet oder gegliedert mit Markdown.
      // In den Stimmmodi spricht er von selbst (siehe unten), im Textmodus
      // erst auf Knopfdruck - dort ist eine vorgelesene Aufzaehlung kein
      // Argument gegen Struktur.
      body: JSON.stringify({ text, gesprochen: modus !== "text" }),
    });

    // Slash-Befehle laufen auf dem Rechner und antworten in einem Stueck -
    // kein Strom, kein Modell. Vorher kannte die Oberflaeche sie gar nicht,
    // und "/clear" ging als Frage an Jarvis, der daraufhin behauptete, er
    // haette die Konversation geloescht.
    if ((antwort.headers.get("content-type") || "").includes("json")) {
      const d = await antwort.json();
      denkenWeg();
      if (d.leeren) $("#verlauf").innerHTML = "";
      if (d.text) blase("SYSTEM", d.text, "system");
      if (d.chats_neu) chatsLaden();
      $("#verlauf").scrollTop = $("#verlauf").scrollHeight;
      laeuft = false;
      status("");
      $("#senden").disabled = false;
      $("#stopp").disabled = true;
      return;
    }

    const leser = antwort.body.getReader();
    const dekoder = new TextDecoder();
    let puffer = "";

    while (true) {
      const { done, value } = await leser.read();
      if (done) break;
      puffer += dekoder.decode(value, { stream: true });
      const zeilen = puffer.split("\n\n");
      puffer = zeilen.pop();
      for (const roh of zeilen) {
        if (!roh.startsWith("data: ")) continue;
        const nachricht = JSON.parse(roh.slice(6));
        if (nachricht.typ === "status") {
          const w = nachricht.wert;
          if (w === "denkt") {
            denkenZeigen(naechstesDenkwort() + " …");
          } else if (w.startsWith("quelle:")) {
            quelleNotieren(w.slice(7));
          } else if (w.startsWith("werkzeug:")) {
            const werkzeug = w.slice(9).trim();
            werkzeugNotieren(werkzeug);
            denkenZeigen("Jarvis " + werkzeugwort(werkzeug) + " …");
          } else if (w.startsWith("info:")) {
            denkenZeigen(w.slice(5));
          } else if (w.startsWith("wartet:")) {
            denkenZeigen(wartewort(w.slice(7)));
          }
        } else if (nachricht.typ === "denken") {
          gedankeDazu(nachricht.wert);
        } else if (nachricht.typ === "text") {
          // Sobald das erste Wort der Antwort kommt, wird aus dem Reaktor
          // die zugeklappte Zeile "Jarvis hat gedacht" - sie bleibt stehen,
          // damit man nachsehen kann, wie die Antwort zustande kam.
          if (!ziel) {
            denkenAbschliessen();
            ziel = blase("JARVIS", "");
            rohtext = "";
          }
          rohtext += nachricht.wert;
          ziel.textContent = rohtext;
          $("#verlauf").scrollTop = $("#verlauf").scrollHeight;
        } else if (nachricht.typ === "sprich") {
          // Vorgelesene Fremdnachricht: wird gesprochen, steht aber nicht im
          // Verlauf - und ist nie durch das Modell gegangen.
          Stimme.sprich(nachricht.wert, () => {});
          const hinweis = document.createElement("div");
          hinweis.className = "trenner";
          hinweis.textContent = "vorgelesen";
          $("#verlauf").appendChild(hinweis);
          $("#verlauf").scrollTop = $("#verlauf").scrollHeight;
        } else if (nachricht.typ === "fremdtext") {
          // Fremder Text im Fenster - NICHT durch das Modell gegangen und
          // nicht im Verlauf. Deshalb sichtbar abgesetzt: man soll sehen,
          // wo er anfaengt und wo er aufhoert. Alles als Textknoten, nie
          // als HTML - es ist ja gerade der Text, dem niemand traut.
          const kasten = document.createElement("div");
          kasten.className = "fremdtext";
          const kopf = document.createElement("div");
          kopf.className = "fremdkopf";
          kopf.textContent = nachricht.kopf || "Fremder Text";
          const koerper = document.createElement("div");
          koerper.className = "fremdkoerper";
          koerper.textContent = nachricht.wert || "";
          const fuss = document.createElement("div");
          fuss.className = "fremdfuss";
          fuss.textContent = "nicht durch Jarvis gegangen";
          kasten.append(kopf, koerper, fuss);
          $("#verlauf").appendChild(kasten);
          $("#verlauf").scrollTop = $("#verlauf").scrollHeight;
        } else if (nachricht.typ === "fehler") {
          denkenWeg();
          blase("FEHLER", nachricht.wert, "fehler");
        }
      }
    }
  } catch (e) {
    denkenWeg();
    blase("FEHLER", String(e), "fehler");
  }

  if (ziel && rohtext) {
    inhaltSetzen(ziel, rohtext);      // jetzt erst die Bilder
    $("#verlauf").scrollTop = $("#verlauf").scrollHeight;
  }
  // Die Quellenzeile erst jetzt: waehrend des Stroms wuerde sie mit jedem
  // Werkzeugaufruf neu wachsen und unter der halbfertigen Antwort zappeln.
  quellenZeigen(ziel);

  // Sicherheitsnetz: kommt gar keine Antwort - abgebrochen, Verbindung weg -,
  // darf der Reaktor nicht ewig weiterdrehen. Gedachtes bleibt trotzdem
  // stehen; gerade wenn keine Antwort kam, ist es das Einzige, woran man
  // sieht, was er versucht hat.
  denkenAbschliessen();
  denkenWeg();
  laeuft = false;
  status("");
  $("#senden").disabled = false;
  $("#stopp").disabled = true;
  zustandLaden();

  // In den Stimmmodi wird die fertige Antwort vorgelesen; danach hört das
  // freie Sprechen von selbst weiter zu.
  const gesagt = ziel ? ziel.textContent.trim() : "";
  if (modus !== "text" && gesagt) {
    strichetext("spricht");
    Stimme.sprich(gesagt, () => {
      strichetext(modus === "frei" ? "hört zu" : "bereit");
      if (modus === "frei") zuhoerenStarten(true);
    });
  } else if (modus === "frei") {
    zuhoerenStarten(true);
  }
}

$("#senden").onclick = senden;
$("#stopp").onclick = () => {
  fetch("/api/abbruch", { method: "POST" });
  Stimme.stopp();
  if (Ohren.laeuft()) Ohren.stoppen();
  strichetext("bereit");
};

// --- Zuhören ---------------------------------------------------------------
function mikroAus() {
  $$("#mikro, #mikro-frei").forEach((k) => k.classList.remove("laeuft"));
  $("#striche").classList.remove("hoert");
}

async function zuhoerenStarten(automatisch) {
  if (Ohren.laeuft() || laeuft) return;
  $$("#mikro, #mikro-frei").forEach((k) => k.classList.add("laeuft"));
  $("#striche").classList.add("hoert");
  strichetext("hört zu");
  status("Jarvis hört zu …");
  if (modus === "frei") gehoertSetzen("", "hoert");

  const lief = await Ohren.starten(async (text) => {
    mikroAus();
    status("");
    if (!text) {
      strichetext("bereit");
      if (modus === "frei") gehoertSetzen("", "nichts");
      if (automatisch && modus === "frei") setTimeout(() => zuhoerenStarten(true), 400);
      return;
    }
    if (modus === "text") {           // im Textmodus nur einfüllen
      $("#eingabe").value = ($("#eingabe").value + " " + text).trim();
      $("#eingabe").focus();
    } else {
      if (modus === "frei") gehoertSetzen(text, "denkt");
      blase("DU", text);
      strichetext("denkt");
      await fragen(text);
    }
  }, automatisch || modus === "frei");

  // Kam die Aufnahme gar nicht zustande, muss das Rot sofort wieder weg.
  // Sonst bleibt es stehen, laeuft() meldet trotzdem false, und der
  // naechste Klick versucht erneut zu starten statt zu stoppen - das
  // Symbol liess sich dann nicht mehr ausschalten.
  if (!lief) {
    mikroAus();
    status("");
    strichetext("bereit");
    if (modus === "frei") gehoertSetzen("", "wartet");
  }
}

// --- Was vorher war --------------------------------------------------------
// Jarvis erinnert sich über Neustarts hinweg - die Oberfläche tat es nicht.
// Am Handy sah man ein leeres Fenster und bekam Antworten auf ein Gespräch,
// das man nicht sehen konnte.
function tagName(datum) {
  const heute = new Date();
  const gestern = new Date(heute.getTime() - 86400000);
  const gleich = (a, b) => a.toDateString() === b.toDateString();
  if (gleich(datum, heute)) return "Heute";
  if (gleich(datum, gestern)) return "Gestern";
  return datum.toLocaleDateString("de-DE",
    { weekday: "long", day: "2-digit", month: "long" });
}

function trenner(text) {
  const d = document.createElement("div");
  d.className = "trenner";
  d.textContent = text;
  $("#verlauf").appendChild(d);
}

// Gibt zurueck, ob etwas geladen wurde - danach entscheidet sich, ob die
// Begruessung noch sinnvoll ist.
async function verlaufLaden() {
  let eintraege;
  try {
    const d = await (await fetch("/api/verlauf?anzahl=30")).json();
    eintraege = d.eintraege || [];
  } catch (e) { return false; }
  if (!eintraege.length) return false;

  let letzterTag = "";
  for (const e of eintraege) {
    const wann = new Date(e.zeit);
    const tag = tagName(wann);
    if (tag !== letzterTag) { trenner(tag); letzterTag = tag; }
    const div = blase(e.rolle === "du" ? "DU" : "JARVIS", e.text);
    // Marke fuer "vor diesem Seitenaufruf". Sie wird NICHT mehr gedaempft -
    // das machte den halben Verlauf schlecht lesbar. Den Schnitt zeigen die
    // Datumstrenner und das "jetzt" darunter.
    div.closest(".blase").classList.add("frueher");
    div.closest(".blase").title =
      wann.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  }
  trenner("jetzt");
  $("#verlauf").scrollTop = $("#verlauf").scrollHeight;
  return true;
}

// --- Chats ------------------------------------------------------------------
// Ein Chat ist ein eigener Gespraechsfaden. Der Bildschirm zeigt immer genau
// einen; die anderen bleiben liegen, bis man sie anklickt.
async function chatsLaden() {
  let d;
  try {
    d = await (await fetch("/api/chats")).json();
  } catch (e) { return; }

  const ul = $("#chats");
  ul.innerHTML = "";
  const chats = d.chats || [];
  if (chats.length === 0) {
    const leer = document.createElement("li");
    leer.className = "chat-leer";
    leer.textContent = "Noch keine Chats. Starte eine Unterhaltung, damit sie hier angezeigt wird.";
    ul.appendChild(leer);
    return;
  }
  for (const chat of chats) {
    const li = document.createElement("li");
    if (chat.aktiv) li.classList.add("an");

    const knopf = document.createElement("button");
    knopf.className = "chatname";
    knopf.textContent = chat.titel || "Ohne Titel";
    knopf.title = `${chat.anzahl} Nachrichten`;
    knopf.addEventListener("click", () => chatOeffnen(chat.id));
    knopf.addEventListener("dblclick", (e) => {
      e.preventDefault();
      umbenennenBeginnen(li, chat);
    });

    const zahl = document.createElement("span");
    zahl.className = "chatzahl";
    zahl.textContent = chat.anzahl;

    // Frueher stand hier ein "×", und Umbenennen ging nur per Doppelklick -
    // also gar nicht, weil niemand das errät. Jetzt fuehren beide Wege
    // ueber denselben Knopf.
    const mehr = document.createElement("button");
    mehr.className = "chatmehr";
    mehr.textContent = "⋯";
    mehr.title = "Umbenennen oder löschen";
    mehr.setAttribute("aria-label", "Mehr zu diesem Chat");
    mehr.addEventListener("click", (e) => {
      e.stopPropagation();          // sonst oeffnet der Klick den Chat
      menueZeigen(li, chat, mehr);
    });

    li.append(knopf, zahl, mehr);
    ul.appendChild(li);
  }
}

// Das kleine Menue hinter den drei Punkten. Es steht IN der Zeile, wie die
// Loeschrueckfrage und das Umbenennfeld - aus demselben Grund: was der
// Browser selbst anbietet (confirm, prompt), laesst sich abschalten, und
// dann tut der Knopf stillschweigend nichts.
function menueZeigen(li, chat, knopf) {
  const offen = li.querySelector(".chatmenue");
  menuesSchliessen();
  if (offen) return;                      // derselbe Knopf schliesst wieder

  const menue = document.createElement("div");
  menue.className = "chatmenue";

  const eintrag = (text, tun) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = text;
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      menue.remove();
      tun();
    });
    return b;
  };

  const loeschen = eintrag("Löschen", () => loeschenFragen(li, chat));
  loeschen.className = "chatgefahr";
  menue.append(eintrag("Umbenennen", () => umbenennenBeginnen(li, chat)),
               loeschen);
  li.appendChild(menue);
  knopf.setAttribute("aria-expanded", "true");
  menue.querySelector("button").focus();
}

function menuesSchliessen() {
  document.querySelectorAll(".chatmenue").forEach((m) => m.remove());
  document.querySelectorAll(".chatmehr[aria-expanded]")
    .forEach((k) => k.removeAttribute("aria-expanded"));
}

// Ein Klick irgendwo sonst schliesst das Menue, Escape auch. Ohne das bleibt
// es offen stehen, waehrend man laengst woanders ist.
document.addEventListener("click", (e) => {
  if (!e.target.closest(".chatmenue, .chatmehr")) menuesSchliessen();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") menuesSchliessen();
});

// Die Rueckfrage steht IN der Zeile, nicht in einem Browserdialog. Grund:
// confirm() laesst sich im Browser abschalten - Edge bietet nach dem ersten
// Dialog "Diese Seite daran hindern, weitere Dialoge zu erzeugen" an, und
// danach liefert confirm() stillschweigend false. Der Loeschknopf tat dann
// gar nichts, ohne dass irgendwo etwas stuende. Auf dem Handy sind solche
// Dialoge ausserdem unangenehm gross.
function loeschenFragen(li, chat) {
  if (li.querySelector(".chatfrage")) return;       // schon offen

  const frage = document.createElement("div");
  frage.className = "chatfrage";
  const text = document.createElement("span");
  text.textContent = chat.anzahl
    ? `${chat.anzahl} Nachrichten löschen?` : "Leeren Chat löschen?";

  const ja = document.createElement("button");
  ja.className = "chatja";
  ja.textContent = "Löschen";
  const nein = document.createElement("button");
  nein.className = "chatnein";
  nein.textContent = "Abbrechen";

  const zu = () => frage.remove();
  nein.addEventListener("click", (e) => { e.stopPropagation(); zu(); });
  ja.addEventListener("click", async (e) => {
    e.stopPropagation();
    ja.disabled = nein.disabled = true;
    ja.textContent = "…";
    await chatLoeschen(chat);
  });

  frage.append(text, ja, nein);
  li.appendChild(frage);
  ja.focus();
}

async function chatOeffnen(id) {
  try {
    await fetch("/api/chats/wechseln", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
  } catch (e) { return; }
  $("#verlauf").innerHTML = "";
  await verlaufLaden();
  chatsLaden();
}

async function chatNeu() {
  try {
    await fetch("/api/chats", { method: "POST" });
  } catch (e) { return; }
  $("#verlauf").innerHTML = "";
  blase("SYSTEM", "Neuer Chat. Das vorige Gespräch steht links.", "system");
  chatsLaden();
}

// Umbenannt wird an Ort und Stelle - aus demselben Grund wie beim Loeschen:
// prompt() laesst sich im Browser abschalten, und dann passiert nichts.
function umbenennenBeginnen(li, chat) {
  if (li.querySelector(".chatfeld")) return;

  const feld = document.createElement("input");
  feld.className = "chatfeld";
  feld.value = chat.titel || "";
  feld.maxLength = 60;
  const knopf = li.querySelector(".chatname");
  knopf.replaceWith(feld);
  feld.focus();
  feld.select();

  let fertig = false;
  const abschliessen = async (speichern) => {
    if (fertig) return;
    fertig = true;
    const titel = feld.value.trim();
    if (speichern && titel && titel !== chat.titel) {
      try {
        await fetch("/api/chats/umbenennen", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: chat.id, titel }),
        });
      } catch (e) { /* die Liste zeigt gleich den alten Namen */ }
    }
    chatsLaden();
  };

  feld.addEventListener("keydown", (e) => {
    e.stopPropagation();
    if (e.key === "Enter") { e.preventDefault(); abschliessen(true); }
    if (e.key === "Escape") { e.preventDefault(); abschliessen(false); }
  });
  feld.addEventListener("blur", () => abschliessen(true));
  feld.addEventListener("click", (e) => e.stopPropagation());
}

async function chatLoeschen(chat) {
  let d;
  try {
    const r = await fetch("/api/chats/loeschen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: chat.id }),
    });
    if (!r.ok) throw new Error(`Server antwortete mit ${r.status}`);
    d = await r.json();
  } catch (e) {
    // Vorher verschluckte ein leeres catch den Fehler, und der Knopf sah
    // aus, als taete er nichts.
    blase("FEHLER", `Löschen fehlgeschlagen: ${e.message}`, "fehler");
    chatsLaden();
    return;
  }
  $("#verlauf").innerHTML = "";
  await verlaufLaden();
  blase("SYSTEM", d.geloescht
        ? `Gelöscht: ${d.geloescht} Nachrichten. Sie liegen in `
          + `data/geloescht.jsonl, falls es ein Fehlgriff war.`
        : "Chat gelöscht - er war leer.", "system");
  chatsLaden();
}

$("#chat-neu").addEventListener("click", chatNeu);

// Auch beim freien Sprechen muss man zurück zur Tastatur kommen - ohne
// Ausweg wäre der Modus eine Falle.
$("#gehoert-zurueck").addEventListener("click", () => modusSetzen("text"));

// Und das Mikrofon muss von Hand anstoßbar bleiben. Beim freien Sprechen
// ist die Eingabezeile ausgeblendet, und mit ihr verschwand der einzige
// Mikrofonknopf - dann lief das Zuhören zwar von selbst an, aber wenn es
// einmal stehenblieb, gab es keinen Weg zurück.
$("#mikro-frei").addEventListener("click", () => {
  if (Ohren.laeuft()) { Ohren.stoppen(); return; }
  zuhoerenStarten(false);
});

// --- Hört der Rechner? -------------------------------------------------------
// Ein Text, der "Weckwort bereit" behauptet, ist keine Auskunft: er sieht bei
// einem stummen Mikrofon genauso aus wie bei einem funktionierenden. Deshalb
// zwei Balken - was ankommt, und wie nah das Weckwort gerade war. Wer "Hey
// Jarvis" sagt und sieht, dass der zweite Balken auf halber Höhe stehenbleibt,
// weiß sofort: gehört ja, Schwelle zu hoch.
let ohrLetzteTreffer = 0;

// Gibt zurueck, ob die Ohrzeile ueberhaupt sichtbar ist. Danach richtet
// sich, wie oft wieder gefragt wird: ist das Weckwort aus, sieht man den
// Pegel gar nicht, und viermal pro Sekunde danach zu fragen ist verschenkt.
async function ohrLaden() {
  let d;
  try {
    d = await (await fetch("/api/sprache")).json();
  } catch (e) { return false; }

  const w = d.weckwort || {};
  const zeile = $("#ohrzeile");
  if (!w.an) { zeile.hidden = true; return false; }
  zeile.hidden = false;

  const p = w.pegel || {};
  // Sprache liegt grob zwischen 0,01 und 0,2 - deshalb nicht linear, sonst
  // zappelt der Balken im untersten Zwanzigstel und man sieht nichts.
  const laut = Math.min(1, Math.sqrt((p.jetzt || 0) / 0.15));
  $("#pegelbalken").style.width = (laut * 100).toFixed(0) + "%";
  $("#pegelbalken").classList.toggle("still", (p.jetzt || 0) < 0.002);

  const naehe = Math.min(1, p.naehe || 0);
  $("#naehebalken").style.width = (naehe * 100).toFixed(0) + "%";
  $("#naeheschwelle").style.left = ((w.schwelle || 0.4) * 100).toFixed(0) + "%";
  $("#naehebalken").classList.toggle("nah", naehe >= (w.schwelle || 0.4));

  $("#ohrwort").textContent = `„${w.wort || "Hey Jarvis"}“`;
  $("#ohrgeraet").textContent = w.geraet || "";
  $("#ohrgeraet").title = `Bisher ${w.treffer || 0}× erkannt`;

  // Die drei Striche bewegen sich mit, auch wenn der Browser nichts hört.
  // "Hey Jarvis" läuft am Rechner; ohne diese Leitung standen sie still,
  // während Jarvis zuhörte - das sah aus wie ein Defekt und war nur eine
  // fehlende Verbindung.
  if (!Ohren.laeuft() && !Stimme.spricht()) Stimme.vonAussen(p.jetzt || 0);

  if ((w.treffer || 0) > ohrLetzteTreffer) {
    ohrLetzteTreffer = w.treffer;
    zeile.classList.add("erkannt");
    // Beim Treffer die Striche zeigen, egal in welchem Modus - dann sieht
    // man, dass er wirklich zuhört, statt es nur zu lesen.
    $("#striche").hidden = false;
    $("#striche").classList.add("hoert");
    strichetext("hört zu");
    setTimeout(() => {
      zeile.classList.remove("erkannt");
      $("#striche").classList.remove("hoert");
      if (modus === "text") $("#striche").hidden = true;
      strichetext("bereit");
    }, 12000);
  }
  return true;
}

$("#mikro").onclick = () => {
  if (Ohren.laeuft()) { Ohren.stoppen(); return; }
  zuhoerenStarten(false);
};
// Frueher rief dieser Knopf /api/reset: Bildschirm leer, Jarvis' Kurzzeit-
// gedaechtnis leer - aber das Archiv unberuehrt, und beim naechsten Laden
// stand alles wieder da. Genau das hat im Gebrauch verwirrt. Jetzt faengt er
// einen neuen Chat an: der Bildschirm ist wirklich leer, und das vorige
// Gespraech ist nicht weg, sondern steht links in der Liste.
$("#leeren").onclick = chatNeu;

$("#eingabe").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); senden(); }
  if (e.key === "Escape" && laeuft) fetch("/api/abbruch", { method: "POST" });
});
$("#eingabe").addEventListener("input", function () {
  this.style.height = "auto";
  this.style.height = Math.min(this.scrollHeight, 160) + "px";
});

// --- Agenten ---------------------------------------------------------------
async function agentenLaden() {
  const d = await (await fetch("/api/agenten")).json();
  $("#agenten-kopf").textContent =
    `${d.laufend} von ${d.grenze} unterwegs · Prozess ${d.prozess_mb} MB · ` +
    `Zeitlimit ${d.zeitlimit} s`;
  $("#zahl-agenten").textContent = d.laufend;

  const ziel = $("#agentenliste");
  if (!d.agenten.length) {
    ziel.innerHTML = '<div class="leerhinweis">Der Hangar ist leer.</div>';
    return;
  }
  ziel.innerHTML = "";
  for (const a of d.agenten) {
    const farbe = { fertig: "gruen", arbeitet: "blau", abgebrochen: "rot",
                    gescheitert: "rot", gestoppt: "gelb" }[a.zustand] || "";
    const karte = document.createElement("div");
    karte.className = "karte";
    karte.innerHTML = `
      <div class="kopf">
        <b>${a.name}</b>
        <span class="marke ${farbe}">${a.zustand}</span>
        <span class="marke">${a.dauer} s</span>
        ${a.zeichen ? `<span class="marke">${Math.round(a.zeichen / 1000)}k Zeichen</span>` : ""}
        <span class="rechts"></span>
      </div>
      <div class="aufgabe"></div>
      ${a.bericht ? '<div class="bericht" style="margin-top:8px;color:var(--text-leise)"></div>' : ""}`;
    karte.querySelector(".aufgabe").textContent = a.aufgabe;
    if (a.bericht) karte.querySelector(".bericht").textContent = a.bericht;

    const rechts = karte.querySelector(".rechts");
    if (a.laeuft) {
      const k = document.createElement("button");
      k.className = "tat leise gefahr";
      k.textContent = "Stoppen";
      k.onclick = async () => {
        await fetch("/api/agenten/" + encodeURIComponent(a.name), { method: "DELETE" });
        agentenLaden();
      };
      rechts.appendChild(k);
    } else {
      const k = document.createElement("button");
      k.className = "tat leise";
      k.textContent = "Bericht abholen";
      k.onclick = async () => {
        const r = await (await fetch("/api/agenten/" + encodeURIComponent(a.name) + "/bericht")).json();
        blase("SYSTEM", r.bericht, "system");
        agentenLaden();
      };
      rechts.appendChild(k);
    }
    ziel.appendChild(karte);
  }
}

$("#agent-start").onclick = async () => {
  const aufgabe = $("#agent-aufgabe").value.trim();
  if (!aufgabe) return;
  const r = await (await fetch("/api/agenten", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aufgabe }),
  })).json();
  if (r.ok) $("#agent-aufgabe").value = "";
  else alert(r.meldung);
  agentenLaden();
};

// --- Werkzeuge -------------------------------------------------------------
let werkzeugAenderungen = {};

async function werkzeugeLaden() {
  const d = await (await fetch("/api/werkzeuge")).json();
  $("#zahl-werkzeuge").textContent = d.aktiv;
  werkzeugAenderungen = {};
  const ziel = $("#werkzeugliste");
  ziel.innerHTML = "";

  for (const w of d.werkzeuge) {
    const karte = document.createElement("div");
    karte.className = "karte";
    karte.innerHTML = `
      <div class="kopf">
        <b>${w.name}</b>
        ${w.geaendert ? '<span class="marke gelb">geändert</span>' : ""}
        <span class="rechts">
          <label class="schalter"><input type="checkbox" ${w.aktiv ? "checked" : ""}> aktiv</label>
        </span>
      </div>
      <label class="feld">
        <span class="name">Beschreibung – <b>danach entscheidet das Modell</b></span>
        <textarea rows="3"></textarea>
      </label>
      <div class="parameter"></div>`;

    const schalter = karte.querySelector("input[type=checkbox]");
    const beschreibung = karte.querySelector("textarea");
    beschreibung.value = w.beschreibung;

    const merken = () => {
      werkzeugAenderungen[w.name] = werkzeugAenderungen[w.name] || {};
      werkzeugAenderungen[w.name].aktiv = schalter.checked;
      if (beschreibung.value.trim() !== w.original)
        werkzeugAenderungen[w.name].beschreibung = beschreibung.value.trim();
      else delete werkzeugAenderungen[w.name].beschreibung;
    };
    schalter.onchange = merken;
    beschreibung.oninput = merken;

    const pziel = karte.querySelector(".parameter");
    if (!w.parameter.length) pziel.remove();
    for (const p of w.parameter) {
      const feld = document.createElement("div");
      feld.className = "feld";
      feld.innerHTML = `
        <span class="name"><b>${p.name}</b> · ${p.typ}${p.pflicht ? " · Pflicht" : ""}</span>
        <input type="text" class="pb" placeholder="Beschreibung">
        <input type="text" class="ps" placeholder="Standardwert (leer = keiner)" style="margin-top:5px">`;
      const pb = feld.querySelector(".pb");
      const ps = feld.querySelector(".ps");
      pb.value = p.beschreibung;
      ps.value = p.standard;
      const merkenP = () => {
        const e = werkzeugAenderungen[w.name] = werkzeugAenderungen[w.name] || {};
        e.aktiv = schalter.checked;
        e.parameter = e.parameter || {};
        const eintrag = {};
        if (pb.value.trim() && pb.value.trim() !== p.original)
          eintrag.beschreibung = pb.value.trim();
        if (ps.value.trim()) eintrag.standard = ps.value.trim();
        if (Object.keys(eintrag).length) e.parameter[p.name] = eintrag;
        else delete e.parameter[p.name];
      };
      pb.oninput = merkenP;
      ps.oninput = merkenP;
      pziel.appendChild(feld);
    }
    ziel.appendChild(karte);
  }
}

$("#werkzeuge-speichern").onclick = async () => {
  const sauber = {};
  for (const [name, e] of Object.entries(werkzeugAenderungen)) {
    const eintrag = {};
    if (e.aktiv === false) eintrag.aktiv = false;
    if (e.beschreibung) eintrag.beschreibung = e.beschreibung;
    if (e.parameter && Object.keys(e.parameter).length) eintrag.parameter = e.parameter;
    if (Object.keys(eintrag).length) sauber[name] = eintrag;
  }
  const r = await (await fetch("/api/werkzeuge", {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aenderungen: sauber }),
  })).json();
  $("#zahl-werkzeuge").textContent = r.aktiv;
  werkzeugeLaden();
};

$("#werkzeuge-zurueck").onclick = async () => {
  if (!confirm("Alle Änderungen an den Werkzeugen verwerfen?")) return;
  await fetch("/api/werkzeuge/zuruecksetzen", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: "" }),
  });
  werkzeugeLaden();
};

// --- Einstellungen ---------------------------------------------------------
async function einstellungenLaden() {
  const d = await (await fetch("/api/einstellungen")).json();
  const ziel = $("#envliste");
  ziel.innerHTML = "";
  const karte = document.createElement("div");
  karte.className = "karte";
  for (const e of d.eintraege) {
    const feld = document.createElement("label");
    feld.className = "feld";
    feld.innerHTML = `<span class="name"><b>${e.schluessel}</b>${
      e.erklaerung ? " · " + e.erklaerung : ""}</span>
      <input type="${e.geheim ? "password" : "text"}" data-k="${e.schluessel}">`;
    feld.querySelector("input").value = e.wert;
    karte.appendChild(feld);
  }
  ziel.appendChild(karte);
  envOffen = false;
  envStand("");
  modelleLaden();
  wachhundLaden();
}

async function wachhundSchicken(daten) {
  await fetch("/api/wachhund", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(daten),
  });
}

const WACH_FELDER = [
  ["anwesend", "Schweigt ab … Minuten Leerlauf", 60, "min"],
  ["pause", "Mindestabstand zwischen Meldungen", 60, "min"],
  ["ruhe_von", "Nachtruhe ab … Uhr", 1, ""],
  ["ruhe_bis", "Nachtruhe bis … Uhr", 1, ""],
  ["ram_prozent", "Arbeitsspeicher meldet ab … Prozent", 1, "%"],
  ["platte_gb", "Laufwerk meldet unter … Gigabyte", 1, "GB"],
  ["last_dauer", "Langer Vorgang ab … Minuten Last", 60, "min"],
  ["laufzeit_tage", "Neustart anregen nach … Tagen", 1, "Tage"],
];

async function wachhundLaden() {
  const d = await (await fetch("/api/wachhund")).json();
  $("#wachhund-regeln-kopf").textContent =
    "Jede Regel einzeln abschaltbar; die Sperrzeit sagt, wie oft sie " +
    "höchstens etwas sagen darf.";

  const ziel = $("#wachhundliste");
  ziel.innerHTML = "";

  for (const r of d.regeln) {
    const zeile = document.createElement("div");
    zeile.style.cssText = "display:flex;align-items:center;gap:10px;padding:5px 0";
    zeile.innerHTML = `
      <label class="schalter"><input type="checkbox" ${r.aktiv ? "checked" : ""}></label>
      <span style="flex:1">${r.beschreibung}</span>
      <input type="text" class="sperre" style="width:62px;text-align:right"
             value="${r.sperrzeit ? Math.round(r.sperrzeit / 60) : 0}">
      <span class="marke">min</span>
      ${r.dringend ? '<span class="marke gelb">auch nachts</span>' : ""}`;

    const schalter = zeile.querySelector("input[type=checkbox]");
    const sperre = zeile.querySelector(".sperre");
    const senden = () => wachhundSchicken({
      name: r.name, aktiv: schalter.checked,
      sperrzeit: (parseFloat(sperre.value) || 0) * 60,
    });
    schalter.onchange = senden;
    sperre.onchange = senden;
    ziel.appendChild(zeile);
  }

  const grenzen = document.createElement("div");
  grenzen.style.cssText = "margin-top:14px;padding-top:12px;" +
    "border-top:1px dashed var(--rand)";
  for (const [schluessel, name, teiler, einheit] of WACH_FELDER) {
    const zeile = document.createElement("div");
    zeile.style.cssText = "display:flex;align-items:center;gap:10px;padding:4px 0";
    zeile.innerHTML = `
      <span style="flex:1;font-size:13px">${name}</span>
      <input type="text" style="width:62px;text-align:right"
             value="${Math.round(d.werte[schluessel] / teiler)}">
      <span class="marke">${einheit || "Uhr"}</span>`;
    const feld = zeile.querySelector("input");
    feld.onchange = () => wachhundSchicken(
      { [schluessel]: (parseFloat(feld.value) || 0) * teiler });
    grenzen.appendChild(zeile);
  }
  ziel.appendChild(grenzen);
}

// --- Rückfragen ------------------------------------------------------------
let gezeigteFragen = new Set();

async function rueckfragenLaden() {
  const d = await (await fetch("/api/rueckfragen")).json();
  const ziel = $("#rueckfragen");
  const offen = new Set(d.fragen.map((f) => f.id));

  for (const kind of [...ziel.children])
    if (!offen.has(kind.dataset.id)) { kind.remove(); gezeigteFragen.delete(kind.dataset.id); }

  for (const f of d.fragen) {
    if (gezeigteFragen.has(f.id)) continue;
    gezeigteFragen.add(f.id);

    const karte = document.createElement("div");
    karte.className = "karte frage" + (f.art === "genehmigung" ? " freigabe" : "");
    karte.dataset.id = f.id;
    karte.innerHTML = `
      <div class="kopf">
        <span class="marke ${f.art === "genehmigung" ? "rot" : "blau"}">
          ${f.art === "genehmigung" ? "Freigabe" : "Frage"}</span>
        <b>${f.von}</b>
        <span class="rechts"><span class="marke rest">${f.rest}s</span></span>
      </div>
      <div class="text"></div>
      ${f.auswirkungen ? '<div class="folgen"></div>' : ""}
      <div class="knoepfe" style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap"></div>`;
    karte.querySelector(".text").textContent = f.text;
    if (f.auswirkungen)
      karte.querySelector(".folgen").textContent = "Folgen: " + f.auswirkungen;

    const knoepfe = karte.querySelector(".knoepfe");
    const antworten = async (wert) => {
      await fetch("/api/rueckfragen", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: f.id, antwort: wert }),
      });
      karte.remove(); gezeigteFragen.delete(f.id);
      blase("DU", wert);
    };

    f.optionen.forEach((o, i) => {
      const k = document.createElement("button");
      const ablehnen = /ablehn/i.test(o);
      k.className = "tat" + (ablehnen ? " leise gefahr" : i > 0 ? " leise" : "");
      k.textContent = o;
      k.onclick = () => antworten(o);
      knoepfe.appendChild(k);
    });

    if (f.art !== "genehmigung") {
      const eigen = document.createElement("input");
      eigen.type = "text";
      eigen.placeholder = "oder etwas anderes …";
      eigen.style.flex = "1 1 220px";
      eigen.onkeydown = (e) => {
        if (e.key === "Enter" && eigen.value.trim()) antworten(eigen.value.trim());
      };
      knoepfe.appendChild(eigen);
    }
    ziel.appendChild(karte);
    karte.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  for (const f of d.fragen) {
    const karte = [...ziel.children].find((k) => k.dataset.id === f.id);
    if (karte) karte.querySelector(".rest").textContent = f.rest + "s";
  }
}

async function modelleLaden() {
  const d = await (await fetch("/api/modelle")).json();
  const zeilen = d.ping.map((p) => {
    const farbe = p.zustand === "frei" ? "gruen" : "rot";
    const laeuft = p.modell === d.laeuft;
    return `<div class="zeile" style="border:0">
      <span style="width:22px">${laeuft ? "▶" : ""}</span>
      <span style="flex:1"><code>${p.modell}</code></span>
      <span class="marke ${farbe}">${p.zustand}</span>
      <span class="marke">${p.zustand === "frei" ? p.dauer.toFixed(1) + " s" : "–"}</span>
      ${laeuft ? "" : `<button class="tat leise" data-m="${p.modell}">nehmen</button>`}
    </div>`;
  }).join("");
  $("#modelltabelle").innerHTML = zeilen +
    `<div style="margin-top:8px;font-size:12px;color:var(--text-leise)">Regel: ${d.wahl}</div>`;
  $$("#modelltabelle button[data-m]").forEach((k) => {
    k.onclick = async () => {
      await fetch("/api/modelle/waehlen", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: k.dataset.m }),
      });
      modelleLaden(); zustandLaden();
    };
  });
}

$("#modelle-pingen").onclick = async () => {
  $("#modelltabelle").innerHTML = '<div class="leerhinweis">Pinge an …</div>';
  await fetch("/api/modelle/pingen", { method: "POST" });
  modelleLaden(); zustandLaden();
};

// Gemessen an einem echten Verlust: ein Mailzugang wurde zweimal
// eingetragen und kam nie an. Der Speicherweg war in Ordnung - geprueft,
// Oberflaeche -> .env -> Oberflaeche traegt. Abgeschickt wurde nur nie.
//
// Der Grund steht in der index.html: der Speichern-Knopf sass UEBER der
// Liste. Wer unten ein Feld ausfuellt, sieht ihn nicht mehr, tippt Enter -
// und nichts passiert, weil das hier kein Formular ist. Dann wechselt man
// den Bereich, und der Eintrag ist weg, ohne dass irgendwo etwas stand.
//
// Drei Gegenmassnahmen: ein zweiter Knopf unten, Enter speichert, und
// ungespeicherte Aenderungen sind sichtbar und werden beim Verlassen
// gemeldet.
let envOffen = false;

function envStand(text, warnend) {
  const feld = $("#env-stand");
  if (!feld) return;
  feld.textContent = text || "";
  feld.classList.toggle("warnung", !!warnend);
}

function envGeaendert() {
  envOffen = true;
  envStand("nicht gespeichert", true);
}

async function envSpeichern() {
  const eintraege = [...$$("#envliste input[data-k]")].map((i) => ({
    schluessel: i.dataset.k, wert: i.value,
  }));
  if (!eintraege.length) return;
  envStand("speichert …", false);
  let r;
  try {
    const antwort = await fetch("/api/einstellungen", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ eintraege }),
    });
    if (!antwort.ok) throw new Error("Server antwortete mit " + antwort.status);
    r = await antwort.json();
  } catch (e) {
    // Frueher verschluckte ein fehlendes catch den Fehler, und der Knopf
    // sah aus, als haette er gespeichert.
    envStand("FEHLER: " + e.message, true);
    return;
  }
  envOffen = false;
  envStand("gespeichert · " + (r.hinweis || ""), false);
}

$("#env-speichern").onclick = envSpeichern;
if ($("#env-speichern-unten")) $("#env-speichern-unten").onclick = envSpeichern;

// Enter im Feld speichert. Ohne das tippt man Enter, es passiert nichts,
// und man haelt es fuer erledigt.
$("#envliste").addEventListener("keydown", (e) => {
  if (e.target.matches("input[data-k]") && e.key === "Enter") {
    e.preventDefault();
    envSpeichern();
  }
});
$("#envliste").addEventListener("input", (e) => {
  if (e.target.matches("input[data-k]")) envGeaendert();
});

// Beim Wechsel in einen anderen Bereich nachfragen, statt stillschweigend
// zu verwerfen.
$$("nav button").forEach((knopf) => {
  knopf.addEventListener("click", () => {
    if (!envOffen || knopf.dataset.bereich === "einstellungen") return;
    if (confirm("Die Einstellungen sind nicht gespeichert. Jetzt speichern?")) {
      envSpeichern();
    } else {
      envOffen = false;
      envStand("");
    }
  });
});

// --- Protokoll -------------------------------------------------------------
async function protokollLaden(vonvorn) {
  if (vonvorn) { letzteProtokollNummer = 0; $("#protokollliste").innerHTML = ""; }
  const d = await (await fetch("/api/protokoll?ab=" + letzteProtokollNummer)).json();
  letzteProtokollNummer = d.letzte;
  $("#zahl-protokoll").textContent = d.letzte;
  const ziel = $("#protokollliste");
  for (const e of d.eintraege) {
    const zeile = document.createElement("div");
    zeile.className = "zeile";
    zeile.innerHTML = `<span class="zeit">${e.zeit}</span>
      <span class="art art-${e.art}">${e.art}</span>
      <span class="inhalt"></span>`;
    zeile.querySelector(".inhalt").textContent = e.text;
    ziel.appendChild(zeile);
  }
  if (!ziel.children.length)
    ziel.innerHTML = '<div class="leerhinweis">Noch nichts geschehen.</div>';
}

$("#protokoll-leeren").onclick = async () => {
  await fetch("/api/protokoll", { method: "DELETE" });
  protokollLaden(true);
};

// --- Kopfzeile -------------------------------------------------------------
async function zustandLaden() {
  try {
    const d = await (await fetch("/api/zustand")).json();
    $("#fuss-modell").textContent = d.modell.split("/").pop();
    $("#fuss-verlauf").textContent = d.verlauf;
    $("#fuss-speicher").textContent = d.prozess_mb;
    $("#zahl-agenten").textContent = d.agenten;
    $("#zahl-werkzeuge").textContent = d.werkzeuge;
    $("#zahl-protokoll").textContent = d.protokoll;
  } catch (e) { /* Server noch nicht bereit */ }
}

// Der Pegel muss oefter kommen als der Rest - ein Balken, der alle drei
// Sekunden nachzieht, taugt nicht zum Hineinsprechen. 250 ms reichen auch
// fuer die drei Striche: dazwischen glaettet die Anzeige selbst, sodass es
// fliessend aussieht statt zu springen.
//
// ABER NICHT MIT setInterval. Das feuert alle 250 ms, egal ob die vorige
// Anfrage schon zurueck ist. Am Rechner selbst kostet das nichts; ueber
// Tailscale - und dort laeuft die Verbindung zum iPad ueber einen Relais
// in Frankfurt, nicht direkt - hat jede Anfrage eine echte Umlaufzeit. Vier
// pro Sekunde stapeln sich dann, das Geraet kommt nie hinterher, und die
// Oberflaeche wirkt zaeh und fehlerhaft, obwohl der Server schnell
// antwortet. Gemeldet genau so vom iPad.
//
// Deshalb eine KETTE statt eines Takts: die naechste Anfrage geht erst los,
// wenn die vorige da ist. Stapeln ist damit unmoeglich. Und die Pause
// richtet sich nach der gemessenen Umlaufzeit - am Rechner bleibt es bei
// 250 ms, auf einer langsamen Leitung wird von selbst gebremst.
const OHR_SCHNELL = 250;      // am Rechner selbst
const OHR_RUHIG = 1500;       // Weckwort aus - dann reicht selten
const OHR_WEG = 5000;         // Tab im Hintergrund

let ohrLaeuft = false;

async function ohrSchleife() {
  if (ohrLaeuft) return;                     // doppelte Kette verhindern
  ohrLaeuft = true;
  let pause = OHR_SCHNELL;
  try {
    if (document.hidden) {
      pause = OHR_WEG;
    } else {
      const start = performance.now();
      const sichtbar = await ohrLaden();
      const umlauf = performance.now() - start;
      // Mindestens das Dreifache der Umlaufzeit warten. Bei 5 ms bleibt es
      // bei 250, bei 120 ms werden daraus 360 - die Leitung bekommt Luft,
      // statt sich zuzusetzen.
      pause = Math.max(sichtbar ? OHR_SCHNELL : OHR_RUHIG, umlauf * 3);
    }
  } catch (e) {
    pause = OHR_RUHIG;
  } finally {
    ohrLaeuft = false;
    setTimeout(ohrSchleife, Math.min(pause, OHR_WEG));
  }
}

ohrSchleife();
// Kommt der Tab zurueck, sofort wieder nachsehen, statt bis zu fuenf
// Sekunden auf die naechste Runde zu warten.
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) ohrSchleife();
});

setInterval(() => {
  // Im Hintergrund braucht niemand einen Zustand. Auf dem iPad hat das
  // sonst weiter alle drei Sekunden ueber den Relais gefragt, waehrend die
  // Seite gar nicht sichtbar war.
  if (document.hidden) return;
  zustandLaden();
  rueckfragenLaden();
  if ($("#bereich-agenten").classList.contains("an")) agentenLaden();
  if ($("#bereich-protokoll").classList.contains("an")) protokollLaden(false);
}, 3000);

zustandLaden();
chatsLaden();
verlaufLaden().then((hatteVerlauf) => {
  // Nur in einem leeren Chat begruessen. Stand schon ein Gespraech da, ist
  // "Bereit. Frag etwas" keine Auskunft, sondern eine Zeile, die sich bei
  // jedem Neuladen unter den Verlauf schiebt - und dort bleibt, bis man
  // daran vorbeigescrollt hat.
  if (!hatteVerlauf) {
    blase("SYSTEM",
          "Bereit. Frag etwas, oder schick im Hangar einen Agenten los.",
          "system");
  }
  $("#verlauf").scrollTop = $("#verlauf").scrollHeight;
});
$("#eingabe").focus();

// Vorführung: /#vorfuehren=Stimme:Sag mal etwas
// Stellt den Modus ein und schickt die Frage gleich ab - praktisch, um die
// Oberflaeche jemandem zu zeigen, ohne selbst davorzusitzen.
(function vorfuehren() {
  const hash = decodeURIComponent(location.hash.replace("#vorfuehren=", ""));
  if (!location.hash.startsWith("#vorfuehren=")) return;
  const [modusname, ...rest] = hash.split(":");
  const frage = rest.join(":").trim();
  const modi = { Text: "text", Stimme: "mischung", Frei: "frei" };
  modusSetzen(modi[modusname] || "text");
  if (frage) setTimeout(() => { $("#eingabe").value = frage; senden(); }, 600);
})();
