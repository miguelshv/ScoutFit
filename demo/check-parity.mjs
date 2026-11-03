import {readFileSync} from 'node:fs';
import {rank,percentile} from './site/engine.mjs';
const root=process.argv[2];
const data=JSON.parse(readFileSync(`${root}/dist/data.json`,'utf8'));
const cases=JSON.parse(readFileSync(`${root}/parity.json`,'utf8'));
for(const c of cases){
 const result=rank(data,c), top=result.ranked.slice(0,5);
 if(JSON.stringify(top.map(p=>p.profile_id))!==JSON.stringify(c.ids))throw new Error(`Orden distinto: ${c.reference}, ${c.minimum}, ${c.priority}`);
 top.forEach((p,i)=>{
  if(Math.abs(p.distance-c.distances[i])>1e-9)throw new Error(`Distancia distinta: ${c.reference}`);
  if(Math.abs(p.contributions.reduce((a,b)=>a+b,0)-p.distance**2)>1e-10)throw new Error('Explicación inconsistente');
 });
 if(top.length){
  const filtered=rank(data,{...c,club:top[0].team_name});
  if(Math.abs(filtered.ranked[0].distance-top[0].distance)>1e-12)throw new Error('El filtro altera la escala');
 }
}
const cohort=[{x:0},{x:0},{x:10},{x:20}];
if(percentile(cohort,cohort[0],'x')!==37.5 || percentile(cohort,cohort[3],'x')!==100)throw new Error('Percentiles con empates incorrectos');
console.log(`Paridad Python/JavaScript: ${cases.length} búsquedas; orden, distancias, filtros y contribuciones correctos.`);
