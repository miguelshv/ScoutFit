// Same weighted, cohort-standardized Euclidean baseline as scoutfit.recommender.
export const presets = {
  balanced: [],
  creation: ['key_passes_p90', 'provider_progressive_carries_p90', 'box_touches_p90'],
  defense: ['recoveries_p90', 'tackles_won_p90', 'interceptions_p90'],
};
export function rank(data, {reference, minimum=450, priority='balanced', sameRole=false, club=''}) {
  const ref=data.players.find(p=>p.profile_id===reference);
  if(!ref || ref.minutes<minimum) throw new Error('La referencia no alcanza el mínimo de minutos.');
  const features=Object.keys(data.features);
  const cohort=data.players.filter(p=>p.role===ref.role && p.minutes>=minimum);
  const scales=features.map(f=>{
    const mean=cohort.reduce((s,p)=>s+p[f],0)/cohort.length;
    const variance=cohort.reduce((s,p)=>s+(p[f]-mean)**2,0)/cohort.length;
    return Math.sqrt(variance)||1;
  });
  const weights=features.map(f=>presets[priority].includes(f)?3:1);
  const sum=weights.reduce((a,b)=>a+b,0);
  const ranked=cohort.filter(p=>p.player_id!==ref.player_id && p.team_id!==ref.team_id
    && (!sameRole || (ref.inferred_role && p.inferred_role===ref.inferred_role))
    && (!club || p.team_name===club)).map(p=>{
      const contributions=features.map((f,i)=>((p[f]-ref[f])/scales[i])**2*weights[i]/sum);
      return {...p,distance:Math.sqrt(contributions.reduce((a,b)=>a+b,0)),contributions};
    }).sort((a,b)=>a.distance-b.distance || (a.player_name<b.player_name?-1:a.player_name>b.player_name?1:0)
      || (a.profile_id<b.profile_id?-1:a.profile_id>b.profile_id?1:0));
  return {ref,cohort,ranked,features,weights};
}
export function percentile(cohort, player, feature) {
  const lower=cohort.filter(p=>p[feature]<player[feature]).length;
  const equal=cohort.filter(p=>p[feature]===player[feature]).length;
  return 100*(lower+(equal+1)/2)/cohort.length;
}
