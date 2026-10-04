import {MOCK,api} from './api.js';import {getRecommendations,readingsOf} from '../engine/recommendationEngine.js';
const cache=new Map();
// MOCK: run the rule engine in the browser. REAL: backend runs the same rules and can merge ML-service findings.
export const recommendationService={
async get(m,tariff=8.5){if(MOCK)return getRecommendations(m,readingsOf(m));
const c=cache.get(m.id);if(c&&c.tariff===tariff&&Date.now()-c.t<10000)return c.v;const v=await api.get('/recommendations/'+encodeURIComponent(m.id)+'?tariff='+encodeURIComponent(tariff));cache.set(m.id,{t:Date.now(),tariff,v});return v},
clearCache:id=>cache.delete(id),feedback:(rid,value)=>MOCK?Promise.resolve():api.post('/recommendations/'+rid+'/feedback',{value})};
