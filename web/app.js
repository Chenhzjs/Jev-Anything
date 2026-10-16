const $ = id => document.getElementById(id);
let history = [];
function display(event) {
  $('state').textContent = event.kind.toUpperCase();
  if (event.trace_id) $('traceid').textContent = event.trace_id;
  const row = document.createElement('li');
  for (const [tag, text] of [['time',new Date(event.timestamp*1000).toLocaleTimeString()],['b',event.kind],['span',event.outcome?.status || event.reason || event.candidate?.label || '']]) {
    const el=document.createElement(tag);el.textContent=text;row.append(el);
  }
  $('trace').append(row);$('trace').scrollTop=$('trace').scrollHeight;
  if(event.candidates){$('candidates').replaceChildren();for(const c of event.candidates){const el=document.createElement('div');el.textContent=c.id+' · '+c.label;$('candidates').append(el);}}
  if(event.decision){$('decision').textContent=JSON.stringify(event.decision,null,2);$('model').textContent=event.decision.model;}
  if(event.outcome)$('decision').textContent+='\n'+JSON.stringify(event.outcome,null,2);
}
const stream=new EventSource('/api/stream');
stream.onopen=()=>{$('connection').textContent='CONNECTED';};
stream.onerror=()=>{$('connection').textContent='DISCONNECTED';};
stream.onmessage=e=>{const event=JSON.parse(e.data);if(history.some(x=>x.sequence===event.sequence&&x.timestamp===event.timestamp))return;history.push(event);display(event);$('raw').textContent=JSON.stringify(history,null,2);};
async function post(path){const r=await fetch(path,{method:'POST'});if(!r.ok)throw new Error(await r.text());}
$('controls').onsubmit=async e=>{e.preventDefault();try{await post('/api/run?'+new URLSearchParams({goal:$('goal').value,provider:$('provider').value,scenario:$('scenario').value,fixture:$('fixture').value}));}catch(err){$('connection').textContent=err.message;}};
$('pause').onclick=()=>post('/api/pause').catch(e=>$('connection').textContent=e.message);
$('reset').onclick=()=>post('/api/reset?fixture='+encodeURIComponent($('fixture').value)).catch(e=>$('connection').textContent=e.message);
$('replay').onclick=()=>{$('trace').replaceChildren();history.forEach(display);$('state').textContent='RECORDED EVENTS';};
$('gui').onload=()=>{$('freshness').textContent=new Date().toLocaleTimeString();};
$('gui').onerror=()=>{$('freshness').textContent='CAPTURE ERROR';};
async function refresh(){try{const r=await fetch('/api/frame');if(!r.ok)throw new Error('frame unavailable');const f=await r.json();$('terminal').textContent=f.terminal;$('run').disabled=f.busy;$('reset').disabled=f.busy;$('gui').src='/api/gui.png?t='+Date.now();}catch(e){$('freshness').textContent='DISCONNECTED';}setTimeout(refresh,750);}refresh();
