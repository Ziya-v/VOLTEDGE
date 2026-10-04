// Pure, transparent rules. No network, no state. The backend runs this same file.
export const stoppable=m=>m.con!=='continuous_operation_required';
export const readingsOf=m=>({kw:m.kw,pf:m.pf,temp:m.temp});
export const worstLevel=rs=>rs.some(r=>r.esc)?'bad':rs.length?'warn':'ok';
const RULES=[
{id:'PF',lvl:'warn',on:(m,r)=>r.pf<.92,o:(m,r)=>`Power factor is ${r.pf.toFixed(2)} (target 0.92 or higher)`,why:'Inductive load is not being compensated',act:['Inspect the capacitor bank / PF panel','Review the load pattern'],obj:'Reduce reactive power and avoid utility penalty'},
{id:'TEMP',lvl:'warn',on:(m,r)=>r.temp>m.bT+5&&r.temp<85,o:(m,r)=>`Temperature is ${r.temp.toFixed(0)}°C, ${(r.temp-m.bT).toFixed(0)}°C above its usual ${m.bT}°C`,why:'Blocked filter, weak cooling or poor ventilation',act:['Check cooling fan, filter and ventilation','Reduce load or pressure setpoint if the process allows'],obj:'Bring temperature back to normal while production continues'},
{id:'EPU',lvl:'warn',on:(m,r)=>m.bK>0&&m.u>0&&r.kw/m.u>m.bK*1.08,o:(m,r)=>`Energy per unit is ${((r.kw/m.u/m.bK-1)*100).toFixed(0)}% above its baseline`,why:'Leakage, high setpoint or idle auxiliary load',act:['Check air / fluid leakage','Review pressure or speed setpoint','Shift non-essential auxiliary load','Schedule maintenance'],obj:'Lower kWh per unit of useful work'},
{id:'IDLE',lvl:'warn',on:(m,r)=>m.idle&&!m.off,o:(m,r)=>`Machine is idle but drawing ${r.kw.toFixed(0)} kW`,why:'Spindle, coolant or auxiliaries left on standby',act:['Reduce unnecessary auxiliary consumption','Review the load pattern'],obj:'Cut idle consumption'},
{id:'CRIT',lvl:'bad',on:(m,r)=>r.temp>=85,o:(m,r)=>`Temperature ${r.temp.toFixed(0)}°C is near the protection limit`,why:'Cooling failure or sustained overload',act:['Alert admin and maintenance now','Reduce load or setpoint only if it is safe'],obj:'Protect the machine. A person decides next steps',esc:'Human decision required. Machine protection limit approaching.'}];
function getRecommendations(m,r){const s=stoppable(m);return RULES.filter(x=>x.on(m,r)).map(x=>{const sw=s&&!x.esc;return{rid:x.id+m.id,rule:x.id,lvl:x.lvl,obs:x.o(m,r),why:x.why,acts:sw?['Planned stop in a low-demand window',x.act[0]]:x.act,obj:sw?'Cut idle or standby consumption':x.obj,esc:x.esc||'',stop:s}})}

export {RULES,getRecommendations};

