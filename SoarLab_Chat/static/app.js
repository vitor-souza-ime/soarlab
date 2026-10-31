'use strict';
const el=id=>document.getElementById(id);
const escapeHtml=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let busy=false;
async function req(path,payload){
 const r=await fetch(path,{method:payload===undefined?'GET':'POST',headers:payload===undefined?{}:{'Content-Type':'application/json'},body:payload===undefined?undefined:JSON.stringify(payload)});
 let data;try{data=await r.json()}catch{throw Error(`Server returned HTTP ${r.status} instead of JSON. Check Flask output or partial benchmark files.`)}
 if(!r.ok||!data.ok)throw Error(data.error||`HTTP ${r.status}`);return data;
}
function say(t,author='assistant',details=''){
 const div=document.createElement('div');div.className='message '+author;
 const bubble=document.createElement('div');bubble.className='bubble';bubble.textContent=t;div.appendChild(bubble);
 if(details){const x=document.createElement('div');x.className='metadata';x.textContent=details;div.appendChild(x)}
 el('messages').appendChild(div);el('messages').scrollTop=el('messages').scrollHeight;
}
function toggleBusy(x){busy=x;el('send-button').disabled=x;el('send-button').textContent=x?'Retrieving…':'Send ↗';}
async function ask(text){
 if(busy||!text.trim())return;toggleBusy(true);say(text,'user');el('question').value='';
 try{const r=(await req('/api/ask',{question:text})).result;
  say(r.text,'assistant',`${r.kind} · ${r.status} · ${r.topic||'no topic'} · ${r.interpretation_method||r.method||'—'} · ${r.latency_ms??'—'} ms · ${r.native_soar?'native Soar':'parser'}`);
  if(r.status==='unknown'&&r.kind==='semantic')say('You may teach this concept using Tools → Teach a new concept. Use the concept name and a definition.','assistant');
  await refresh();
 }catch(e){say('Error: '+e.message,'error')}finally{toggleBusy(false)}
}
function popup(title,html){el('dialog-title').textContent=title;el('dialog-content').innerHTML=html;el('overlay').classList.remove('hidden');el('sidebar').classList.remove('open');}
function close(){el('overlay').classList.add('hidden')}
function field(id,label,placeholder,type='text'){
 return `<div class="field"><label for="${id}">${label}</label>${type==='textarea'?`<textarea id="${id}" rows="4" placeholder="${placeholder}"></textarea>`:`<input id="${id}" placeholder="${placeholder}">`}</div>`;
}
function teach(){popup('Teach a concept to native SMem',`<p class="hint">A new fact is confirmed only after native SMem storage and exact read-after-write retrieval.</p>${field('fact-topic','Concept','e.g. Tactile sensor array')}${field('fact-alias','Alternative names (optional; semicolon-separated)','touch sensor array; tactile matrix')}${field('fact-description','Definition to teach','e.g. A tactile array measures contact over several locations.','textarea')}<button class="primary" id="fact-save">Store and verify in Soar</button><div id="form-status" class="alert">Ready to teach.</div>`);
 el('fact-save').onclick=async()=>{
  const btn=el('fact-save');btn.disabled=true;el('form-status').textContent='Storing and verifying in native SMem…';
  try{const r=(await req('/api/teach',{topic:el('fact-topic').value,aliases:el('fact-alias').value,description:el('fact-description').value})).result;
      el('form-status').textContent=r.text+' Ask about the concept again.';
      say('Taught: '+el('fact-topic').value,'user');say(r.text,'assistant','SMem · native read-after-write verified');await refresh();}
  catch(e){el('form-status').className='alert error';el('form-status').textContent='Storage NOT confirmed: '+e.message}finally{btn.disabled=false}
 };
}
function experience(){popup('Record an experience in EpMem',`<p class="hint">The event is presented to the agent working memory; EpMem records a cognitive episode and must retrieve it before confirmation.</p><div class="field"><label for="event-topic">Event category</label><select id="event-topic"><option value="obstacle">Obstacle</option><option value="battery">Battery</option><option value="sensor">Sensor</option><option value="navigation">Navigation</option><option value="vision">Vision</option><option value="actuator">Actuator</option></select></div>${field('event-description','Observed event','e.g. The robot detected a wall and stopped.','textarea')}<button class="primary" id="event-save">Record and retrieve in Soar</button><div id="form-status" class="alert">Ready.</div>`);
 el('event-save').onclick=async()=>{
  const button=el('event-save');button.disabled=true;el('form-status').textContent='Recording and checking native episode retrieval…';
  try{const r=(await req('/api/experience',{topic:el('event-topic').value,description:el('event-description').value})).result;
   el('form-status').textContent=r.text;say('Recorded '+r.topic+' experience','user');say(r.text,'assistant','EpMem · native retrieval verified');await refresh();}
  catch(e){el('form-status').className='alert error';el('form-status').textContent='Episode NOT confirmed: '+e.message}finally{button.disabled=false}
 };
}
async function inspect(memory){popup('Inspect '+memory+' memory','<p class="hint">Reading Soar native memory statistics…</p>');
 try{const r=await req('/api/inspect/'+memory);el('dialog-content').innerHTML='<pre class="pre">'+escapeHtml(r.raw)+'</pre>'}
 catch(e){el('dialog-content').textContent='Error: '+e.message}
}
async function refresh(){try{const s=(await req('/api/status')).state;
  el('connection').textContent='● Native Soar connected';el('connection').className='connection';
  el('count-rules').textContent=s.procedural_productions;
  el('count-facts').textContent=s.native_verifications.semantic;
  el('count-experiences').textContent=s.verified_episodes;
 }catch(e){el('connection').textContent='● Native integration failed';el('connection').className='connection bad';console.error(e)}}
function showBench(){popup('Research benchmark · 8 figures',`<p class="hint">The fixed benchmark evaluates 48 prespecified questions and controlled paraphrases. Session replay uses questions already asked in this process; session labels are parser-derived, so the score is agreement rather than independent accuracy.</p><div class="field"><label for="bench-mode">Data source</label><select id="bench-mode"><option value="fixed">Fixed evaluation corpus (48 questions)</option><option value="session">Current chat questions (replay)</option></select></div><div class="field"><label for="reps">Repetitions per question (1–15)</label><input id="reps" type="number" min="1" max="15" value="3"></div><div class="field"><label for="bench-seed">Shuffle seed</label><input id="bench-seed" type="number" value="2026"></div><button id="start-bench" class="primary">Run native benchmark</button><div id="benchmark-result" class="alert">No experiment started.</div>`);
 el('start-bench').onclick=async()=>{const b=el('start-bench');b.disabled=true;el('benchmark-result').textContent='Executing native Soar queries. Results appear upon completion.';
  try{const data=(await req('/api/benchmark',{repetitions:Number(el('reps').value),seed:Number(el('bench-seed').value),mode:el('bench-mode').value})).results;
   const prefix='/results/'+encodeURIComponent(data.run_id)+'/';
   const score=data.accuracy===null?'n/a':(data.accuracy*100).toFixed(1)+'%';
   el('benchmark-result').innerHTML=`<p><strong>${data.n} native queries.</strong> ${escapeHtml(data.score_name)}: ${score}</p><p><a href="${prefix}raw.csv">Download raw CSV</a> · <a href="${prefix}metadata.json">Download metadata</a></p><div class="gallery">${data.files.filter(s=>s.endsWith('.png')).map(s=>`<div><a href="${prefix+s}" target="_blank" rel="noopener"><img src="${prefix+s}" loading="lazy" alt="Figure ${escapeHtml(s)}">${escapeHtml(s)}</a></div>`).join('')}</div>`;
  }catch(e){el('benchmark-result').className='alert error';el('benchmark-result').textContent='Benchmark failed: '+e.message;console.error(e)}finally{b.disabled=false}
 };
}
async function showQuestions(){popup('Evaluation questions and paraphrases','<p>Loading the fixed evaluation set…</p>');
 try{const qs=(await req('/api/questions')).questions;el('dialog-content').innerHTML='<p class="hint">These questions have predefined memory/topic reference labels. Facts are retrieved only from Soar. Click a question to submit it.</p><div class="list-questions">'+qs.map(q=>`<button class="probe" data-q="${escapeHtml(q.question)}"><small>${escapeHtml(q.memory)} · ${escapeHtml(q.topic)}</small><br>${escapeHtml(q.question)}</button>`).join('')+'</div>';
  document.querySelectorAll('.probe').forEach(button=>button.onclick=()=>{const q=button.dataset.q;close();ask(q)});
 }catch(e){el('dialog-content').textContent=e.message}
}
el('send-button').onclick=()=>ask(el('question').value);
el('question').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();ask(el('question').value)}});
el('clear-chat').onclick=()=>el('messages').innerHTML='';
el('teach-button').onclick=teach;el('experience-button').onclick=experience;
el('bench-button').onclick=showBench;el('questions-button').onclick=showQuestions;el('refresh-button').onclick=refresh;
el('close-modal').onclick=close;el('overlay').onclick=event=>{if(event.target===el('overlay'))close()};
el('menu-button').onclick=()=>{const sidebar=el('sidebar');sidebar.classList.toggle('open');el('menu-button').setAttribute('aria-expanded',sidebar.classList.contains('open'))};
document.querySelectorAll('[data-inspect]').forEach(button=>button.onclick=()=>inspect(button.dataset.inspect));
document.querySelectorAll('[data-question]').forEach(button => {
    button.onclick = () => ask(button.dataset.question);
});
refresh();
