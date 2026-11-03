import {rank,percentile} from './engine.mjs';
const $=id=>document.getElementById(id), fmt=n=>new Intl.NumberFormat('es-ES',{maximumFractionDigits:2}).format(n);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const normalize=s=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
let data,result,candidateId;
function options(id,players,value){$(id).innerHTML=players.map(p=>`<option value="${esc(p.profile_id)}">${esc(p.player_name)} · ${esc(p.team_name)}</option>`).join('');if(players.some(p=>p.profile_id===value))$(id).value=value;}
function references(){
 const previous=$('reference').value, query=normalize($('search').value).trim().split(/\s+/);
 const players=data.players.filter(p=>p.minutes>=Number($('minimum').value) && (!$('team').value || p.team_name===$('team').value) && query.every(q=>normalize(p.player_name).includes(q))).sort((a,b)=>a.player_name.localeCompare(b.player_name,'es'));
 options('reference',players,previous); $('reference').disabled=!players.length;
 if(!players.length){$('identity').innerHTML='<p>No hay referencias con estos filtros. Borra el nombre o amplía el club y los minutos.</p>';$('shortlist').replaceChildren();$('comparison').hidden=true;$('empty').hidden=true;return;}
 update();
}
function update(){
 try{result=rank(data,{reference:$('reference').value,minimum:Number($('minimum').value),priority:$('priority').value,sameRole:$('same-role').checked,club:$('club').value});
 const r=result.ref,initials=r.player_name.split(' ').map(s=>s[0]).slice(0,2).join('');
 $('identity').innerHTML=`<div class="avatar">${esc(initials)}</div><div><p class="eyebrow">TU REFERENCIA</p><h2>${esc(r.player_name)}</h2><p>${esc(r.team_name)} · ${esc(r.role)}</p><p>${fmt(r.minutes)} min · ${r.matches} partidos</p><span class="tag">${esc(r.inferred_role||'Sin perfil inferido')}</span></div>`;
 $('cohort').textContent=`${result.cohort.length} perfiles en la posición · ${result.ranked.length} candidatos`;
 if(!result.ranked.some(p=>p.profile_id===candidateId))candidateId=result.ranked[0]?.profile_id;
 $('shortlist').innerHTML=result.ranked.slice(0,3).map((p,i)=>`<button class="card" data-player="${esc(p.profile_id)}" aria-pressed="${p.profile_id===candidateId}" aria-label="Comparar con ${esc(p.player_name)}"><small>EN LA LISTA / 0${i+1}</small><h3>${esc(p.player_name)}</h3><p>${esc(p.team_name)}</p><p>${esc(p.inferred_role||p.role)} · ${fmt(p.minutes)} min</p><strong class="distance">${p.distance.toFixed(3)}<span>distancia</span></strong><span class="cta">Explorar el parecido ↗</span></button>`).join('');
 $('empty').hidden=!!result.ranked.length;$('comparison').hidden=!result.ranked.length;
 document.querySelectorAll('[data-player]').forEach(button=>button.onclick=()=>{candidateId=button.dataset.player;update();$('comparison').scrollIntoView({behavior:'smooth',block:'start'});});
 options('candidate',result.ranked,candidateId);if(result.ranked.length)comparison();$('error').hidden=true;
 }catch(error){$('error').textContent=error.message;$('error').hidden=false;}
}
function comparison(){
 const p=result.ranked.find(p=>p.profile_id===candidateId),r=result.ref;
 $('comparison-context').textContent=`${r.player_name} frente a ${p.player_name}. Barras: percentiles sobre ${result.cohort.length} perfiles de ${r.role.toLowerCase()}; cifras: valores /90 o porcentaje de pase.`;
 $('bars').innerHTML=result.features.map(f=>`<div class="metric"><div><div class="metric-name">${esc(data.features[f])}</div><div class="tracks"><div class="track"><i style="width:${percentile(result.cohort,r,f)}%"></i></div><div class="track alt"><i style="width:${percentile(result.cohort,p,f)}%"></i></div></div></div><div class="values"><span>${fmt(r[f])} / ${fmt(p[f])}</span><br><small>P${Math.round(percentile(result.cohort,r,f))} / P${Math.round(percentile(result.cohort,p,f))}</small></div></div>`).join('');
 const contributions=result.features.map((f,i)=>({f,c:p.contributions[i]})).sort((a,b)=>a.c-b.c);
 $('explanation').innerHTML=`<strong>Dónde se parecen:</strong> ${esc(contributions.slice(0,2).map(x=>data.features[x.f]).join(' y '))}.<br><strong>Qué los separa:</strong> ${esc(contributions.slice(-2).reverse().map(x=>data.features[x.f]).join(' y '))}.<br>La suma de las contribuciones ponderadas es ${p.contributions.reduce((a,b)=>a+b,0).toFixed(4)}; su raíz cuadrada da la distancia ${p.distance.toFixed(3)}. Describe parecido, no calidad global.`;
}
function download(){const p=result.ranked.find(p=>p.profile_id===candidateId),r=result.ref;const quote=x=>'"'+String(x).replace(/"/g,'""')+'"';const rows=[['Consulta','Métrica',r.player_name,p.player_name,'Percentil referencia','Percentil candidato'],...result.features.map(f=>[data.snapshot,data.features[f],r[f],p[f],percentile(result.cohort,r,f),percentile(result.cohort,p,f)])];const url=URL.createObjectURL(new Blob(['\ufeff'+rows.map(row=>row.map(quote).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='scoutfit-comparacion.csv';a.click();URL.revokeObjectURL(url);}
async function start(){try{const response=await fetch('./data.json');if(!response.ok)throw new Error('No se ha podido cargar la consulta pública.');data=await response.json();
 $('source').innerHTML=`<span>LaLiga masculina · ${esc(data.season)}</span><span>${data.team_count} clubes</span><span>${data.players.length} perfiles</span>`;
 $('date').textContent=`Fuente: ESPN · Consulta: ${new Intl.DateTimeFormat('es-ES',{dateStyle:'medium',timeStyle:'short',timeZone:'Europe/Madrid'}).format(new Date(data.consulted_at))} (Madrid) · Demo de una consulta guardada, sin actualización en directo.`;
 $('evaluation').textContent=`Campaña reproducible: ${data.evaluation.references_planned} referencias y ${data.evaluation.pairs_planned} parejas. Pesos equilibrados, mínimo 450 minutos y otros clubes. Estado: ${data.evaluation.status}.`;
 const clubs=[...new Set(data.players.map(p=>p.team_name))].sort((a,b)=>a.localeCompare(b,'es'));for(const id of ['team','club'])$(id).insertAdjacentHTML('beforeend',clubs.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join(''));
 const params=new URLSearchParams(location.search),requested=params.get('reference');
 references();const defaultRef=data.players.find(p=>p.profile_id===requested&&p.minutes>=450)||data.players.find(p=>p.player_name==='Pedri');if(defaultRef){$('reference').value=defaultRef.profile_id;update();}
 $('search').oninput=references;for(const id of ['team','minimum'])$(id).onchange=references;for(const id of ['reference','priority','same-role','club'])$(id).onchange=update;
 $('candidate').onchange=()=>{candidateId=$('candidate').value;comparison();document.querySelectorAll('[data-player]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.player===candidateId));};
 $('reset').onclick=()=>{$('search').value='';$('team').value='';$('minimum').value='450';$('priority').value='balanced';$('club').value='';$('same-role').checked=false;references();};$('download').onclick=download;
 }catch(error){$('error').textContent=error.message;$('error').hidden=false;$('source').textContent='Consulta no disponible';}}
start();
