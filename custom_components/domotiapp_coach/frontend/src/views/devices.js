/**
 * Apparaten -- everything in the house that costs or produces energy.
 *
 * For now a device is a type, an optional name and a power sensor. That is the
 * minimum the energy flow needs to draw it. More per-device settings are coming
 * (what it may be switched on for, what it costs to run, when it is allowed to
 * start), so each device is its own card with room to grow downwards rather than
 * a row in a table.
 */

import { define } from "../base.js";
import { icons } from "../icons.js";
import { DEVICE_TYPES, deviceLabel, typeMeta } from "../devices.js";
import {
  DacEditorElement,
  adminNoticeHtml,
  editorCss,
  saveBarHtml,
} from "./editor-base.js";
import "../components/entity-picker.js";

const uid = () => `dev-${Math.random().toString(36).slice(2, 9)}`;

class DacViewDevices extends DacEditorElement {
  static sections = ["devices"];

  constructor() {
    super();
    /**
     * Which devices are open, by id.
     *
     * Kept on the id and not the position, because removing a device shifts
     * every index below it and would leave the wrong cards open. A device is
     * open while it is being worked on: straight after it is added, and after
     * its line is tapped. Saving closes them all -- the list is what this screen
     * is for, and a house has more than two appliances.
     */
    this.open_ = new Set();
  }

  render() {
    return `
      <div class="wrap">
        <header class="intro">
          <div class="eyebrow">Apparaten</div>
          <h1>Wat er in huis energie vraagt</h1>
          <p>Deze apparaten verschijnen als bollen in de energiestroom op het overzicht. Er staan er altijd hoogstens twee in beeld: draaien er meer, dan krijgt de zwaarste zijn eigen bol en worden de rest bij elkaar opgeteld in de tweede.</p>
        </header>

        ${adminNoticeHtml}

        <div id="device-list"></div>

        <button class="add" type="button" id="add-device">${icons.plus} Apparaat toevoegen</button>
      </div>

      ${saveBarHtml}
    `;
  }

  afterRender() {
    this.$("#add-device").addEventListener("click", () => {
      const device = { id: uid(), type: "laadpaal", name: "", entity: "" };
      this.draft_.devices.push(device);
      // A new device has nothing filled in yet, so it opens on its fields.
      this.open_.add(device.id);
      this.paintDevices_();
      this.syncSaveBar_();
      // A device added from the bottom of a long list is off screen otherwise.
      this.$$(".device").at(-1)?.scrollIntoView({ block: "center", behavior: "smooth" });
    });

    this.wireSaveBar_();
    this.paint_();
  }

  paint_() {
    if (!this.draft_ || !this.rendered_) return;
    this.paintDevices_();
    this.syncSaveBar_();
  }

  /** Everything is filled in and stored, so the list goes back to being a list. */
  afterSave_() {
    if (!this.open_.size) return;
    this.open_.clear();
    this.paintDevices_();
  }

  /** Keep the folded-shut line in step while the card is open. */
  paintSummary_(index) {
    const line = this.$(`[data-summary="${index}"]`);
    if (!line) return;
    const { text, warn } = this.summary_(this.draft_.devices[index]);
    line.textContent = text;
    line.classList.toggle("warn", warn);
  }

  /** How a device reads when it is folded shut. */
  summary_(device) {
    // The sensor is the one thing worth checking without opening the card: it is
    // what decides whether this device shows up on the overview at all. The type
    // only earns a place when the heading above it is a name of the customer's
    // own, otherwise it would say the same word twice.
    const what = device.entity || "nog geen vermogenssensor";
    const named = (device.name ?? "").trim();
    return {
      text: named ? `${typeMeta(device.type).label} · ${what}` : what,
      warn: !device.entity,
    };
  }

  paintDevices_() {
    const list = this.$("#device-list");
    const devices = this.draft_.devices ?? [];

    if (!devices.length) {
      list.innerHTML = `
        <section class="card empty">
          <div class="empty-mark">${icons.devices}</div>
          <h2>Nog geen apparaten</h2>
          <p>Voeg je laadpaal, warmtepomp of vaatwasser toe om te zien wanneer ze draaien en wat ze op dat moment vragen.</p>
        </section>`;
      return;
    }

    list.innerHTML = devices
      .map((device, index) => {
        const open = this.open_.has(device.id);
        const summary = this.summary_(device);
        return `
        <section class="card device${open ? " open" : ""}" data-index="${index}">
          <div class="device-head">
            <button class="toggle" type="button" data-toggle="${index}" aria-expanded="${open}">
              <span class="chip">${icons[typeMeta(device.type).icon]}</span>
              <span class="head-body">
                <span class="name" data-title="${index}"></span>
                <span class="sub${summary.warn ? " warn" : ""}" data-summary="${index}"></span>
              </span>
              <span class="chev">${icons.chevronRight}</span>
            </button>
            <button class="remove" type="button" data-remove="${index}" aria-label="Verwijderen">${icons.trash}</button>
          </div>
          <div class="fields"${open ? "" : " hidden"}>
            <div class="two">
              <div class="row">
                <label>Type</label>
                <select data-field="type" data-index="${index}">
                  ${DEVICE_TYPES.map(
                    (t) => `<option value="${t.id}"${t.id === device.type ? " selected" : ""}>${t.label}</option>`
                  ).join("")}
                </select>
              </div>
              <div class="row">
                <label>Eigen naam</label>
                <input type="text" data-field="name" data-index="${index}"
                       value="${(device.name ?? "").replace(/"/g, "&quot;")}"
                       placeholder="${device.type === "overig" ? "Bijvoorbeeld: serverkast" : "optioneel"}"
                       autocomplete="off">
              </div>
            </div>
            <div class="row">
              <label>Vermogenssensor</label>
              <dac-entity-picker data-index="${index}"></dac-entity-picker>
            </div>
          </div>
        </section>`;
      })
      .join("");

    // Names are the customer's own text and the entity id comes from Home
    // Assistant, so neither goes in through innerHTML.
    for (const [index, device] of devices.entries()) {
      list.querySelector(`[data-title="${index}"]`).textContent = deviceLabel(device);
      list.querySelector(`[data-summary="${index}"]`).textContent = this.summary_(device).text;
    }

    for (const toggle of list.querySelectorAll("[data-toggle]")) {
      toggle.addEventListener("click", () => {
        const { id } = devices[Number(toggle.dataset.toggle)];
        if (this.open_.has(id)) this.open_.delete(id);
        else this.open_.add(id);
        this.paintDevices_();
      });
    }

    for (const picker of list.querySelectorAll("dac-entity-picker")) {
      const index = Number(picker.dataset.index);
      picker.filter = "power";
      picker.placeholder = "Zoek een vermogenssensor…";
      picker.stateFeed = this.feed_;
      picker.value = devices[index].entity ?? "";
      picker.addEventListener("dac-entity-change", (ev) => {
        this.draft_.devices[index].entity = ev.detail.value;
        this.paintSummary_(index);
        this.syncSaveBar_();
      });
    }

    for (const el of list.querySelectorAll("[data-field]")) {
      const index = Number(el.dataset.index);
      const field = el.dataset.field;
      el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => {
        this.draft_.devices[index][field] = el.value;
        if (field === "type") {
          // The icon and the heading follow the type, but redrawing on every
          // keystroke in the name field would throw the caret away.
          this.paintDevices_();
        } else if (field === "name") {
          const title = list.querySelector(`[data-title="${index}"]`);
          title.textContent = deviceLabel(this.draft_.devices[index]);
        }
        this.syncSaveBar_();
      });
    }

    for (const button of list.querySelectorAll("[data-remove]")) {
      button.addEventListener("click", () => {
        this.draft_.devices.splice(Number(button.dataset.remove), 1);
        this.paintDevices_();
        this.syncSaveBar_();
      });
    }
  }
}

DacViewDevices.css = /* css */ `
  ${editorCss}

  #device-list { display: flex; flex-direction: column; gap: 12px; }

  /* Folded shut a device is one line, so the card is only as tall as that line;
     open, it gets the room its fields need. */
  section.card.device { padding: 12px 12px 12px 14px; }
  section.card.device.open { padding-bottom: 20px; }
  .device .fields[hidden] { display: none; }

  .device-head { display: flex; align-items: center; gap: 8px; }

  .device-head button.toggle {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 4px 2px;
    border: 0;
    background: transparent;
    color: var(--dac-ink);
    font: inherit;
    text-align: left;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }
  .device-head .head-body { flex: 1 1 auto; min-width: 0; display: grid; gap: 2px; }
  .device-head .sub {
    font-size: 12px;
    color: var(--dac-ink-3);
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .device-head .sub.warn { color: var(--dac-warn); }

  .device-head .chev { flex: 0 0 auto; display: grid; color: var(--dac-ink-3); }
  .device-head .chev .icon {
    width: 18px; height: 18px;
    transition: transform 220ms cubic-bezier(0.22,0.61,0.36,1);
  }
  .device.open .chev .icon { transform: rotate(90deg); }
  .device-head button.toggle:hover .chev { color: var(--dac-ink-2); }

  .device-head .chip {
    width: 36px; height: 36px; flex: 0 0 auto;
    display: grid; place-items: center;
    border-radius: 11px;
    color: var(--dac-accent-hi);
    background: var(--dac-accent-soft);
    border: 1px solid rgba(25,143,217,0.28);
  }
  .device-head .chip .icon { width: 19px; height: 19px; }
  .device-head .name {
    font-size: 15px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .device-head button.remove {
    flex: 0 0 auto;
    width: 36px; height: 36px;
    display: grid; place-items: center;
    border-radius: 10px;
    border: 1px solid var(--dac-border);
    background: transparent;
    color: var(--dac-ink-3);
    cursor: pointer;
  }
  .device-head button.remove:hover { color: var(--dac-bad); border-color: rgba(208,59,59,0.5); }
  .device-head button.remove .icon { width: 16px; height: 16px; }

  button.add {
    align-self: flex-start;
    display: inline-flex; align-items: center; gap: 8px;
    padding: 12px 18px;
    border-radius: var(--dac-radius-pill);
    border: 1px dashed var(--dac-border-hi);
    background: transparent;
    color: var(--dac-ink-2);
    font: inherit; font-size: 14px; font-weight: 500;
    cursor: pointer;
    min-height: 44px;
  }
  button.add:hover { color: var(--dac-ink); border-color: var(--dac-accent-hi); background: var(--dac-accent-soft); }
  button.add .icon { width: 17px; height: 17px; }

  .empty { text-align: center; padding: 40px 22px 42px; }
  .empty-mark {
    width: 56px; height: 56px; margin: 0 auto 18px;
    display: grid; place-items: center;
    border-radius: 18px;
    color: var(--dac-accent-hi);
    background: var(--dac-accent-soft);
    border: 1px solid rgba(25,143,217,0.28);
  }
  .empty-mark .icon { width: 27px; height: 27px; }
  .empty h2 { display: block; font-size: 18px; }
  .empty p { margin: 10px auto 0; max-width: 46ch; font-size: 13.5px; line-height: 1.6; color: var(--dac-ink-2); }

  @media (max-width: 560px) {
    button.add { align-self: stretch; justify-content: center; }
  }
`;

define("dac-view-devices", DacViewDevices);
