"use strict";
fetch('/api/config-status').then(r=>r.json()).then(c=>{document.getElementById('status').textContent=`FalkorDB ${c.database_host_configured?'configured':'needs setup'} · ${c.model_key_configured?'Model key saved':'Model key needed for live runs'}`;}).catch(()=>{document.getElementById('status').textContent='Open Connections to configure the lab.';});
