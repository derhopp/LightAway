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

test("week controls use numeric and boolean inputs with autosave", () => {
  const source = fs.readFileSync(
    path.join(__dirname, "../custom_components/lightaway/frontend/lightaway-card.js"),
    "utf8"
  );
  for(const key of ["min_weeks_from_today","max_weeks_away",
    "use_recent_weeks","just_same_copy_day"]) {
    assert.ok(source.includes(key), key);
  }
  assert.match(source, /Min\. Weeks from today/);
  assert.match(source, /Max\. Weeks away/);
  assert.match(source, /Just same copy day/);
  assert.ok(source.includes('type:"number"'));
  assert.ok(source.includes("Number.isInteger"));
  assert.ok(source.includes("this._save({[key]:number})"));
});

test("progress is visible while recalculation or configuration is pending", () => {
  const card = new Card();
  const progress = {hidden: true};
  const text = {textContent: ""};
  card._progress = progress;
  card._progressText = text;
  card._snapshot = {ready: false, settings: {}, lights: []};
  card._updateProgress();
  assert.equal(progress.hidden, false);
  assert.equal(text.textContent, card.t.updating);

  card._snapshot.ready = true;
  card._updateProgress();
  assert.equal(progress.hidden, true);

  card._pendingWrites = 1;
  card._updateProgress();
  assert.equal(progress.hidden, false);
});


test("card does not force wider-than-parent layout or horizontal scrolling", () => {
  const source = fs.readFileSync(
    path.join(__dirname, "../custom_components/lightaway/frontend/lightaway-card.js"),
    "utf8"
  );
  assert.match(source, /:host\\{display:block;box-sizing:border-box;width:100%;max-width:100%;min-width:0/);
  assert.doesNotMatch(source, /width:min\\(150%/);
  assert.doesNotMatch(source, /getGridOptions\\(\\)/);
  assert.match(source, /\\.light-metrics\\{display:grid;grid-template-columns:repeat\\(4,minmax\\(0,1fr\\)\\)/);
  assert.match(source, /@media\\(max-width:700px\\)\\{\\.light-metrics\\{grid-template-columns:repeat\\(2,minmax\\(0,1fr\\)\\)/);
  assert.match(source, /overflow-wrap:anywhere/);
  assert.match(source, /const addPicker=this\\._entityPicker\\(\\["light"\\]/);
  assert.match(source, /addControl\\.append\\(addButton\\)/);
  assert.match(source, /icon\\.setAttribute\\("icon","mdi:delete-outline"\\)/);
  assert.doesNotMatch(source, /const selectedList=/);
  assert.doesNotMatch(source, /const table=this\\._el\\("table"\\)/);
});

test("combined light list includes copy day, actual, desired, status, and a delete action", async () => {
  const card = new Card();
  const node = (tag, attrs = {}, value) => ({
    tagName: tag, attrs: {...attrs}, textContent: value, children: [],
    handlers: {}, disabled: false,
    setAttribute(k, v){this.attrs[k]=v;},
    addEventListener(name, fn){this.handlers[name]=fn;},
    append(...children){this.children.push(...children);},
    replaceChildren(...children){this.children=[...children];}
  });
  card._el=node;
  card._lightList=node("ul");
  card._hass={states:{
    "light.a": {state:"on",attributes:{friendly_name:"Kitchen Main"}},
    "light.b": {state:"off",attributes:{friendly_name:"Study"}}
  }};
  card._snapshot={
    ready:true,
    settings:{lights:["light.a","light.b"]},
    lights:[
      {entity_id:"light.a",copy_day:"2026-11-10",desired:"off",status:"ok"},
      {entity_id:"light.b",copy_day:"2026-11-11",desired:"on",status:"ok"}
    ]
  };
  let saved=null;
  card._save=async changes=>{saved=changes;};
  card._refreshStates();
  assert.equal(card._lightList.children.length,2);
  const first=card._lightList.children[0];
  assert.equal(first.children[0].children[0].children[0].textContent,"Kitchen Main");
  assert.equal(first.children[0].children[0].children[1].textContent,"light.a");
  const metrics=first.children[1].children.map(x=>x.children.map(y=>y.textContent));
  assert.deepEqual(metrics,[
    [card.t.date,"2026-11-10"],[card.t.actual,card.t.on],
    [card.t.desired,card.t.off],[card.t.status,card.t.ok]
  ]);
  const remove=first.children[0].children[1];
  assert.equal(remove.attrs["aria-label"],card.t.remove+": Kitchen Main");
  assert.equal(remove.children[0].attrs.icon,"mdi:delete-outline");
  remove.handlers.click();
  assert.deepEqual(saved,{lights:["light.b"]});
  assert.equal(remove.disabled,true);
});

test("combined light list keeps stale calculations hidden during rebuild", () => {
  const card=new Card();
  const node=(tag,attrs={},value)=>({
    tagName:tag,textContent:value,children:[],
    setAttribute(){},addEventListener(){},append(...xs){this.children.push(...xs);},
    replaceChildren(...xs){this.children=[...xs];}
  });
  card._el=node;
  card._lightList=node("ul");
  card._hass={states:{"light.a":{state:"on",attributes:{}}}};
  card._snapshot={ready:false,settings:{lights:["light.a"]},
    lights:[{entity_id:"light.a",copy_day:"2025-01-01",desired:"off",status:"ok"}]};
  card._refreshStates();
  const values=card._lightList.children[0].children[1].children.map(x=>x.children[1].textContent);
  assert.deepEqual(values,["—",card.t.on,card.t.recalculating,card.t.recalculating]);
});

test("add picker only changes candidate; clicking Add persists it", async () => {
  const source = fs.readFileSync(
    path.join(__dirname, "../custom_components/lightaway/frontend/lightaway-card.js"),
    "utf8"
  );
  const choice = source.slice(
    source.indexOf('const addPicker=this._entityPicker(["light"]'),
    source.indexOf('this._lightList=this._el(')
  );
  assert.match(choice, /this\._lightCandidate=event\.detail\?\.value\|\|""/);
  assert.match(choice, /void this\._save\(\{lights:\[\.\.\.lights,value\]\}\)/);
  assert.equal((choice.match(/this\._save\(/g)||[]).length, 1);
});
