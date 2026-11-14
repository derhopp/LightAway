"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const registered = new Map();
const context = {
  HTMLElement: class {},
  customElements: {
    get(name) { return registered.get(name); },
    define(name, klass) { registered.set(name, klass); },
  },
  window: { customCards: [] },
  document: { createElement(tag) { return { tagName: tag }; } },
  setInterval() { return 1; },
  clearInterval() {},
};
vm.runInNewContext(
  fs.readFileSync(
    path.join(__dirname, "../custom_components/lightaway/frontend/lightaway-card.js"),
    "utf8"
  ),
  context
);
const Card = registered.get("lightaway-card");

test("card registers and creates native searchable HA entity fields", () => {
  assert.ok(Card);
  const card = new Card();
  const picker = card._entityPicker(
    ["binary_sensor", "switch", "input_boolean"],
    "binary_sensor.holiday",
    "Presence",
    "Search"
  );
  assert.equal(picker.tagName, "ha-entity-picker");
  assert.deepEqual(Array.from(picker.includeDomains), [
    "binary_sensor", "switch", "input_boolean"
  ]);
  assert.equal(picker.showEntityId, true);
  assert.equal(picker.value, "binary_sensor.holiday");
  const light = card._entityPicker(["light"], "", "Light", "Search");
  assert.deepEqual(Array.from(light.includeDomains), ["light"]);
  assert.equal(light.value, "");
});

test("settings changes persist without a save button and serialize rapidly", async () => {
  const card = new Card();
  const server = {
    presence: null, invert: false, enabled: false, lights: ["light.a"]
  };
  const calls = [];
  card._snapshot = { settings: { ...server }, lights: [] };
  card._hass = {
    callWS: async (message) => {
      calls.push(message);
      await Promise.resolve();
      for (const key of ["presence", "invert", "lights", "enabled"]) {
        if (Object.hasOwn(message, key)) server[key] = message[key];
      }
      return { settings: { ...server }, lights: [] };
    }
  };
  let redrawn = 0;
  card._draw = () => { redrawn++; };
  let message = "";
  card._showMessage = (msg) => { message = msg; };
  const first = card._save({ presence: "binary_sensor.holiday" });
  const second = card._save({ lights: ["light.a", "light.b"] });
  await Promise.all([first, second]);
  assert.deepEqual(calls.map(call => call.type), [
    "lightaway/configure", "lightaway/configure"
  ]);
  assert.equal(server.presence, "binary_sensor.holiday");
  assert.deepEqual(server.lights, ["light.a", "light.b"]);
  assert.equal(redrawn, 1);
  assert.equal(message, card.t.saved);
  assert.equal(card._pendingWrites, 0);
});

test("copy-day label is localized consistently in the card", () => {
  const source = fs.readFileSync(
    path.join(__dirname, "../custom_components/lightaway/frontend/lightaway-card.js"),
    "utf8"
  );
  assert.match(source, /date: "Copy day"/);
  assert.match(source, /date: "Kopiertag"/);
  assert.match(source, /no_copy_day: "No suitable copy day"/);
  assert.match(source, /no_copy_day: "Kein geeigneter Kopiertag"/);
  assert.match(source, /item\.copy_day/);
  assert.doesNotMatch(source, /Original.day|original_day/);
});
