/**
 * Wat de coach van de kamer van een airco leerde, als regels op de kaart (v0.207.0).
 *
 * Een bewoner op 07-11-2026: "Hoe snel koelt een woning af bij een bepaalde
 * buitentemperatuur, en hoe snel warmt een woning weer op om op een gewenste
 * temperatuur te komen. Dit gekoppeld aan de verbruikte energie." De coach rekent
 * (kamer.py); dit zet alleen in woorden wat hij vaak genoeg mat. Daarvoor staat er
 * dat hij nog aan het leren is, nooit een getal dat hij niet mat.
 */
import { locale, t } from "./i18n.js";

function graden(waarde) {
  return `${waarde.toLocaleString(locale(), { minimumFractionDigits: 1, maximumFractionDigits: 1 })} °C`;
}

function kwh(waarde) {
  const cijfers = waarde < 1 ? 2 : 1;
  return `${waarde.toLocaleString(locale(), { minimumFractionDigits: cijfers, maximumFractionDigits: cijfers })} kWh`;
}

function leert(n, nodig) {
  return t("nog aan het leren ({n} van {nodig} metingen)", { n: Math.min(n, nodig), nodig });
}

export function aircoRegels(besluit) {
  if (!besluit || besluit.kind !== "airco" || !besluit.learned) return [];
  const l = besluit.learned;
  const nodig = l.needed ?? 5;
  const rijen = [];

  // Zonder airco: hoe snel de kamer naar buiten toe zakt (of stijgt), nu.
  const k = l.loss_per_c;
  const kamer = besluit.room_c;
  const buiten = l.outdoor_c;
  let zonder;
  if (!Number.isFinite(k)) {
    zonder = Number.isFinite(buiten) ? leert(l.loss_per_c_n ?? 0, nodig) : t("weet hij niet zonder buitentemperatuur");
  } else if (Number.isFinite(kamer) && Number.isFinite(buiten) && Math.abs(kamer - buiten) >= 1) {
    const perUur = k * Math.abs(kamer - buiten);
    const delen = { c: graden(perUur), binnen: graden(kamer), buiten: graden(buiten) };
    zonder = kamer > buiten
      ? t("zakt ongeveer {c} per uur, bij {binnen} binnen en {buiten} buiten", delen)
      : t("stijgt ongeveer {c} per uur, bij {binnen} binnen en {buiten} buiten", delen);
  } else {
    zonder = t("ongeveer {c} per uur per graad verschil met buiten", { c: graden(k) });
  }
  rijen.push({ label: t("Zonder airco"), text: zonder });

  // Wat een graad kost, per stand: pas als hij in die stand gemeten heeft.
  for (const [sleutel, label] of [["heat", t("Verwarmen")], ["cool", t("Koelen")]]) {
    const perKwh = l[`${sleutel}_c_per_kwh`];
    const n = l[`${sleutel}_c_per_kwh_n`] ?? 0;
    if (Number.isFinite(perKwh) && perKwh > 0) {
      rijen.push({ label, text: t("1 °C kost ongeveer {kwh}", { kwh: kwh(1 / perKwh) }) });
    } else if (n > 0) {
      rijen.push({ label, text: leert(n, nodig) });
    } else if (sleutel === "heat" && Number.isFinite(k) && !l.power_sensor) {
      rijen.push({ label, text: t("weet hij niet zonder vermogenssensor") });
    }
  }
  return rijen;
}
