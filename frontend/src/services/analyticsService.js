import {MOCK,api} from './api.js';import {win,mSeries,total} from './mock/demoSeries.js';
export const LIVE_ANALYTICS=import.meta.env.VITE_USE_LIVE_AUTH==='true'&&import.meta.env.VITE_USE_LIVE_MACHINES==='true';
// REAL contract: GET /api/analytics?rg=7D&from=&to=&machines=M1,M2
//   -> {per:[{machineId,points:[{l,e,kwu,eff}]}], total:[{l,e,eff}]}   (e = kWh, kwu = kWh/unit, eff = %)
export const analyticsService={async series(machines,range){
if(!LIVE_ANALYTICS&&MOCK){const w=win(range);return{per:machines.map(m=>({m,s:mSeries(m,w)})),tot:total(w,machines)}}
const q=new URLSearchParams({rg:range.rg,from:range.from||'',to:range.to||'',machines:machines.map(m=>m.id).join(',')});
const r=await api.get('/analytics?'+q.toString());
return{per:r.per.map(p=>({m:machines.find(x=>x.id===p.machineId),s:p.points})),tot:r.total}}};
