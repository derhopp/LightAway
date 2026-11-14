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
    combinedList: "Selected lights & monitoring",
    lightField: "Light", duplicate: "This light is already selected",
    add: "Add light", remove: "Remove light", removeLabel: "Remove",
    searchHint: "Search by name or entity ID, then use Add. Remove lights with the trash icon; changes are saved automatically.",
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
    combinedList: "Leuchten & Überwachung",
    lightField: "Leuchte", duplicate: "Diese Leuchte ist bereits ausgewählt",
    add: "Hinzufügen", remove: "Leuchte entfernen", removeLabel: "Entfernen",
    searchHint: "Nach Name oder Entity-ID suchen und dann hinzufügen. Leuchten über die Mülltonne entfernen. Änderungen werden automatisch gespeichert.",
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
:host{display:block;box-sizing:border-box;width:100%;max-width:100%;min-width:0;color:var(--primary-text-color)}
*,*::before,*::after{box-sizing:border-box}
ha-card{display:block;width:100%;max-width:100%;min-width:0;padding:16px;overflow:hidden}
h2{font-size:1.2rem;margin:0 0 12px}
h3{font-size:1rem;margin:18px 0 8px}
.flex{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start;min-width:0}
.field{min-width:0;flex:1 1 170px;max-width:100%}
label{display:block;font-size:.875rem;margin-bottom:5px}
ha-entity-picker{display:block;width:100%;max-width:100%;min-width:0}
input[type=number]{display:block;width:100%;min-width:0;min-height:40px;background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:6px;padding:8px;color:var(--primary-text-color);font:inherit}
.picker-control{display:flex;flex-direction:column;align-items:stretch;gap:10px;width:100%;max-width:520px;min-width:0}
.picker-action{align-self:flex-start;min-width:125px;border:0;background:var(--primary-color);color:var(--text-primary-color,#fff);border-radius:8px;min-height:38px;padding:8px 18px;cursor:pointer;font:inherit;font-weight:600}
.picker-action:disabled{opacity:.45;cursor:default}
.switch-options{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,190px),1fr));gap:10px;margin:14px 0;min-width:0}
.helper{color:var(--secondary-text-color);font-size:.85rem;line-height:1.4}
label.toggle{display:flex;gap:8px;align-items:center;cursor:pointer;min-height:36px}
input[type=checkbox]{accent-color:var(--primary-color);width:18px;height:18px;flex-shrink:0}
.light-list{list-style:none;display:flex;flex-direction:column;gap:9px;margin:12px 0 0;padding:0;min-width:0;max-width:100%}
.light-item{border:1px solid var(--divider-color);border-radius:9px;padding:12px;min-width:0;max-width:100%}
.light-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;min-width:0}
.light-details{display:flex;flex:1;flex-direction:column;gap:3px;min-width:0}
.light-name{font-size:.94rem;font-weight:600;overflow-wrap:anywhere}
.light-id{font-size:.8rem;color:var(--secondary-text-color);overflow-wrap:anywhere}
.delete-button{display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;flex:0 0 38px;color:var(--error-color,var(--primary-text-color));background:transparent;border:0;border-radius:8px;cursor:pointer}
.delete-button:hover,.delete-button:focus-visible{background:var(--secondary-background-color)}
.delete-button:disabled{opacity:.4;cursor:default}
.delete-button ha-icon{--mdc-icon-size:20px}
.light-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px;min-width:0}
.light-metric{display:flex;flex-direction:column;gap:4px;min-width:0}
.metric-label{font-size:.75rem;color:var(--secondary-text-color);overflow-wrap:anywhere}
.metric-value{font-size:.9rem;overflow-wrap:anywhere}
.message{margin-top:12px;font-size:.9rem;color:var(--secondary-text-color);overflow-wrap:anywhere}
.update-progress{display:flex;align-items:center;gap:9px;font-size:.92rem;font-weight:500;margin:10px 0;color:var(--primary-text-color)}
.update-progress[hidden]{display:none}
.update-spinner{display:inline-block;width:15px;height:15px;border:2px solid var(--divider-color);border-top-color:var(--primary-color);border-radius:50%;animation:lightaway-spin .9s linear infinite;flex-shrink:0}
@keyframes lightaway-spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.update-spinner{animation:none}}
@media(max-width:700px){.light-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:340px){.light-metrics{grid-template-columns:minmax(0,1fr)}}
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
  getCardSize(){return 6;}
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
    this._updateProgress();
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
    const presence=this._el("div",{class:"picker-control"});
    const presencePicker=this._entityPicker(
      ["binary_sensor","switch","input_boolean"],settings.presence||"",t.presence,t.choose
    );
    presencePicker.addEventListener("value-changed",event=>{
      const value=event.detail?.value||null;
      if(value===(this._draftSettings?.presence??null))return;
      void this._save({presence:value});
    });
    presence.append(presencePicker);
    card.append(presence);
    const optionControls=this._el("div",{class:"switch-options"});
    for(const [key,label] of [
      ["invert",t.invert],["enabled",t.simulation],
      ["use_recent_weeks",t.recentWeeks],["just_same_copy_day",t.sameCopyDay],
    ]){
      const wrapper=this._el("label",{class:"toggle"});
      const input=this._el("input",{type:"checkbox"});
      input.checked=!!settings[key];
      input.addEventListener("change",()=>void this._save({[key]:input.checked}));
      wrapper.append(input,document.createTextNode(label));
      optionControls.append(wrapper);
    }
    card.append(optionControls);
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
    card.append(ranges);
    const presenceValue=this._snapshot.presence_status;
    card.append(this._el("p",{class:"message"},!settings.presence?t.presence_not_configured:(presenceValue===null?t.presence_unavailable:(presenceValue?t.active:t.away))));
    card.append(this._el("h3",{},t.addLight));
    card.append(this._el("p",{class:"helper"},t.searchHint));
    const addControl=this._el("div",{class:"picker-control"});
    const addPicker=this._entityPicker(["light"],"",t.addLight,t.choose);
    this._lightCandidate="";
    addControl.append(addPicker);
    const addButton=this._el("button",{class:"picker-action",type:"button"},t.add);
    addButton.disabled=true;
    addPicker.addEventListener("value-changed",event=>{
      this._lightCandidate=event.detail?.value||"";
      addButton.disabled=!this._lightCandidate||Boolean(this._pendingWrites);
    });
    addButton.addEventListener("click",()=>{
      const value=this._lightCandidate;
      if(!value||this._pendingWrites)return;
      const lights=[...(this._draftSettings?.lights||settings.lights)];
      if(lights.includes(value)){
        this._showMessage(t.duplicate);
        return;
      }
      addButton.disabled=true;
      void this._save({lights:[...lights,value]});
    });
    addControl.append(addButton);
    card.append(addControl);
    card.append(this._el("h3",{},t.combinedList));
    this._progress=this._el("div",{class:"update-progress"});
    this._progress.setAttribute("role","status");
    this._progress.setAttribute("aria-live","polite");
    const spinner=this._el("span",{class:"update-spinner"});
    spinner.setAttribute("aria-hidden","true");
    this._progressText=this._el("span");
    this._progress.append(spinner,this._progressText);
    card.append(this._progress);
    this._lightList=this._el("ul",{class:"light-list"});
    card.append(this._lightList);
    this._message=this._el("p",{class:"message"});
    card.append(this._message);
    this._shadow.append(card);
    this._root=card;
    this._refreshStates();
  }
  _name(id){return this._hass?.states?.[id]?.attributes?.friendly_name||id;}
  _refreshStates(){
    if(!this._lightList||!this._snapshot)return;
    this._updateProgress();
    const t=this.t;
    const info=new Map((this._snapshot.lights||[]).map(item=>[item.entity_id,item]));
    this._lightList.replaceChildren();
    const configured=this._snapshot.settings?.lights||[];
    for(const light of configured){
      const item=info.get(light);
      const busy=!this._snapshot.ready||!item||item.status==="recalculating";
      const state=this._hass?.states?.[light];
      const row=this._el("li",{class:"light-item"});
      const heading=this._el("div",{class:"light-heading"});
      const details=this._el("div",{class:"light-details"});
      details.append(this._el("span",{class:"light-name"},this._name(light)));
      details.append(this._el("span",{class:"light-id"},light));
      const remove=this._el("button",{class:"delete-button",type:"button"});
      remove.setAttribute("aria-label",t.remove+": "+this._name(light));
      remove.setAttribute("title",t.removeLabel);
      remove.disabled=Boolean(this._pendingWrites);
      const icon=this._el("ha-icon");
      icon.setAttribute("icon","mdi:delete-outline");
      remove.append(icon);
      remove.addEventListener("click",()=>{
        if(this._pendingWrites)return;
        const lights=(this._draftSettings?.lights||configured).filter(id=>id!==light);
        remove.disabled=true;
        void this._save({lights});
      });
      heading.append(details,remove);
      row.append(heading);
      const metrics=this._el("div",{class:"light-metrics"});
      const values=[
        [t.date,busy?"—":(item.copy_day||"—")],
        [t.actual,state?.state==="on"?t.on:(state?.state==="off"?t.off:t.unavailable)],
        [t.desired,busy?t.recalculating:(item.desired==null?t.unavailable:t[item.desired])],
        [t.status,busy?t.recalculating:(t[item.status]||item.status||t.invalid)],
      ];
      for(const [label,value] of values){
        const metric=this._el("div",{class:"light-metric"});
        metric.append(this._el("span",{class:"metric-label"},label));
        metric.append(this._el("span",{class:"metric-value"},value));
        metrics.append(metric);
      }
      row.append(metrics);
      this._lightList.append(row);
    }
    if(!configured.length){
      this._lightList.append(this._el("li",{class:"helper"},t.empty));
    }
  }
}
if(!customElements.get("lightaway-card"))customElements.define("lightaway-card",LightAwayCard);
window.customCards=window.customCards||[];
if(!window.customCards.some(card=>card.type==="lightaway-card")){
  window.customCards.push({type:"lightaway-card",name:"LightAway",
    description:"Historical light simulation and dashboard configuration"});
}
