const SIDES = ["A", "B", "C", "D"];

function cardHTML(g, c) {
  const sensorsHTML = SIDES.map((side) => {
    const s = c.sensors[side];
    const tempStr = s.present ? s.temperature.toFixed(2) + "\u00B0" : "--";
    return `
      <div class="sensor-cell ${s.present ? "sensor-present" : ""}">
        <span class="sensor-side">${side}</span>
        <span class="sensor-temp">${tempStr}</span>
      </div>`;
  }).join("");

  const doorTone = c.door === "CLOSED" ? "state-ok" : c.door === "OPEN" ? "state-warn" : "";
  const smpsTone = c.smpsRelay === "ON" ? "state-ok" : "";

  return `
    <article class="card" data-compartment="${g}">
      <div class="card-cell ${c.smpsRelay === "ON" ? "charging" : ""}"></div>
      <div class="card-body">
        <div class="card-head">
          <span class="card-eyebrow">Compartment</span>
          <h2>${String(g).padStart(2, "0")}</h2>
          <span class="badge badge-ghost">Board ${c.board} &middot; Slot ${c.localCompartment}</span>
        </div>

        <div class="sensor-grid">${sensorsHTML}</div>

        <div class="stat-row">
          <span class="stat-label">Door</span>
          <span class="badge ${doorTone}">${c.door}</span>
        </div>
        <div class="btn-row">
          <button class="btn btn-open" data-action="door" data-compartment="${g}" data-state="1">Open</button>
          <button class="btn btn-close" data-action="door" data-compartment="${g}" data-state="0">Close</button>
        </div>

        <div class="stat-row">
          <span class="stat-label">SMPS Charging</span>
          <span class="badge ${smpsTone}">${c.smpsRelay}</span>
        </div>
        <div class="btn-row">
          <button class="btn btn-on" data-action="smps" data-compartment="${g}" data-state="1">On</button>
          <button class="btn btn-off" data-action="smps" data-compartment="${g}" data-state="0">Off</button>
        </div>

        <div class="stat-row muted-row">
          <span class="stat-label">Battery</span>
          <span class="badge badge-ghost">${c.battery === "YES" ? "PRESENT" : "NONE"}</span>
        </div>
      </div>
    </article>`;
}

function updateConnection(anyOnline) {
  const conn = document.getElementById("connIndicator");
  const label = document.getElementById("connLabel");

  conn.classList.remove("is-live", "is-down");

  if (anyOnline) {
    conn.classList.add("is-live");
    label.textContent = "LIVE";
  } else {
    conn.classList.add("is-down");
    label.textContent = "NO SIGNAL";
  }
}

function loadStatus() {
  fetch("/status")
    .then((response) => response.json())
    .then((payload) => {
      const compartments = payload.compartments;
      const meta = payload.meta;
      const grid = document.getElementById("cardGrid");

      document.getElementById("stationName").textContent = meta.name;
      document.getElementById("firmwareVer").textContent = meta.firmware;
      document.getElementById("footerCompany").textContent = meta.company;
      document.getElementById("boardCount").textContent = meta.boardCount;
      document.getElementById("compartmentCount").textContent = meta.compartmentCount;

      const ids = Object.keys(compartments).map(Number).sort((a, b) => a - b);

      if (ids.length === 0) {
        grid.innerHTML = '<p class="empty-state">Waiting for boards to report in over CAN&hellip;</p>';
        updateConnection(false);
        document.getElementById("lastUpdated").textContent = new Date().toLocaleTimeString();
        return;
      }

      let anyOnline = false;
      grid.innerHTML = ids.map((g) => {
        if (compartments[g].online) anyOnline = true;
        return cardHTML(g, compartments[g]);
      }).join("");

      grid.querySelectorAll(".card").forEach((card) => {
        card.classList.toggle("card-offline", !compartments[card.dataset.compartment].online);
      });

      wireButtons();
      updateConnection(anyOnline);
      document.getElementById("lastUpdated").textContent = new Date().toLocaleTimeString();
    })
    .catch(() => updateConnection(false));
}

function sendRelayCommand(action, compartment, state, button) {
  button.classList.add("is-sending");

  fetch("/api/relay/" + action + "/" + compartment + "/" + state, { method: "POST" })
    .then((r) => r.json())
    .then((r) => {
      if (!r.ok) console.error("Command failed:", action, compartment, state);
    })
    .catch((e) => console.error("Command error:", e))
    .finally(() => {
      setTimeout(() => button.classList.remove("is-sending"), 400);
      loadStatus();
    });
}

// Cards are rebuilt every poll, so buttons need rewiring each time.
function wireButtons() {
  document.querySelectorAll("button[data-action]").forEach((btn) => {
    btn.onclick = () => {
      sendRelayCommand(btn.dataset.action, btn.dataset.compartment, btn.dataset.state, btn);
    };
  });
}

loadStatus();
setInterval(loadStatus, 1000);
