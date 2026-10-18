"use strict";
const $ = id => document.getElementById(id);
let currentJob = null, polling = null, renderedEvents = -1, replayMode = false;
const labels = {local_rule:"Local memory + Gemini",local_prepared:"Local learned rule",local_training:"Local experiments",none:"No memory",raw:"Raw experience",sleep:"Prepared graph",flat:"Prepared text"};
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
  const value = await response.json();
  if (!response.ok) throw new Error(typeof value.detail === "string" ? value.detail : JSON.stringify(value.detail || value));
  return value;
}
function runTime(value){return value?new Date(value).toLocaleString("en-GB",{timeZone:"Europe/Berlin",day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit",second:"2-digit",timeZoneName:"short"}):"Time unavailable";}
function notice(text) { $("notice").textContent = text; $("notice").hidden = !text; }
function el(tag, text, className) { const n = document.createElement(tag); if(text !== undefined)n.textContent=text;if(className)n.className=className;return n; }
function svg(tag, attrs) { const n=document.createElementNS("http://www.w3.org/2000/svg",tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));return n; }
function drawWorld(state) {
  if(!state)return;
  $("world-empty").hidden=true;const root=$("world");root.replaceChildren();root.setAttribute("viewBox",`0 0 ${state.width*48+32} ${state.height*48+32}`);
  root.setAttribute("aria-label",`Evaluator world view at tick ${state.tick}; this full map is not sent to the model.`);
  const walls=new Set(state.walls.map(p=>p.join(",")));
  for(let y=0;y<state.height;y++)for(let x=0;x<state.width;x++)root.append(svg("rect",{x:x*48+16,y:y*48+16,width:45,height:45,rx:5,fill:walls.has(`${x},${y}`)?"#647260":"#f5f7ef",opacity:walls.has(`${x},${y}`)?0.7:0.95}));
  for(const [id,o] of Object.entries(state.objects)){
    const [x,y]=o.position;const cx=x*48+38,cy=y*48+38;
    if(o.kind==="switch"){const active=Object.values(state.robots).some(p=>p[0]===x&&p[1]===y);root.append(svg("rect",{x:cx-14,y:cy-14,width:28,height:28,rx:5,fill:active?"#cce88a":"#dce4d0",stroke:"#82986a","stroke-width":2}));}
    if(o.kind==="gate"){root.append(svg("rect",{x:cx-14,y:cy-20,width:28,height:40,rx:3,fill:state.gate_open?"#b5d29a":"#c5946c"}));for(let n=-8;n<=8;n+=8)root.append(svg("line",{x1:cx+n,y1:cy-15,x2:cx+n,y2:cy+15,stroke:state.gate_open?"#71935a":"#795436","stroke-width":2}));}
    if(o.kind==="target"){root.append(svg("circle",{cx,cy,r:14,fill:"none",stroke:"#5e8c50","stroke-width":2,"stroke-dasharray":"4 3"}));const t=svg("text",{x:cx,y:cy+4,"text-anchor":"middle",fill:"#456a3e","font-size":12});t.textContent="✦";root.append(t);}
  }
  const colors={a:"#43875c",b:"#9e78c1",c:"#dca657"};const occupied={};
  for(const [id,p] of Object.entries(state.robots)){const key=p.join(","),n=occupied[key]||0;occupied[key]=n+1;const cx=p[0]*48+38+n*10,cy=p[1]*48+38+n*5;root.append(svg("circle",{cx,cy,r:12,fill:colors[id],stroke:"#fffefa","stroke-width":2}));const t=svg("text",{x:cx,y:cy+4,"text-anchor":"middle",fill:"white","font-size":11,"font-weight":700});t.textContent=id.toUpperCase();root.append(t);}
  $("tick").textContent=`Tick ${state.tick} · evaluator view`;
}
function drawTimeline(events){
  const signature=JSON.stringify(events.map(e=>[e.episode_id,e.tick]));if(signature===renderedEvents)return;renderedEvents=signature;$("timeline").replaceChildren();$("event-count").textContent=`${events.length} RECENT OBSERVATIONS`;
  for(const event of [...events].reverse().slice(0,80)){const item=el("li");item.append(el("span",`${event.recorded_at?runTime(event.recorded_at)+" · ":""}T${event.tick} · ROBOT ${event.action.robot_id.toUpperCase()} · ${event.outcome}`,"event-tag"));item.append(el("span",`Actual: [${event.before.position}] → [${event.after.position}] · ${event.action.operation} ${event.action.direction||""}`,"event-tag"));item.append(el("span",event.explanation || `${event.action.operation}${event.action.direction?" "+event.action.direction:""}`));$("timeline").append(item);}
}
function drawResults(rows){$("results").replaceChildren();for(const row of rows){const tr=el("tr");for(const value of [labels[row.condition]||row.condition,row.seed,row.success?"Success":row.termination,row.actions??"—",row.model_calls??"—",row.elapsed_seconds!==undefined?`${row.elapsed_seconds.toFixed(1)}s`:"—"])tr.append(el("td",String(value)));$("results").append(tr);}}
function setBusy(busy){for(const id of ["explore","sleep","transfer","evaluate","preview","check-connections","local-audit","local-learn","local-transfer"])$(id).disabled=busy;$("cancel").disabled=!busy;}
function showJob(job){
  $("job-status").textContent=`${runTime(job.started_at||job.created_at)} · ${job.action} · ${job.id.slice(-8)} · ${job.status}${job.rate_wait_seconds > 0 ? ` · quota pause ${Math.ceil(job.rate_wait_seconds)}s` : ""}`;$("run-mode").textContent=replayMode?"Recorded replay":`Live · ${job.action}`;drawWorld(job.latest_snapshot);drawTimeline(job.events||[]);
  if(job.error)notice(`Run failed: ${job.error.code}. ${job.error.note} ${(job.error.validation_errors||[]).map(e=>`${(e.loc||[]).join(".")}: ${e.msg}`).join("; ")}`);
  if(job.result){const result=job.result;
    if(result.local_rule)showLocalRule(result.local_rule);
    if(result.result){const row=result.result;if(row.kind==="discovery"){$("episode-id").value=row.episode_id;$("artifact-id").value="";}else drawResults([row]);if(row.errors?.length)notice(`Run ended: ${row.termination}. ${row.errors.map(e=>e.code||e.type).join(", ")}`);}
    else if(result.artifact){$("artifact-id").value=result.id;showMemory(result);$("seed").value=101;}
    else if(result.results)drawResults(result.results);
  }
}
async function poll(){if(!currentJob)return;try{const job=await api(`/api/jobs/${currentJob}`);showJob(job);const busy=["queued","running"].includes(job.status);setBusy(busy);if(!busy){clearInterval(polling);polling=null;await refreshReplays();await refreshSources();}}catch(e){notice(e.message);clearInterval(polling);polling=null;setBusy(false);}}
async function start(action){notice("");if(action==="sleep"&&!$("episode-id").value.trim()){notice("Choose a completed discovery episode above before preparing memory.");return;}replayMode=false;renderedEvents=-1;const data={action,seed:Number($("seed").value),max_actions:Number($("actions").value),episode_id:$("episode-id").value.trim(),artifact_id:$("artifact-id").value.trim(),condition:$("condition").value};if(action.startsWith("local_")){data.max_actions=250;if(action==="local_transfer")data.seed=Number($("local-seed").value);}try{setBusy(true);const job=await api("/api/jobs",data);currentJob=job.id;showJob(job);clearInterval(polling);polling=setInterval(poll,1200);await poll();}catch(e){notice(e.message);setBusy(false);}}
function showMemory(data){const target=$("memory-content");target.replaceChildren();const a=data.artifact;target.append(el("p",a.summary,"muted"));
  for(const h of a.hypotheses){const card=el("article",undefined,"memory-card");card.append(el("span","HYPOTHESIS · CANDIDATE","candidate"));card.append(el("p",h.description));card.append(el("div",`${h.evidence_ids.length} observation(s) → ${h.local_id}`,"evidence-path"));if(h.unresolved_questions.length)card.append(el("p",`Still unknown: ${h.unresolved_questions.join(" ")}`));target.append(card);}
  for(const p of a.procedures){const card=el("article",undefined,"memory-card");card.append(el("span","PROCEDURE · CANDIDATE","candidate"));card.append(el("h3",p.title));card.append(el("p",`Requires: ${p.preconditions.join("; ")}`));const list=el("ol");p.steps.forEach(s=>list.append(el("li",s)));card.append(list);if(p.ongoing_conditions?.length)card.append(el("p",`Keep true: ${p.ongoing_conditions.join("; ")}`));card.append(el("div",`${p.hypothesis_ids.join(" + ")} → ${p.title}`,"evidence-path"));target.append(card);}
  if(data.graph){const details=el("details"),summary=el("summary",`Inspect ${data.graph.evidence_paths.length} evidence paths`);details.append(summary);for(const path of data.graph.evidence_paths){details.append(el("p",`${path.procedure.title} → ${path.hypothesis.description} → ${path.observation_id}`,"evidence-path"));details.append(el("pre",JSON.stringify(path.observation,null,2)));}target.append(details);}
}
async function refreshSources(){
 const [e,a]=await Promise.all([api('/api/episodes'),api('/api/artifacts')]);
 const episodes=e.episodes.filter(x=>x.kind==='discovery'&&x.status!=='running');
 for(const [selectId,inputId,items] of [['episode-select','episode-id',episodes],['artifact-select','artifact-id',a.artifacts]]){
  const select=$(selectId);select.replaceChildren();const empty=el('option',items.length?'Choose a saved record':'No completed records yet');empty.value='';select.append(empty);
  for(const item of items){const option=el('option',`${runTime(item.created_at)} · ${item.status||'prepared'} · ${item.id.slice(-8)}`);option.value=item.id;select.append(option);}
  if(!$(inputId).value&&items.length){const preferred=inputId==="artifact-id"?items.find(x=>x.episode_id===$("episode-id").value):items[0];if(preferred)$(inputId).value=preferred.id;}
  select.value=$(inputId).value;
 }
}
async function refreshReplays(){const data=await api("/api/replays");$("replay-select").replaceChildren();const first=el("option",data.replays.length?"Select a recording":"No recordings yet");first.value="";$("replay-select").append(first);for(const item of data.items){const opt=el("option",`${runTime(item.started_at||item.created_at)} · ${item.action} · ${item.status} · ${item.id.slice(-8)}`);opt.value=item.id;$("replay-select").append(opt);}}

async function loadStatus(){const c=await api("/api/config-status");$("host").value=c.database_host;$("port").value=c.database_port;$("username").value=c.database_username;$("tls").checked=c.database_tls;$("connection-pill").textContent=c.model_key_configured?"Model configured":"API key needed";$("job-status").textContent=c.model_key_configured?"Ready for connection check":"Add Gemini API key";if(!c.model_key_configured)$("connections").hidden=false;}
$("connections-toggle").onclick=()=>{$("connections").hidden=!$("connections").hidden;};
$("connection-form").onsubmit=async event=>{event.preventDefault();try{await api("/api/config",{host:$("host").value.trim(),port:Number($("port").value),username:$("username").value.trim(),tls:$("tls").checked,password:$("password").value||null,api_key:$("api-key").value||null});$("password").value="";$("api-key").value="";$("connection-result").textContent="Saved locally. Check connections before running.";await loadStatus();}catch(e){notice(e.message);}};
$("check-connections").onclick=async()=>{const button=$("check-connections");button.disabled=true;$("connection-result").textContent="Checking database and model…";try{const r=await api("/api/check-connections",{});$("connection-result").textContent=`Database: ${r.database}${r.database_error?" ("+r.database_error+")":""}. Model: ${r.model}${r.model_error?" ("+r.model_error+")":""}.`;$("connection-pill").textContent=r.database==="verified"&&r.model==="verified"?"Connections verified":"Setup incomplete";}catch(e){notice(e.message);}finally{button.disabled=false;}};
$("explore").onclick=()=>start("discover");$("sleep").onclick=()=>start("sleep");$("transfer").onclick=()=>start("transfer");$("evaluate").onclick=()=>start("evaluate");
$("cancel").onclick=async()=>{if(currentJob){try{await api(`/api/jobs/${currentJob}/cancel`,{});notice("Stop requested. The current API request may finish before the run stops.");}catch(e){notice(e.message);}}};
$("preview").onclick=async()=>{try{const data=await api(`/api/world-preview?seed=${Number($("seed").value)}`);drawWorld(data);$("run-mode").textContent="Engine preview · no AI";}catch(e){notice(e.message);}};
$("load-memory").onclick=async()=>{try{const id=$("artifact-id").value.trim();if(!id)throw new Error("Run the sleep phase or enter a saved artifact ID first.");showMemory(await api(`/api/artifacts/${encodeURIComponent(id)}`));}catch(e){notice(e.message);}};
$("refresh-replays").onclick=()=>refreshReplays().catch(e=>notice(e.message));
$("load-replay").onclick=async()=>{const id=$("replay-select").value;if(!id)return;try{if(polling)throw new Error("Wait for the active run before loading a replay.");replayMode=true;renderedEvents=-1;showJob(await api(`/api/replays/${encodeURIComponent(id)}`));}catch(e){notice(e.message);}};
async function resumeActiveJob(){const data=await api("/api/jobs");const job=data.jobs.find(j=>["queued","running"].includes(j.status));if(job){currentJob=job.id;setBusy(true);polling=setInterval(poll,1200);await poll();}}
$("episode-select").onchange=()=>{$("episode-id").value=$("episode-select").value;$("artifact-id").value="";refreshSources().catch(e=>notice(e.message));};
$("artifact-select").onchange=()=>{$("artifact-id").value=$("artifact-select").value;};
Promise.all([loadStatus(),refreshReplays(),refreshSources(),resumeActiveJob()]).catch(e=>notice(e.message));

function showLocalRule(rule){if(rule&&(rule.training_seeds||[]).includes(Number($("local-seed").value))){let next=701;while(rule.training_seeds.includes(next))next++;$("local-seed").value=next;}$("local-rule-status").textContent=rule?`${rule.status} · 0 API calls\nOccupancy → gate open: ${JSON.stringify(rule.table)}\nMissing cases: ${rule.missing_cases.join(", ")||"none"}\nContradictions: ${rule.contradictions.join(", ")||"none"}\nTraining seeds (do not reuse for transfer): ${(rule.training_seeds||[]).join(", ")}\n${rule.scope}`:"No local rule yet. Review past events or run local experiments.";}
$("local-audit").onclick=()=>start("local_audit");
$("local-learn").onclick=()=>start("local_learn");
$("local-transfer").onclick=()=>start("local_transfer");
api("/api/local-rule").then(data=>showLocalRule(data.local_rule)).catch(e=>notice(e.message));

$("condition").onchange=async()=>{if($("condition").value!=="local_rule")return;try{const {local_rule:r}=await api("/api/local-rule");if(!r){notice("Run local learning first. No sleep artifact is needed for this option.");return;}let seed=701;while((r.training_seeds||[]).includes(seed))seed++;$("seed").value=seed;notice(`Gemini will retrieve local rule ${r.id} (${r.status}) from FalkorDB. No sleep preparation is needed. This transfer uses API calls; local transfer remains free of provider calls.`);}catch(e){notice(e.message);}};

if(location.hash==='#connections')$('connections').hidden=false;


let replayFrames = [], replayEvents = [], replaySeed = null, frameTimer = null;
const originalShowJob = showJob;
showJob = function(job) {
  if(frameTimer){clearInterval(frameTimer);frameTimer=null;}
  originalShowJob(job);
  replaySeed = job.result?.result?.seed ?? null;
  if(replaySeed !== null) $("seed").value = replaySeed;
  replayFrames = job.result?.evaluator_snapshots || [];
  replayEvents = job.result?.events || job.events || [];
  $("play-replay").disabled = replayFrames.length < 2 || ["queued","running"].includes(job.status);
  $("play-replay").textContent = "Play recorded actions";
};
$("play-replay").onclick=()=>{
  if(frameTimer){clearInterval(frameTimer);frameTimer=null;$("play-replay").textContent="Play recorded actions";return;}
  let index=0;
  $("play-replay").textContent="Stop playback";
  const frame=()=>{
    const state=replayFrames[index++];
    if(!state){clearInterval(frameTimer);frameTimer=null;$("play-replay").textContent="Play recorded actions";return;}
    drawWorld(state);drawTimeline(replayEvents.filter(e=>e.tick<=state.tick));
    $("run-mode").textContent=`Recorded playback · seed ${replaySeed} · ${index}/${replayFrames.length}`;
  };
  frame();frameTimer=setInterval(frame,300);
};
