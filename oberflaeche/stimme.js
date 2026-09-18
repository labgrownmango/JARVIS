// Stimme, Ohren und die drei Striche.
//
// Der Ton kommt fertig vom Server und wird HIER abgespielt - nur so lässt er
// sich messen. Ein AnalyserNode zerlegt ihn laufend in Frequenzen; jeder
// Strich bekommt ein eigenes Band und schlägt nach dessen Lautstärke aus.

const Stimme = (() => {
  let kontext = null;      // AudioContext
  let analyse = null;      // AnalyserNode
  let quelle = null;       // gerade spielende Quelle
  let laufendeAnimation = null;
  let daten = null;

  // Drei Bänder, grob: Grundton, Vokale, Zischlaute. Die Grenzen sind
  // Erfahrungswerte für Sprache, nicht für Musik.
  const BAENDER = [[80, 350], [350, 1600], [1600, 6000]];

  function starten() {
    if (!kontext) {
      kontext = new (window.AudioContext || window.webkitAudioContext)();
      analyse = kontext.createAnalyser();
      analyse.fftSize = 1024;
      analyse.smoothingTimeConstant = 0.72;
      analyse.connect(kontext.destination);
      daten = new Uint8Array(analyse.frequencyBinCount);
    }
    if (kontext.state === "suspended") kontext.resume();
    return kontext;
  }

  function bandStaerke(index) {
    const proBin = kontext.sampleRate / 2 / analyse.frequencyBinCount;
    const [von, bis] = BAENDER[index];
    let summe = 0, zahl = 0;
    for (let i = Math.floor(von / proBin); i < Math.ceil(bis / proBin); i++) {
      if (i >= daten.length) break;
      summe += daten[i]; zahl++;
    }
    return zahl ? summe / zahl / 255 : 0;
  }

  // Die Striche stehen senkrecht und wachsen aus der Mitte heraus. Eine
  // lautstärkeabhängige Neigung sah zufällig aus, eine feste Fächerstellung
  // unruhig - gerade ist am saubersten.
  // Für einen Fächer: [-0.13, 0, 0.13] statt Nullen eintragen.
  const MITTE = 110, X = [60, 150, 240];
  const NEIGUNG = [0, 0, 0];               // Bogenmaß, konstant

  // Höhere Bänder sind von Natur aus leiser. Ohne eigene Verstärkung bliebe
  // der rechte Strich fast reglos.
  const VERSTAERKUNG = [1.5, 2.3, 4.2];

  // Schnell hoch, langsam runter - das gibt den Ausschlägen Kontur.
  const ANSTIEG = 0.55, ABFALL = 0.11;
  let geglaettet = [0, 0, 0];

  function zeichnen() {
    analyse.getByteFrequencyData(daten);
    for (let i = 0; i < 3; i++) {
      // Wurzel statt roher Wert: leise Stellen bewegen sich sonst kaum
      const roh = Math.min(Math.sqrt(bandStaerke(i)) * VERSTAERKUNG[i] * 0.55, 1);
      const tempo = roh > geglaettet[i] ? ANSTIEG : ABFALL;
      geglaettet[i] += (roh - geglaettet[i]) * tempo;
      const staerke = geglaettet[i];

      const halbe = 11 + staerke * 85;
      const dx = Math.sin(NEIGUNG[i]) * halbe;
      const dy = Math.cos(NEIGUNG[i]) * halbe;
      const strich = document.getElementById("strich" + i);
      strich.setAttribute("x1", X[i] - dx);
      strich.setAttribute("y1", MITTE - dy);
      strich.setAttribute("x2", X[i] + dx);
      strich.setAttribute("y2", MITTE + dy);
      strich.setAttribute("stroke-width", 16 + staerke * 8);
      strich.style.opacity = 0.55 + staerke * 0.45;
    }
    laufendeAnimation = requestAnimationFrame(zeichnen);
  }

  function ruhen() {
    cancelAnimationFrame(laufendeAnimation);
    laufendeAnimation = null;
    geglaettet = [0, 0, 0];
    for (let i = 0; i < 3; i++) {
      const s = document.getElementById("strich" + i);
      const dx = Math.sin(NEIGUNG[i]) * 11, dy = Math.cos(NEIGUNG[i]) * 11;
      s.setAttribute("x1", X[i] - dx); s.setAttribute("y1", MITTE - dy);
      s.setAttribute("x2", X[i] + dx); s.setAttribute("y2", MITTE + dy);
      s.setAttribute("stroke-width", 16);
      s.style.opacity = 0.55;
    }
  }

  async function sprich(text, beiEnde) {
    stopp();
    const ctx = starten();
    let antwort;
    try {
      antwort = await fetch("/api/stimme", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!antwort.ok) throw new Error("Stimme nicht verfügbar");
    } catch (e) {
      if (beiEnde) beiEnde(e);
      return;
    }
    const puffer = await ctx.decodeAudioData(await antwort.arrayBuffer());
    quelle = ctx.createBufferSource();
    quelle.buffer = puffer;
    quelle.connect(analyse);
    quelle.onended = () => { quelle = null; ruhen(); if (beiEnde) beiEnde(null); };
    quelle.start();
    if (!laufendeAnimation) zeichnen();
  }

  function stopp() {
    if (quelle) { try { quelle.stop(); } catch (e) {} quelle = null; }
    ruhen();
  }

  const spricht = () => quelle !== null;
  return { sprich, stopp, spricht, starten, ruhen };
})();


// --- Mikrofon --------------------------------------------------------------
// Aufgenommen wird im Browser, verstanden wird auf diesem Rechner mit
// faster-whisper. Es verlässt nichts das Haus.
const Ohren = (() => {
  let aufnahme = null, stuecke = [], strom = null;
  let stilleSeit = 0, pruefer = null, analyse = null, kontext = null;

  async function starten(beiText, automatisch) {
    if (aufnahme) return;

    // Browser geben das Mikrofon nur in einem "sicheren Kontext" frei: ueber
    // HTTPS, oder direkt auf localhost. Ueber http://jarvis/ vom Handy aus
    // ist navigator.mediaDevices schlicht nicht da - und der Nutzer bekam
    // "Cannot read properties of undefined (reading 'getUserMedia')" zu
    // sehen, was nach einem kaputten Mikrofon aussieht und keines ist.
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      const woher = location.protocol === "https:"
        ? "Dieser Browser gibt kein Mikrofon frei."
        : `Der Browser gibt das Mikrofon nur über HTTPS frei - diese Seite `
          + `läuft über ${location.protocol}//${location.host}. `
          + `Tippen geht weiter; für Sprache bräuchte es eine `
          + `HTTPS-Adresse (z. B. über "tailscale serve").`;
      alert(woher);
      return;
    }

    try {
      strom = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      // NotAllowedError heisst: der Mensch hat abgelehnt oder es einmal
      // blockiert. Das ist etwas anderes als "kein Mikrofon da".
      const grund = e && e.name === "NotAllowedError"
        ? "Der Zugriff wurde abgelehnt. Im Schloss-Symbol der Adresszeile "
          + "lässt sich das Mikrofon wieder erlauben."
        : (e && e.message) || String(e);
      alert("Kein Zugriff aufs Mikrofon: " + grund);
      return;
    }
    stuecke = [];
    aufnahme = new MediaRecorder(strom);
    aufnahme.ondataavailable = (e) => { if (e.data.size) stuecke.push(e.data); };
    aufnahme.onstop = async () => {
      aufraeumen();
      const daten = new Blob(stuecke, { type: "audio/webm" });
      if (daten.size < 1500) { beiText(""); return; }
      const antwort = await fetch("/api/hoeren", {
        method: "POST", headers: { "Content-Type": "application/octet-stream" },
        body: daten,
      });
      const d = await antwort.json();
      beiText(d.text || "");
    };
    aufnahme.start();

    if (automatisch) stilleUeberwachen();
  }

  // Im freien Sprechen endet die Aufnahme von selbst, wenn es still wird
  function stilleUeberwachen() {
    kontext = new (window.AudioContext || window.webkitAudioContext)();
    const quelle = kontext.createMediaStreamSource(strom);
    analyse = kontext.createAnalyser();
    analyse.fftSize = 512;
    quelle.connect(analyse);
    const werte = new Uint8Array(analyse.frequencyBinCount);
    let gesprochen = false;
    stilleSeit = performance.now();

    pruefer = setInterval(() => {
      analyse.getByteTimeDomainData(werte);
      let summe = 0;
      for (const w of werte) summe += (w - 128) ** 2;
      const pegel = Math.sqrt(summe / werte.length) / 128;
      if (pegel > 0.022) { gesprochen = true; stilleSeit = performance.now(); }
      else if (gesprochen && performance.now() - stilleSeit > 1300) stoppen();
    }, 100);
  }

  function aufraeumen() {
    clearInterval(pruefer); pruefer = null;
    if (kontext) { kontext.close(); kontext = null; }
    if (strom) { strom.getTracks().forEach((t) => t.stop()); strom = null; }
    aufnahme = null;
  }

  function stoppen() {
    if (aufnahme && aufnahme.state !== "inactive") aufnahme.stop();
    else aufraeumen();
  }

  const laeuft = () => aufnahme !== null;
  return { starten, stoppen, laeuft };
})();
