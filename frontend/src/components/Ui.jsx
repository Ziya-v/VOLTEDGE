import {useState} from 'react';import {useApp} from '../context/AppContext.jsx';import {MOCK} from '../services/api.js';
import {stoppable} from '../engine/recommendationEngine.js';import {recommendationService} from '../services/recommendationService.js';import {speak} from '../lib/speech.js';import {iso} from '../services/mock/demoSeries.js';
export const Pill=({k='lav',children})=><span className={'pill '+k}>{children}</span>;
export const Card=({title,badge,wide,className='',children})=><div className={`card ${wide?'wide':''} ${className}`}>{(title||badge)&&<div className="row sb"><h3>{title}</h3>{badge&&<Pill>{badge}</Pill>}</div>}{children}</div>;
export const demoTag=MOCK?'Demo Data':null;
export const Loading=()=><div className="card mut" role="status">Loading…</div>;
export const ErrorState=({msg})=><div className="card bad" role="alert">⚠️ {msg}</div>;
export const EmptyState=({children})=><div className="card ok">{children}</div>;
export function FlowStrip({m}){const s=stoppable(m);return(<div className="flow">
<div className={s?'ok':'warn'}><small>Stoppable?</small><b>{s?'YES':'NO'}</b><small>{s?'Safe to stop':'Continuous operation required'}</small></div><span>→</span>
<div className="inf"><small>Solution</small><b>{s?'Reduce idle / standby use':'Optimise while running'}</b></div><span>→</span>
<div className="lav"><small>Action</small><b>{s?'Planned stop in a low-demand window (needs confirmation and admin approval)':'Check leakage, filter, setpoint · schedule maintenance'}</b></div></div>)}
export function RecCard({m,r,detail}){const {lang}=useApp(),[f,setF]=useState('');
const vote=v=>{const n=f===v?'':v;setF(n);recommendationService.feedback(r.rid,n)};
return(<div className="card" style={{borderLeft:`5px solid var(--${r.esc?'bt':'wt'})`}}>
<div className="row sb"><b>{r.esc?'🚨':'⚠️'} {m.n}</b><Pill>{r.source==='ml-service'?'ML service':'Rule-based'+(MOCK?' (simulated)':'')}</Pill></div>
{r.esc&&<div className="item bad"><b>{r.esc}</b></div>}
<div className="chain"><div><small>Observation</small>{r.obs}</div><i>↓</i><div><small>Possible reason</small>{r.why}</div><i>↓</i>
<div><small>Recommended action</small><ul>{r.acts.map(a=><li key={a}>{a}</li>)}</ul></div><i>↓</i><div><small>Expected objective</small>{r.obj}</div></div>
{detail&&<div className="mut">{r.source==='ml-service'?`Trained asset ${r.asset_id} · 15-minute energy history · anomaly score ${r.anomaly_score??'—'}`:`Rule ${r.rule} · inputs: kW, power factor, temperature · baseline ${m.bT}°C, ${m.bK} kWh/unit`}</div>}
<div className="row" style={{marginTop:8}}><button className={'chip '+(f==='up'?'on':'')} onClick={()=>vote('up')}>👍 Helpful</button><button className={'chip '+(f==='dn'?'on':'')} onClick={()=>vote('dn')}>👎 Not helpful</button>
<button className="chip" aria-label="Read aloud" onClick={()=>speak(r.obs+'. '+r.acts.join('. '),lang)}>🔊</button></div></div>)}
export function ConfirmModal({open,message,onConfirm,onCancel}){const {t}=useApp();if(!open)return null;
return(<div className="modal" role="dialog" aria-modal="true"><div className="card"><h3>⚠️ {t('cf')}</h3><p>{message}</p><div className="row"><button className="g" onClick={onConfirm}>{t('yes')}</button><button autoFocus onClick={onCancel}>{t('no')}</button></div></div></div>)}
export function LineChart({values,labels,unit=''}){const w=520,h=150,mx=Math.max(...values),mn=Math.min(...values),X=i=>20+i/(values.length-1||1)*(w-30),Y=v=>h-24-(v-mn)/(mx-mn||1)*(h-44),f=n=>Math.round(n).toLocaleString('en-IN');
return(<svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="trend chart"><polyline fill="none" stroke="var(--at)" strokeWidth="2.5" strokeLinejoin="round" points={values.map((v,i)=>X(i).toFixed(1)+','+Y(v).toFixed(1)).join(' ')}/>
<g fill="var(--mut)" fontSize="11"><text x="20" y="12">max {f(mx)}{unit}</text><text x={w-10} y="12" textAnchor="end">min {f(mn)}{unit}</text><text x="20" y={h-4}>{labels[0]}</text><text x={w-10} y={h-4} textAnchor="end">{labels[labels.length-1]}</text></g></svg>)}
export function BarList({items,onPick}){const mx=Math.max(...items.map(i=>i.v));
return items.map(i=>{const row=<><span>{i.l}</span><div className="bar"><i style={{width:i.v/mx*100+'%'}}/></div><b>{i.t}</b></>;
return onPick?<button key={i.l} className="hb" onClick={()=>onPick(i.id)}>{row}</button>:<div key={i.l} className="hb">{row}</div>})}
export function Bars({values}){const mx=Math.max(...values,1);return <div style={{display:'flex',alignItems:'flex-end',gap:8,height:130}}>{values.map((v,i)=><div key={i} title={Math.round(v)} style={{flex:1,background:'var(--ab)',borderRadius:'8px 8px 0 0',height:v/mx*100+'%',minHeight:6}}/>)}</div>}
export function DateFilter({value,onChange}){const set=p=>onChange({...value,...p}),today=iso(new Date());
const pick=rg=>{if(rg==='Custom'&&!value.from){const e=new Date(),to=iso(e);e.setDate(e.getDate()-6);return onChange({rg,from:iso(e),to})}set({rg})};
return(<><div className="row" style={{marginBottom:14}} role="group" aria-label="Date range">{['Today','7D','30D','1Y','Custom'].map(r=><button key={r} className={'chip '+(value.rg===r?'on':'')} onClick={()=>pick(r)}>{r}</button>)}
{value.rg==='Custom'&&<><input type="date" aria-label="From" style={{width:'auto'}} value={value.from} max={today} onChange={e=>set({from:e.target.value})}/><input type="date" aria-label="To" style={{width:'auto'}} value={value.to} min={value.from} max={today} onChange={e=>set({to:e.target.value})}/></>}</div>
{value.rg==='Custom'&&value.from>value.to&&<div className="err">Start date must be before end date</div>}</>)}
