import {Link} from 'react-router-dom';
import {useData} from '../../context/DataContext.jsx';
import {useAuth} from '../../context/AuthContext.jsx';
import {Card,EmptyState,FlowStrip,Pill,RecCard,Loading} from '../../components/Ui.jsx';
import {stoppable} from '../../engine/recommendationEngine.js';
import {MOCK} from '../../services/api.js';

const fmt=(value,digits=1)=>Number(value||0).toLocaleString('en-IN',{minimumFractionDigits:digits,maximumFractionDigits:digits});

export default function Optimization(){
  const {machines,recs,machinesLoading}=useData(),{user}=useAuth();
  const visibleMachines=user?.role==='operator'?machines.filter(machine=>(user.machines||[]).includes(machine.id)):machines;
  const opportunities=visibleMachines.flatMap(machine=>(recs[machine.id]||[]).map(recommendation=>({machine,recommendation})))
    .sort((a,b)=>Number(!!b.recommendation.esc)-Number(!!a.recommendation.esc)||Number(b.recommendation.lvl==='bad')-Number(a.recommendation.lvl==='bad'));
  const demand=visibleMachines.reduce((sum,machine)=>sum+Number(machine.kw||0),0);
  const critical=opportunities.filter(item=>item.recommendation.esc||item.recommendation.lvl==='bad').length;
  const normal=visibleMachines.length-opportunities.reduce((ids,item)=>ids.add(item.machine.id),new Set()).size;
  if(machinesLoading)return <Loading/>;
  if(!visibleMachines.length)return <EmptyState>No machines are assigned to your account yet. Ask your admin to assign one in People.</EmptyState>;
  return <div className="optimization-page">
    <section className="optimization-welcome">
      <div><div className="report-eyebrow">VOLTEDGE · DECISION SUPPORT</div><h2>Optimization</h2>
        <p>Prioritized energy and operating suggestions based on the latest readings for your machines.</p></div>
      <div className="row"><Link className="optimization-link" to={`/${user?.role==='operator'?'operator':'admin'}/analytics`}>Open analytics ↗</Link><Link className="optimization-link" to={`/${user?.role==='operator'?'operator':'admin'}/reports`}>Create report ↗</Link></div>
    </section>
    <div className="optimization-kpis">
      <div className="optimization-kpi"><span>🏭</span><b>{visibleMachines.length}</b><small>Machines in view</small></div>
      <div className="optimization-kpi"><span>⚡</span><b>{fmt(demand)} kW</b><small>Current measured load</small></div>
      <div className="optimization-kpi"><span>🧭</span><b>{opportunities.length}</b><small>Open suggestions</small></div>
      <div className="optimization-kpi"><span>{critical?'🚨':'✅'}</span><b>{critical||normal}</b><small>{critical?'Urgent reviews':'Machines in normal range'}</small></div>
    </div>
    <Card title="How to use this view" badge={MOCK?'Demo readings':'Live readings'}>
      <p className="mut optimization-note">Suggestions are rule-based and use current power, power factor, temperature, and configured machine baselines. They are decision support only: verify process and safety requirements before changing operation. A simulated IoT meter is marked as demo data.</p>
      {visibleMachines.length>0&&<div className="optimization-load-list">{[...visibleMachines].sort((a,b)=>b.kw-a.kw).map(machine=>{
        const pct=machine.rt>0?Math.min(100,Math.max(0,machine.kw/machine.rt*100)):0;
        return <div key={machine.id} className="optimization-load"><div><b>{machine.n}</b><span>{fmt(machine.kw)} kW{machine.rt>0?` of ${fmt(machine.rt,0)} kW rated`:''}</span></div><div className="optimization-meter" role="img" aria-label={`${Math.round(pct)} percent of rated power`}><i style={{width:`${pct}%`}}/></div><small>{machine.rt>0?`${Math.round(pct)}% of rated power`:'Rated power not set'}</small></div>;
      })}</div>}
    </Card>
    <section className="optimization-opportunities">
      <div className="row sb"><div><h3>Recommended opportunities</h3><p className="mut">Sorted with safety-critical items first. Suggestions refresh as machine readings change.</p></div><Pill>{opportunities.length?'Current analysis':'No open issues'}</Pill></div>
      {opportunities.length?opportunities.map(({machine,recommendation})=><article className="optimization-machine" key={machine.id+recommendation.rid}>
        <div className="row sb"><div><h3>{machine.n}</h3><span className="mut">{machine.id} · {machine.ty} · {stoppable(machine)?'Stoppable':'Continuous operation required'}</span></div>
          <Pill k={recommendation.esc||recommendation.lvl==='bad'?'bad':'warn'}>{recommendation.esc?'Urgent review':'Opportunity'}</Pill></div>
        <FlowStrip m={machine}/>
        <RecCard m={machine} r={recommendation} detail/>
      </article>):<div className="card ok optimization-clear"><span>✓</span><div><b>No active optimization issues</b><p>Current readings are within the configured rules. New suggestions will appear when a reading crosses a rule threshold.</p></div></div>}
    </section>
  </div>;
}
