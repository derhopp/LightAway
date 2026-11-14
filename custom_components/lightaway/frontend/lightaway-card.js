/* LightAway Lovelace card. No external JavaScript dependencies. */
const translations = {
  en: {
    title: "LightAway", presence: "Presence entity", invert: "Invert presence",
    lights: "Lights", simulation: "Enable simulation",
    minWeeks: "Min. Weeks from today", maxWeeks: "Max. Weeks away",
    recentWeeks: "Use recent Weeks", sameCopyDay: "Just same copy day",
    invalidWeeks: "Enter a valid whole number in the allowed range.",
    source: "Light", date: "Copy day", actual: "Actual", desired: "Desired",
    status: "Status", saved: "Configuration saved automatically",
    choose: "Search by name or entity ID", empty: "No lights selected",
    select: "Selected lights", addLight: "Add a light",
    lightField: "Light", duplicate: "This light is already selected",
    searchHint: "Type a name or entity ID to search. Changes are saved automatically.",
    loading: "Loading LightAway…",
    error: "Failed to load LightAway", active: "Present", away: "Away",
    invalid: "Unknown", on: "On", off: "Off", unavailable: "Unavailable",
    ok: "Valid", no_copy_day: "No suitable copy day",
    recorder_unavailable: "Recorder data unavailable",
    insufficient_history: "Insufficient valid historical states",
    light_unavailable: "Light unavailable", light_missing: "Light deleted",
    presence_not_configured: "Presence entity not configured",
    presence_unavailable: "Presence entity unavailable",
    calculation_error: "Calculation error", switch_error: "Light switching failed",
    recalculating: "Recalculating", updating: "Updating copy days…",
    select_hint: "Choose any number of lights",
    config: "Configuration", monitor: "Monitoring",
    admin: "Configuration changes require administrator permissions.",
  },
  de: {
    title: "LightAway", presence: "Anwesenheits-Entität", invert: "Anwesenheit invertieren",
    lights: "Leuchten", simulation: "Simulation aktivieren",
    minWeeks: "Min. Wochen Abstand zu heute", maxWeeks: "Max. Wochen Abstand",
    recentWeeks: "Neuere Wochen verwenden", sameCopyDay: "Nur gemeinsamer Kopiertag",
    invalidWeeks: "Bitte eine ganze Zahl im erlaubten Bereich eingeben.",
    source: "Licht", date: "Kopiertag", actual: "Ist-Zustand", desired: "Soll-Zustand",
    status: "Status", saved: "Konfiguration automatisch gespeichert",
    choose: "Nach Name oder Entity-ID suchen", empty: "Keine Leuchten ausgewählt",
    select: "Ausgewählte Leuchten", addLight: "Leuchte hinzufügen",
    lightField: "Leuchte", duplicate: "Diese Leuchte ist bereits ausgewählt",
    searchHint: "Nach Name oder Entity-ID suchen. Änderungen werden automatisch gespeichert.",
    loading: "LightAway wird geladen…",
    error: "LightAway konnte nicht geladen werden", active: "Anwesend", away: "Abwesend",
    invalid: "Unbekannt", on: "An", off: "Aus", unavailable: "Nicht verfügbar",
    ok: "Gültig", no_copy_day: "Kein geeigneter Kopiertag",
    recorder_unavailable: "Recorder-Daten nicht verfügbar",
    insufficient_history: "Zu wenige gültige historische Zustände",
    light_unavailable: "Leuchte nicht verfügbar", light_missing: "Leuchte gelöscht",
    presence_not_configured: "Anwesenheits-Entität nicht konfiguriert",
    presence_unavailable: "Anwesenheits-Entität nicht verfügbar",
    calculation_error: "Berechnungsfehler", switch_error: "Lichtschaltung fehlgeschlagen",
    recalculating: "Neuberechnung", updating: "Kopiertage werden aktualisiert…",
    select_hint: "Beliebig viele Leuchten auswählen",
    config: "Konfiguration", monitor: "Überwachung",
    admin: "Konfigurationsänderungen erfordern Administratorrechte.",
  }
};
const css = `
:host{display:block;color:var(--primary-text-color)}
ha-card{padding:16px;overflow:hidden}
h2{font-size:1.2rem;margin:0 0 12px}
h3{font-size:1rem;margin:18px 0 8px}
.flex{display:flex;flex-wrap:wrap;gap:14px;align-items:center}
.field{min-width:215px;flex:1}
label{display:block;font-size:.875rem;margin-bottom:5px}
ha-entity-picker{display:block;width:100%;min-width:0}
input[type=number]{display:block;box-sizing:border-box;width:100%;min-height:40px;background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:6px;padding:8px;color:var(--primary-text-color);font:inherit}
.entity-fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:12px;align-items:start}
.helper{color:var(--secondary-text-color);font-size:.85rem;line-height:1.4}
label.toggle{display:flex;gap:8px;align-items:center;cursor:pointer}
input[type=checkbox]{accent-color:var(--primary-color);width:18px;height:18px}
table{border-collapse:collapse;width:100%}
th,td{border-bottom:1px solid var(--divider-color);padding:10px 6px;text-align:left;overflow-wrap:anywhere}
th{font-size:.82rem;color:var(--secondary-text-color)}
.status{font-size:.85rem}
.message{margin-top:12px;font-size:.9rem;color:var(--secondary-text-color)}
.update-progress{display:flex;align-items:center;gap:9px;font-size:.92rem;font-weight:500;margin:10px 0;color:var(--primary-text-color)}
.update-progress[hidden]{display:none}
.update-spinner{display:inline-block;width:15px;height:15px;border:2px solid var(--divider-color);border-top-color:var(--primary-color);border-radius:50%;animation:lightaway-spin .9s linear infinite;flex-shrink:0}
@keyframes lightaway-spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.update-spinner{animation:none}}
@media(max-width:650px){
thead{display:none}
tr{display:block;border-bottom:1px solid var(--divider-color);padding:8px 0}
td{display:flex;border:0;padding:4px 0;gap:12px}
td::before{content:attr(data-label);font-weight:600;min-width:100px;max-width:38%}
}
`;
class LightAwayCard extends HTMLElement {
  setConfig(config) { this._config = config; this._draw(); }
  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if(first) this._load();
    else if(this._snapshot) this._refreshStates();
    if(this.isConnected) void this._subscribeUpdates();
  }
  getCardSize(){return 5;}
  connectedCallback(){
    if (!this._timer) this._timer = setInterval(() => this._load(true), 15000);
    void this._subscribeUpdates();
  }
  disconnectedCallback(){
    clearInterval(this._timer);
    this._timer=null;
    this._unsubscribeUpdates?.();
    this._unsubscribeUpdates=null;
  }
  async _subscribeUpdates(){
    if(this._unsubscribeUpdates||this._subscribingUpdates
      ||!this._hass?.connection?.subscribeEvents)return;
    this._subscribingUpdates=true;
    try{
      const unsubscribe=await this._hass.connection.subscribeEvents(
        ()=>void this._load(true), "lightaway_updated"
      );
      if(this.isConnected)this._unsubscribeUpdates=unsubscribe;
      else unsubscribe();
    }catch(error){
      // Polling remains available if event subscriptions are not permitted.
    }finally{
      this._subscribingUpdates=false;
    }
  }
  get t(){return translations[(this._hass?.language || "").toLowerCase().startsWith("de")?"de":"en"];}
  async _load(silent=false){
    if(!this._hass) return;
    if(this._loading){this._refreshRequested=true;return;}
    this._loading=true;
    try{
      const data=await this._hass.callWS({type:"lightaway/status"});
      const previous=JSON.stringify(this._snapshot?.settings);
      this._snapshot=data;
      if(this._pendingWrites){
        this._refreshStates();
      }else if (!silent || previous!==JSON.stringify(data.settings) || !this._root){
        this._draftSettings={...data.settings};
        this._draw();
      }else this._refreshStates();
    }catch(error){
      if(!silent){this._error=String(error);this._draw();}
    }finally{
      this._loading=false;
      if(this._refreshRequested){
        this._refreshRequested=false;
        void this._load(true);
      }
    }
  }
  _el(tag,attrs={},value){
    const el=document.createElement(tag);
    for(const [key,val] of Object.entries(attrs)){
      if(key==="class") el.className=val;
      else if(key==="type" || key==="value") el.setAttribute(key,val);
    }
    if(value!==undefined)el.textContent=value;
    return el;
  }
  _entityPicker(domains,value,label,placeholder){
    const picker=this._el("ha-entity-picker");
    picker.includeDomains=domains;
    picker.showEntityId=true;
    picker.value=value;
    picker.label=label;
    picker.placeholder=placeholder;
    return picker;
  }
  _showMessage(message){
    if(this._message)this._message.textContent=message;
  }
  _updateProgress(){
    if(!this._progress||!this._snapshot)return;
    const busy=Boolean(this._pendingWrites)||!this._snapshot.ready;
    this._progress.hidden=!busy;
    this._progressText.textContent=busy?this.t.updating:"";
  }
  async _save(changes){
    // Serialize writes to avoid losing rapid edits to different fields.
    const next={...(this._draftSettings||this._snapshot?.settings||{}),...changes};
    this._draftSettings=next;
    this._pendingWrites=(this._pendingWrites||0)+1;
    const task=async()=>{
      const data=await this._hass.callWS({type:"lightaway/configure",...changes});
      this._snapshot=data;
      return data;
    };
    const pending=(this._saveChain||Promise.resolve()).catch(()=>{}).then(task);
    this._saveChain=pending;
    try{
      await pending;
      this._pendingWrites--;
      if(this._pendingWrites===0){
        this._draftSettings={...this._snapshot.settings};
        this._draw();
        this._showMessage(this.t.saved);
      }
    }catch(error){
      this._pendingWrites--;
      if(this._pendingWrites===0){
        this._draftSettings=null;
        await this._load();
        this._showMessage(this.t.admin+" "+String(error));
      }
    }
  }
  _draw(){
    if(!this._hass)return;
    const t=this.t;
    if(!this._shadow){
      this._shadow=this.attachShadow({mode:"open"});
      this._shadow.innerHTML="<style>"+css+"</style>";
    }
    this._root?.remove();
    const card=this._el("ha-card");
    card.append(this._el("h2",{},t.title));
    if(!this._snapshot){
      card.append(this._el("p",{},this._error?t.error+": "+this._error:t.loading));
      this._shadow.append(card);this._root=card;return;
    }
    card.append(this._el("h3",{},t.config));
    const settings=this._snapshot.settings;
    const flex=this._el("div",{class:"flex"});
    const presence=this._el("div",{class:"field"});
    const presencePicker=this._entityPicker(
      ["binary_sensor","switch","input_boolean"],settings.presence||"",t.presence,t.choose
    );
    presencePicker.addEventListener("value-changed",event=>{
      const value=event.detail?.value||null;
      if(value===(this._draftSettings?.presence??null))return;
      void this._save({presence:value});
    });
    presence.append(presencePicker);flex.append(presence);
    const invertWrap=this._el("label",{class:"toggle"});
    const invert=this._el("input",{type:"checkbox"});
    invert.checked=!!settings.invert;
    invert.addEventListener("change",()=>void this._save({invert:invert.checked}));
    invertWrap.append(invert,document.createTextNode(t.invert));flex.append(invertWrap);
    const enableWrap=this._el("label",{class:"toggle"});
    const enable=this._el("input",{type:"checkbox"});
    enable.checked=!!settings.enabled;
    enable.addEventListener("change",()=>void this._save({enabled:enable.checked}));
    enableWrap.append(enable,document.createTextNode(t.simulation));flex.append(enableWrap);
    card.append(flex);
    const ranges=this._el("div",{class:"flex"});
    for(const [key,translation,minimum] of [
      ["min_weeks_from_today",t.minWeeks,1],
      ["max_weeks_away",t.maxWeeks,2],
    ]){
      const field=this._el("div",{class:"field"});
      const label=this._el("label",{},translation);
      const input=this._el("input",{type:"number"});
      input.value=String(settings[key]??(key==="min_weeks_from_today"?1:8));
      input.min=String(minimum);
      input.max="52";
      input.step="1";
      input.setAttribute("aria-label",translation);
      input.addEventListener("change",()=>{
        const number=Number(input.value);
        if(input.value.trim()===""||!Number.isInteger(number)||number<minimum||number>52){
          this._showMessage(t.invalidWeeks);
          input.value=String(this._draftSettings?.[key]??settings[key]);
          return;
        }
        if(number!==this._draftSettings?.[key])void this._save({[key]:number});
      });
      field.append(label,input);
      ranges.append(field);
    }
    for(const [key,translation] of [
      ["use_recent_weeks",t.recentWeeks],
      ["just_same_copy_day",t.sameCopyDay],
    ]){
      const row=this._el("label",{class:"toggle"});
      const input=this._el("input",{type:"checkbox"});
      input.checked=!!settings[key];
      input.addEventListener("change",()=>void this._save({[key]:input.checked}));
      row.append(input,document.createTextNode(translation));
      ranges.append(row);
    }
    card.append(ranges);
    const presenceValue=this._snapshot.presence_status;
    card.append(this._el("p",{class:"message"},!settings.presence?t.presence_not_configured:(presenceValue===null?t.presence_unavailable:(presenceValue?t.active:t.away))));
    card.append(this._el("h3",{},t.select));
    card.append(this._el("p",{class:"helper"},t.searchHint));
    const entityFields=this._el("div",{class:"entity-fields"});
    for(const [index,light] of settings.lights.entries()){
      const picker=this._entityPicker(["light"],light,`${t.lightField} ${index+1}`,t.choose);
      picker.addEventListener("value-changed",event=>{
        const replacement=event.detail?.value||null;
        const lights=[...(this._draftSettings?.lights||settings.lights)];
        const currentIndex=lights.indexOf(light);
        if(currentIndex===-1)return;
        if(replacement===light)return;
        if(replacement&&lights.includes(replacement)){
          picker.value=light;
          this._showMessage(t.duplicate);
          return;
        }
        if(replacement)lights[currentIndex]=replacement;
        else lights.splice(currentIndex,1);
        void this._save({lights});
      });
      entityFields.append(picker);
    }
    // Always provide a searchable field, never render the entire entity list.
    const addPicker=this._entityPicker(["light"],"",t.addLight,t.choose);
    addPicker.addEventListener("value-changed",event=>{
      const value=event.detail?.value;
      if(!value)return;
      const lights=[...(this._draftSettings?.lights||settings.lights)];
      // Keep the selection visible until the server acknowledges the save.
      if(lights.includes(value)){
        this._showMessage(t.duplicate);
        return;
      }
      void this._save({lights:[...lights,value]});
    });
    entityFields.append(addPicker);
    card.append(entityFields);
    card.append(this._el("h3",{},t.monitor));
    this._progress=this._el("div",{class:"update-progress"});
    this._progress.setAttribute("role","status");
    this._progress.setAttribute("aria-live","polite");
    const spinner=this._el("span",{class:"update-spinner"});
    spinner.setAttribute("aria-hidden","true");
    this._progressText=this._el("span");
    this._progress.append(spinner,this._progressText);
    card.append(this._progress);
    const table=this._el("table");
    const head=this._el("thead");const headers=this._el("tr");
    for(const label of [t.source,t.date,t.actual,t.desired,t.status])headers.append(this._el("th",{},label));
    head.append(headers);table.append(head);
    this._tbody=this._el("tbody");table.append(this._tbody);
    card.append(table);
    this._message=this._el("p",{class:"message"});
    card.append(this._message);
    this._shadow.append(card);
    this._root=card;
    this._refreshStates();
  }
  _name(id){return this._hass?.states?.[id]?.attributes?.friendly_name||id;}
  _refreshStates(){
    if(!this._tbody||!this._snapshot)return;
    this._updateProgress();
    const t=this.t;this._tbody.replaceChildren();
    for(const item of this._snapshot.lights){
      const row=this._el("tr");
      const state=this._hass.states[item.entity_id];
      const cells=[
        this._name(item.entity_id),
        item.copy_day||"—",
        state?.state==="on"?t.on:(state?.state==="off"?t.off:t.unavailable),
        !this._snapshot.ready||item.status==="recalculating"?t.recalculating:
          item.desired==null?t.unavailable:t[item.desired],
        !this._snapshot.ready?t.recalculating:(t[item.status]||item.status||t.invalid),
      ];
      [t.source,t.date,t.actual,t.desired,t.status].forEach((label,i)=>{
        const td=this._el("td",{class:i===4?"status":""},cells[i]);
        td.setAttribute("data-label",label);row.append(td);
      });
      this._tbody.append(row);
    }
    if(!this._snapshot.lights.length){
      const row=this._el("tr");row.append(this._el("td",{},t.empty));this._tbody.append(row);
    }
  }
}
if(!customElements.get("lightaway-card"))customElements.define("lightaway-card",LightAwayCard);
window.customCards=window.customCards||[];
if(!window.customCards.some(card=>card.type==="lightaway-card")){
  window.customCards.push({type:"lightaway-card",name:"LightAway",
    description:"Historical light simulation and dashboard configuration"});
}
