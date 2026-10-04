import {useState} from 'react';import {useSearchParams} from 'react-router-dom';import {useData} from '../../context/DataContext.jsx';import {useAuth} from '../../context/AuthContext.jsx';
import {Card,FlowStrip,RecCard,LineChart,BarList,DateFilter,Loading,EmptyState,demoTag} from '../../components/Ui.jsx';import {useSeries,validRange} from '../../hooks/useSeries.js';import {worstLevel} from '../../engine/recommendationEngine.js';import {LIVE_ANALYTICS} from '../../services/analyticsService.js';
const f=n=>Math.round(n).toLocaleString('en-IN'),avg=(a,k)=>a.reduce((s,x)=>s+x[k],0)/a.length;
export default function Analytics(){const {machines,recs,tariff}=useData(),{user}=useAuth(),visibleMachines=user?.role==='operator'?machines.filter(m=>(user.machines||[]).includes(m.id)):machines,[sp,setSp]=useSearchParams(),[range,setRange]=useState({rg:'7D',from:'',to:''}),d=useSeries(visibleMachines,range),dd=sp.get('machine');
const filt=<DateFilter value={range} onChange={setRange}/>;if(!visibleMachines.length)return <EmptyState>No machines are assigned to your account yet. Ask your admin to assign one in People.</EmptyState>;if(!validRange(range))return filt;if(!d)return <>{filt}<Loading/></>;
const C=(q,b)=><Card title={q} badge={LIVE_ANALYTICS?'Live MongoDB':demoTag}>{b}</Card>;
if(dd){const p=d.per.find(x=>x.m.id===dd);if(p){const m=p.m,L=p.s.map(x=>x.l);return(<>{filt}<button onClick={()=>setSp({})}>← All machines</button>
<Card title={'⚙️ '+m.n}><FlowStrip m={m}/></Card><div className="grid" style={{margin:'14px 0'}}>{C(`How has ${m.n} used energy?`,<LineChart values={p.s.map(x=>x.e)} labels={L} unit=" kWh"/>)}{C(`Is ${m.n} getting more or less efficient?`,<LineChart values={p.s.map(x=>x.eff)} labels={L} unit="%"/>)}</div>
<div className="grid">{(recs[m.id]||[]).map(r=><RecCard key={r.rid} m={m} r={r} detail/>)}</div></>)}}
const L=d.tot.map(x=>x.l),cmp=d.per.map(p=>{const e=p.s.reduce((a,b)=>a+b.e,0);return{id:p.m.id,l:p.m.n,v:e,t:f(e)+' kWh'}}).sort((a,b)=>b.v-a.v),
ki=d.per.map(p=>{const k=avg(p.s,'kwu');return{id:p.m.id,l:p.m.n,v:k,t:k.toFixed(2)+' kWh/u'}}).sort((a,b)=>b.v-a.v),
cat=['Production','Utility'].map(c=>{const e=d.per.filter(p=>p.m.cat===c).reduce((a,p)=>a+p.s.reduce((x,y)=>x+y.e,0),0);return{l:c,v:e,t:f(e)+' kWh'}});
return(<>{filt}<div className="grid">
{C('Is factory energy rising or falling?',<LineChart values={d.tot.map(x=>x.e)} labels={L} unit=" kWh"/>)}
{C('Which machines use the most energy? (click one)',<BarList items={cmp} onPick={id=>setSp({machine:id})}/>)}
{C('Where does energy go by machine category?',<BarList items={cat}/>)}
{C('Which machine wastes the most energy per unit made? (click one)',<BarList items={ki} onPick={id=>setSp({machine:id})}/>)}
{C('How is the energy cost changing?',<LineChart values={d.tot.map(x=>x.e*tariff)} labels={L} unit=" ₹"/>)}
{C('Is overall efficiency improving?',<LineChart values={d.tot.map(x=>x.eff)} labels={L} unit="%"/>)}</div></>)}
