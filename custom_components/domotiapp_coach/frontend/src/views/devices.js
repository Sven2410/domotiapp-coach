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
import {
  DEVICE_TYPES,
  DISHWASHER_PROGRAMS,
  PLAN_LABELS,
  brandActions,
  brandButtons,
  brandDevice,
  brandEntityFields,
  brandFields,
  brandMeta,
  brandsFor,
  deviceLabel,
  deviceLabelMap,
  missingForControl,
  typeMeta,
} from "../devices.js";
import { duration } from "../format.js";
import {
  DacEditorElement,
  adminNoticeHtml,
  editorCss,
  saveBarHtml,
} from "./editor-base.js";
import { sheetCss } from "../theme.js";
import "../components/entity-picker.js";

const uid = () => `dev-${Math.random().toString(36).slice(2, 9)}`;

/** "ontbreekt nog: Status" / "ontbreken nog: Status en Stroom". */
const missingText = (missing) =>
  `${missing.length > 1 ? "ontbreken" : "ontbreekt"} nog: ${missing.join(" en ")}`;

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

      <dialog class="sheet" id="confirm" aria-labelledby="confirm-title">
        <div class="sheet-head">
          <div>
            <div class="eyebrow">Verwijderen</div>
            <h3 id="confirm-title"></h3>
          </div>
          <button class="sheet-close" type="button" id="confirm-close" aria-label="Sluiten">${icons.close}</button>
        </div>
        <p class="sheet-sub" id="confirm-sub"></p>
        <div class="sheet-buttons">
          <button type="button" id="confirm-no">Laat staan</button>
          <button type="button" class="danger" id="confirm-yes">Verwijderen</button>
        </div>
      </dialog>

      ${saveBarHtml}
    `;
  }

  afterRender() {
    this.$("#add-device").addEventListener("click", () => {
      const device = {
        id: uid(),
        type: "laadpaal",
        name: "",
        entity: "",
        brand: "",
        controllable: false,
        entities: {},
        device_id: "",
        actions: {},
      };
      this.draft_.devices.push(device);
      // A new device has nothing filled in yet, so it opens on its fields.
      this.open_.add(device.id);
      this.paintDevices_();
      this.syncSaveBar_();
      // A device added from the bottom of a long list is off screen otherwise.
      this.$$(".device").at(-1)?.scrollIntoView({ block: "center", behavior: "smooth" });
    });

    const confirm = this.$("#confirm");
    this.$("#confirm-yes").addEventListener("click", () => this.confirmRemove_());
    for (const id of ["#confirm-no", "#confirm-close"]) {
      this.$(id).addEventListener("click", () => confirm.close());
    }
    confirm.addEventListener("close", () => {
      this.removing_ = null;
    });

    this.wireSaveBar_();
    this.paint_();
  }

  paint_() {
    if (!this.draft_ || !this.rendered_) return;
    this.paintDevices_();
    this.syncSaveBar_();
  }

  onDisconnect() {
    super.onDisconnect();
    // A modal that is detached loses its place in the top layer, so it would
    // come back as a panel stuck in the middle of the page.
    this.$("#confirm")?.close();
  }

  onHass_() {
    this.loadIntegrationDevices_();
  }

  onConnect() {
    this.loadIntegrationDevices_();
  }

  /**
   * Home Assistant's device registry, fetched once.
   *
   * Newer frontends hand the panel `hass.devices` outright; older ones do not,
   * so the websocket is the fallback. Either way a failure is not fatal -- the
   * dropdown says so and everything else on the screen keeps working.
   */
  async loadIntegrationDevices_() {
    if (this.haDevices_ || this.loadingDevices_ || !this.hass_) return;
    this.loadingDevices_ = true;

    try {
      const known = Object.values(this.hass_.devices ?? {});
      this.haDevices_ = known.length
        ? known
        : await this.hass_.callWS({ type: "config/device_registry/list" });
    } catch (error) {
      console.warn("[DomotiApp Coach] kon de apparaten van Home Assistant niet lezen", error);
      this.haDevices_ = [];
    }

    this.loadingDevices_ = false;
    if (this.rendered_ && this.draft_) this.paintDevices_();
  }

  /** The registry devices belonging to one integration. */
  integrationDevices_(domain) {
    return (this.haDevices_ ?? [])
      .filter((device) =>
        (device.identifiers ?? []).some(([owner]) => owner === domain)
      )
      .map((device) => ({
        id: device.id,
        label: device.name_by_user || device.name || device.id,
      }))
      .sort((a, b) => a.label.localeCompare(b.label, "nl"));
  }

  /**
   * A device may not be marked steerable without the means to steer it.
   *
   * Saving it worked before, and then nothing happened: the box stayed ticked,
   * the device turned up on the overview with a vrijgaveknop, and the commands
   * it needed were never there. Better to refuse the save and say which field
   * is missing, on the card that is missing it.
   */
  blockers_() {
    const broken = (this.draft_?.devices ?? [])
      .map((device) => ({ device, missing: missingForControl(device) }))
      .filter((entry) => entry.missing.length);

    if (!broken.length) return [];

    const [first] = broken;
    if (broken.length === 1) {
      return [`${this.labelFor_(first.device)}: om te kunnen sturen ${missingText(first.missing)}.`];
    }
    return [
      `${broken.length} apparaten kunnen nog niet gestuurd worden, om te beginnen ${this.labelFor_(first.device)}.`,
    ];
  }

  /** Everything is filled in and stored, so the list goes back to being a list. */
  afterSave_() {
    if (!this.open_.size) return;
    this.open_.clear();
    this.paintDevices_();
  }

  /**
   * The entity fields for one device.
   *
   * Anything with brands is asked for its brand first and nothing else: which
   * entities it has is a brand question, and a screen full of fields that only
   * apply to somebody else's appliance helps nobody. Everything else goes
   * straight to its power sensor, which every device has -- it is what puts it
   * on the energy flow at all.
   */
  brandHtml_(device, index) {
    const brands = brandsFor(device.type);
    const brand = brandMeta(device);
    const what = typeMeta(device.type).label.toLowerCase();

    const brandRow = !brands.length
      ? ""
      : `
        <div class="row">
          <label for="brand-${index}">Merk</label>
          <select id="brand-${index}" data-field="brand" data-index="${index}">
            <option value=""${device.brand ? "" : " selected"}>Kies een merk…</option>
            ${brands.map(
              (b) => `<option value="${b.id}"${b.id === device.brand ? " selected" : ""}>${b.label}</option>`
            ).join("")}
          </select>
          <span class="sub">Welke gegevens een ${what} levert, hangt van het merk af. Kies er een en de bijbehorende velden verschijnen.${brands.some((b) => b.note) ? ` ${brands.filter((b) => b.note).map((b) => b.note).join(" ")}` : ""}</span>
        </div>`;

    // Something with brands but none picked has nothing to ask for yet.
    if (brands.length && !brand) return brandRow;

    const power = `
      <div class="row">
        <label>Vermogenssensor</label>
        <dac-entity-picker data-power data-index="${index}"></dac-entity-picker>
      </div>`;

    const extra = brandFields(device)
      .map(
        (field) => `
        <div class="row">
          <label>${field.label}</label>
          <dac-entity-picker data-entity-key="${field.key}" data-index="${index}"></dac-entity-picker>
          <span class="sub">${field.hint}${field.needed ? " Nodig zodra de coach mag sturen." : ""}</span>
        </div>`
      )
      .join("");

    const note =
      brands.length && !extra
        ? `<p class="sub">Voor dit merk zijn de velden nog niet uitgewerkt — vermogen wordt wel meegenomen.</p>`
        : "";

    return `${brandRow}${this.integrationHtml_(device, index)}${power}${extra}${this.buttonsHtml_(device, index)}${this.actionsHtml_(device, index)}${this.programsHtml_(device)}${note}`;
  }

  /**
   * The entities this brand is steered through.
   *
   * Separate from the readings above: these are the ones that make something
   * happen, and the customer picking them should know that is what they are.
   */
  buttonsHtml_(device, index) {
    const buttons = brandButtons(device);
    if (!buttons.length) return "";

    const rows = buttons
      .map(
        (button) => `
        <div class="row">
          <label>${button.label}</label>
          <dac-entity-picker data-entity-key="${button.key}" data-index="${index}"></dac-entity-picker>
          <span class="sub">${button.hint}${button.needed ? " Nodig zodra de coach mag sturen." : ""}</span>
        </div>`
      )
      .join("");

    return `
      <div class="row">
        <label>Bediening</label>
        <span class="sub">Wat er ingedrukt wordt om dit apparaat te laten lopen. Dit is wat de knoppen onder Handmatige besturing op het overzicht doen; de coach doet het nog niet uit zichzelf.</span>
        <div class="fields">${rows}</div>
      </div>`;
  }

  /**
   * What the panel already knows about this brand's programs.
   *
   * Shown because it is what the coach will plan with: the customer should be
   * able to see that the numbers exist, and that they are specifications rather
   * than something measured at their house.
   */
  programsHtml_(device) {
    if (brandMeta(device)?.id !== "home_connect" || device.type !== "vaatwasser") return "";

    const rows = DISHWASHER_PROGRAMS.map(
      (program) => `
      <tr>
        <td>${program.label}</td>
        <td class="tnum">${duration(program.minutes)}</td>
        <td class="tnum">${program.kwh.toLocaleString("nl-NL", { minimumFractionDigits: 2 })} kWh</td>
        <td>${PLAN_LABELS[program.plan]}</td>
      </tr>`
    ).join("");

    return `
      <div class="row">
        <label>Bekende programma's</label>
        <span class="sub">Wat een programma ongeveer duurt en kost staat in het paneel, zodat de coach straks kan uitrekenen wanneer hij hem het beste kan laten draaien. Dit zijn opgaven van de fabrikant, geen metingen bij jou thuis.</span>
        <div class="table-scroll">
          <table class="programs">
            <thead><tr><th>Programma</th><th>Duur</th><th>Energie</th><th>Verschuiven</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
  }

  /**
   * The Home Assistant device behind a brand that is steered per device.
   *
   * Easee's `action_command` takes a device id, not an entity, so the
   * integration's own device is picked here. The list comes from Home
   * Assistant's device registry, filtered to that integration -- typing a
   * device id by hand is not something to ask of anybody.
   */
  integrationHtml_(device, index) {
    const wanted = brandDevice(device);
    if (!wanted) return "";

    const found = this.integrationDevices_(wanted.domain);
    const options = found
      .map(
        (d) =>
          `<option value="${d.id}"${d.id === device.device_id ? " selected" : ""}>${d.label}</option>`
      )
      .join("");

    const empty = !found.length
      ? `<span class="sub warn">Home Assistant kent nog geen ${wanted.label}. Installeer die integratie eerst.</span>`
      : "";

    return `
      <div class="row">
        <label for="hadev-${index}">${wanted.label}</label>
        <select id="hadev-${index}" data-field="device_id" data-index="${index}"${found.length ? "" : " disabled"}>
          <option value=""${device.device_id ? "" : " selected"}>Kies je laadpaal…</option>
          ${options}
        </select>
        <span class="sub">${wanted.hint}</span>
        ${empty}
      </div>`;
  }

  /** The words this brand wants for start, stop, pause, resume and reboot. */
  actionsHtml_(device, index) {
    const actions = brandActions(device);
    if (!actions.length) return "";

    const brand = brandMeta(device);
    const fields = actions
      .map(
        (action) => `
        <div class="row">
          <label for="act-${index}-${action.key}">${action.label}</label>
          <input type="text" id="act-${index}-${action.key}"
                 data-action="${action.key}" data-index="${index}"
                 value="${(device.actions?.[action.key] ?? action.fallback).replace(/"/g, "&quot;")}"
                 placeholder="${action.fallback}" autocomplete="off"
                 autocapitalize="off" spellcheck="false">
        </div>`
      )
      .join("");

    return `
      <div class="row">
        <label>Opdrachten</label>
        <span class="sub">Wat er naar <code>${brand.service}</code> gestuurd wordt als <code>${brand.field}</code>. De ingevulde woorden zijn wat Easee vandaag gebruikt; wijkt jouw paal af, dan pas je ze hier aan. Dit is wat de knoppen onder Handmatige besturing op het overzicht versturen; de coach stuurt nog niet uit zichzelf.</span>
        <div class="two commands">${fields}</div>
      </div>`;
  }

  /** Whether the coach may act on this device once it can. */
  controlHtml_(device, index) {
    // Nothing to decide yet on an appliance whose brand is still unknown.
    if (brandsFor(device.type).length && !brandMeta(device)) return "";

    const missing = missingForControl(device);
    return `
      <label class="check" for="control-${index}">
        <input type="checkbox" id="control-${index}" data-field="controllable" data-index="${index}"
               ${device.controllable ? "checked" : ""}>
        <span>
          <strong>De coach mag dit apparaat aansturen</strong>
          Een apparaat dat alleen op een meetstekker zit, kun je wel volgen maar niet sturen. Zet dit alleen aan bij apparaten die echt te bedienen zijn. Ze komen dan op het overzicht te staan, met een vrijgaveknop en handmatige besturing.
        </span>
      </label>
      <div class="notice"${missing.length ? "" : " hidden"} data-missing="${index}">
        ${icons.warning}
        <span>Om te kunnen sturen ${missingText(missing)}.</span>
      </div>`;
  }

  /** Say on the spot what steering this device would still need. */
  paintMissing_(index) {
    const notice = this.$(`[data-missing="${index}"]`);
    if (!notice) return;
    const missing = missingForControl(this.draft_.devices[index]);
    notice.hidden = !missing.length;
    if (missing.length) {
      notice.querySelector("span").textContent = `Om te kunnen sturen ${missingText(missing)}.`;
    }
  }

  /** Keep the folded-shut line in step while the card is open. */
  paintSummary_(index) {
    const line = this.$(`[data-summary="${index}"]`);
    if (!line) return;
    const { text, warn } = this.summary_(this.draft_.devices[index]);
    line.textContent = text;
    line.classList.toggle("warn", warn);
  }

  /**
   * This device's name, with two of a kind told apart.
   *
   * Two dishwashers added without names are both "Vaatwasser", and this list is
   * where you would be deleting one of them.
   */
  labelFor_(device) {
    return deviceLabelMap(this.draft_?.devices).get(device.id) ?? deviceLabel(device);
  }

  /** Whether another device would read exactly the same on a list. */
  sharesLabel_(device) {
    const label = deviceLabel(device);
    return (this.draft_?.devices ?? []).some(
      (other) => other !== device && deviceLabel(other) === label
    );
  }

  /** Whether another device is already reading the same power sensor. */
  sharesSensor_(device) {
    return (this.draft_?.devices ?? []).some(
      (other) => other !== device && other.entity && other.entity === device.entity
    );
  }

  /** How a device reads when it is folded shut. */
  summary_(device) {
    // Whatever is missing outranks everything else: a device that cannot be
    // steered while it is set to be steered is the one thing worth saying on a
    // folded-shut line.
    const missing = missingForControl(device);
    if (missing.length) return { text: `om te kunnen sturen ${missingText(missing)}`, warn: true };
    if (brandsFor(device.type).length && !device.brand) {
      return { text: "nog geen merk gekozen", warn: true };
    }
    // Two devices on one power sensor means the energy flow counts those watts
    // twice, and the second bubble is a copy of the first. Almost always a
    // sensor picked in a hurry.
    if (device.entity && this.sharesSensor_(device)) {
      return { text: `${device.entity} zit al op een ander apparaat`, warn: true };
    }

    // The sensor is the one thing worth checking without opening the card: it is
    // what decides whether this device shows up in the energy flow. Not having
    // one is a fair choice rather than a mistake -- plenty of appliances are
    // worth steering without being metered -- so it is stated plainly and not
    // in the warning colour. The type only earns a place when the heading above
    // it is a name of the customer's own, otherwise it would say the same word
    // twice.
    const what = device.entity || "geen vermogenssensor";
    const brand = brandMeta(device)?.label;
    const prefix = brand ?? ((device.name ?? "").trim() ? typeMeta(device.type).label : "");
    return {
      text: prefix ? `${prefix} · ${what}` : what,
      warn: false,
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
                ${
                  this.sharesLabel_(device)
                    ? `<span class="sub">Er staan er twee van dit type. Zonder eigen naam heten ze hier en op het overzicht "${typeMeta(device.type).label} 1" en "${typeMeta(device.type).label} 2"; met een naam weet je meteen welke welke is.</span>`
                    : ""
                }
              </div>
            </div>
            ${this.brandHtml_(device, index)}
            ${this.controlHtml_(device, index)}
          </div>
        </section>`;
      })
      .join("");

    // Names are the customer's own text and the entity id comes from Home
    // Assistant, so neither goes in through innerHTML.
    for (const [index, device] of devices.entries()) {
      list.querySelector(`[data-title="${index}"]`).textContent = this.labelFor_(device);
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

    for (const picker of list.querySelectorAll("dac-entity-picker[data-power]")) {
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

    for (const picker of list.querySelectorAll("dac-entity-picker[data-entity-key]")) {
      const index = Number(picker.dataset.index);
      const key = picker.dataset.entityKey;
      // Not a power filter: a status or a limit is anything but watts, and the
      // filter is a ranking rather than a restriction anyway.
      picker.filter = "all";
      picker.placeholder = "Zoek een entiteit…";
      picker.stateFeed = this.feed_;
      // A charger reports its status in English keys whatever the language Home
      // Assistant is set to, so the check "is this the right sensor?" is only
      // useful if it reads the same here as on the overview.
      const meta = brandEntityFields(devices[index]).find((field) => field.key === key);
      picker.values = meta?.values;
      picker.format = meta?.format;
      picker.value = devices[index].entities?.[key] ?? "";
      picker.addEventListener("dac-entity-change", (ev) => {
        const device = this.draft_.devices[index];
        device.entities = { ...(device.entities ?? {}), [key]: ev.detail.value };
        this.paintMissing_(index);
        this.paintSummary_(index);
        this.syncSaveBar_();
      });
    }

    for (const input of list.querySelectorAll("[data-action]")) {
      const index = Number(input.dataset.index);
      const key = input.dataset.action;
      input.addEventListener("input", () => {
        const device = this.draft_.devices[index];
        device.actions = { ...(device.actions ?? {}), [key]: input.value.trim() };
        this.syncSaveBar_();
      });
    }

    for (const el of list.querySelectorAll("[data-field]")) {
      const index = Number(el.dataset.index);
      const field = el.dataset.field;
      const event = el.type === "checkbox" ? "change" : el.tagName === "SELECT" ? "change" : "input";

      el.addEventListener(event, () => {
        const device = this.draft_.devices[index];

        if (field === "controllable") {
          device.controllable = el.checked;
        } else {
          device[field] = el.value;
        }

        if (field === "controllable" || field === "device_id") {
          this.paintMissing_(index);
          this.paintSummary_(index);
        }

        if (field === "type" || field === "brand") {
          // Both decide which fields belong here at all, so the card is redrawn.
          // The name field is not: redrawing on every keystroke would throw the
          // caret away.
          this.paintDevices_();
        } else if (field === "name") {
          list.querySelector(`[data-title="${index}"]`).textContent = this.labelFor_(device);
          this.paintSummary_(index);
        }

        this.syncSaveBar_();
      });
    }

    for (const button of list.querySelectorAll("[data-remove]")) {
      button.addEventListener("click", () => this.askRemove_(Number(button.dataset.remove)));
    }
  }

  /**
   * Ask before a device disappears.
   *
   * The save bar can still undo it, but the two are not the same reassurance:
   * the bin sits right next to the line you tap to open a device, so the tap
   * that removes something is exactly the tap you make by accident -- and a
   * device carries a screen full of entities somebody sat down to fill in.
   */
  askRemove_(index) {
    const device = this.draft_.devices[index];
    if (!device) return;

    this.removing_ = device.id;
    this.$("#confirm-title").textContent = this.labelFor_(device);
    this.$("#confirm-sub").textContent = device.entity
      ? `Dit apparaat verdwijnt uit de lijst, met alles wat je eraan gekoppeld hebt. Opslaan maakt het definitief; tot die tijd kun je het onderaan nog terugdraaien.`
      : `Dit apparaat verdwijnt uit de lijst. Opslaan maakt het definitief; tot die tijd kun je het onderaan nog terugdraaien.`;
    this.$("#confirm").showModal();
  }

  /** Remove the device the dialog was opened for, by id rather than position. */
  confirmRemove_() {
    const index = this.draft_.devices.findIndex((device) => device.id === this.removing_);
    this.$("#confirm").close();
    this.removing_ = null;
    if (index < 0) return;

    this.draft_.devices.splice(index, 1);
    this.paintDevices_();
    this.syncSaveBar_();
  }
}

DacViewDevices.css = /* css */ `
  ${editorCss}
  ${sheetCss}

  #device-list { display: flex; flex-direction: column; gap: 12px; }

  /* The programme table is wider than a phone; it scrolls inside its own box
     rather than making the page scroll sideways. */
  .table-scroll { overflow-x: auto; overscroll-behavior-x: contain; margin-top: 8px; }
  table.programs {
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
    white-space: nowrap;
  }
  table.programs th, table.programs td {
    padding: 7px 14px 7px 0;
    text-align: left;
    border-bottom: 1px solid var(--dac-border);
  }
  table.programs th {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--dac-ink-3);
  }
  table.programs td { color: var(--dac-ink-2); }
  table.programs td:first-child { color: var(--dac-ink); font-weight: 500; }
  table.programs tr:last-child td { border-bottom: 0; }

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

  /* The notice sits in the field grid, which already spaces its rows. */
  .device .fields .notice { margin-top: 0; }
  .sub.warn { color: var(--dac-warn); }
  .commands { margin-top: 2px; }
  .commands input { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  code {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.94em;
    color: var(--dac-ink-2);
  }
  .device .fields > .sub { margin: 0; font-size: 12px; color: var(--dac-ink-3); line-height: 1.45; }

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
