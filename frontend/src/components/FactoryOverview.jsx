import {useEffect,useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {useApp} from '../context/AppContext.jsx';
import {useAuth} from '../context/AuthContext.jsx';
import {useData} from '../context/DataContext.jsx';
import {Card,Pill,Loading,ErrorState} from './Ui.jsx';
import {worstLevel} from '../engine/recommendationEngine.js';
import {dashboardService} from '../services/dashboardService.js';

const LIVE=import.meta.env.VITE_USE_LIVE_AUTH==='true'&&import.meta.env.VITE_USE_LIVE_MACHINES==='true';
const onlineNow=m=>{const stamp=new Date(m.lastReadingAt).getTime();return Number.isFinite(stamp)&&Date.now()-stamp<60_000};
const fmt=(value,digits=0)=>Number(value||0).toLocaleString('en-IN',{maximumFractionDigits:digits,minimumFractionDigits:digits});

export default function FactoryOverview(){
  const {user}=useAuth(),{machines,recs,alerts,tariff}=useData(),nav=useNavigate();
  const isOperator=user?.role==='operator',base=isOperator?'/operator':'/admin';
  const [summary,setSummary]=useState(null),[apiError,setApiError]=useState('');
  const visibleMachines=isOperator?machines.filter(m=>(user?.machines||[]).includes(m.id)):machines;
  const visibleRecs=Object.fromEntries(visibleMachines.map(m=>[m.id,recs[m.id]||[]]));
  useEffect(()=>{
    if(!LIVE)return;
    let active=true,firstResponse=false;
    const timeout=setTimeout(()=>{if(active&&!firstResponse)setApiError('The factory overview request timed out. Check that the backend and MongoDB connection are available.')},12000);
    const refresh=()=>dashboardService.overview(tariff).then(value=>{firstResponse=true;clearTimeout(timeout);if(active){setSummary(value);setApiError('')}}).catch(error=>{firstResponse=true;clearTimeout(timeout);if(active)setApiError(error.message)});
    refresh();const timer=setInterval(refresh,5000);
    return()=>{active=false;clearTimeout(timeout);clearInterval(timer)};
  },[tariff]);
  if(LIVE&&!summary&&!apiError)return <Loading/>;
  if(LIVE&&!summary&&apiError)return <ErrorState msg={'Could not load factory data: '+apiError}/>;

  const rows=LIVE?summary.machines.map(m=>({id:m.machine_id,n:m.name,ty:m.machine_type,kw:m.power_kw,rt:m.rated_power,temp:m.temperature,
    health:m.health==='critical'?'bad':m.health==='attention'?'warn':'ok',online:m.online,lastReadingAt:m.last_reading_at,con:m.operational_constraint})):
    visibleMachines.map(m=>({id:m.id,n:m.n,ty:m.ty,kw:m.kw,rt:m.rt,temp:m.temp,health:worstLevel(visibleRecs[m.id]||[]),online:onlineNow(m),lastReadingAt:m.lastReadingAt,con:m.con}));
  const metrics=summary?.metrics;
  const totalKw=LIVE?metrics.current_demand_kw:rows.reduce((sum,m)=>sum+m.kw,0);
  const online=LIVE?metrics.online_machines:rows.filter(m=>m.online).length;
  const critical=LIVE?metrics.critical_issues:Object.values(visibleRecs).flat().filter(r=>r.esc).length;
  const opportunities=LIVE?metrics.improvement_ideas:Object.values(visibleRecs).flat().filter(r=>!r.esc).length;
  const visibleAlerts=LIVE?summary.alerts:alerts.filter(a=>!isOperator||visibleMachines.some(m=>m.id===a.m)).slice(0,10).map(a=>({id:a.id,machine_id:a.m,machine_name:rows.find(m=>m.id===a.m)?.n||a.m,txt:a.txt,severity:a.s==='bad'?'critical':'warning'}));
  const maxPower=Math.max(...rows.map(m=>m.rt||m.kw),1);
  const shortcuts=[['Analytics','📊',base+'/analytics'],['Alerts','🔔',base+'/alerts'],['Reports','📄',base+'/reports'],['Maintenance','🔧',base+'/maintenance'],['People','👥',base+'/people']];

  return <div className="admin-dashboard">
    {apiError&&<div className="item warn" role="status">Could not refresh factory data; showing the last successful update. {apiError}</div>}
    <section className="admin-welcome card">
      <div><div className="eyebrow">VOLTEDGE · FACTORY</div><h1>Hello, {user?.name||'Team member'}</h1>
        <p className="mut">Shared factory overview of machine activity, energy demand, health and alerts.</p></div>
      <div className="row"><Pill k={LIVE?'ok':'lav'}>{LIVE?'● MongoDB live':'Demo telemetry'}</Pill>{summary?.generated_at&&<span className="mut">Updated {new Date(summary.generated_at).toLocaleTimeString()}</span>}</div>
    </section>

    <section className="admin-kpis" aria-label="Factory summary">
      <div className="card inf"><div className="kpi-label">⚡ Current demand</div><div className="big">{fmt(totalKw,1)} <small>kW</small></div><div className="mut">Estimated cost ₹{fmt(LIVE?metrics.estimated_cost_per_hour:totalKw*tariff,0)} / hour</div></div>
      <div className="card ok"><div className="kpi-label">📡 Machines online</div><div className="big">{online}<small> / {rows.length}</small></div><div className="mut">Last reading within 1 minute</div></div>
      <div className={'card '+(critical?'bad':'lav')}><div className="kpi-label">🚨 Critical issues</div><div className="big">{critical}</div><div className="mut">{LIVE?metrics.open_alerts:alerts.length} open alerts total</div></div>
      <div className="card"><div className="kpi-label">🤖 Improvement ideas</div><div className="big">{opportunities}</div><div className="mut">Based on current telemetry</div></div>
    </section>

    <div className="admin-content-grid">
      <Card title="🏭 Machine activity" badge={LIVE?'Live · refreshes every 5 sec':'Demo data'}>
        <div className="table-scroll"><table><thead><tr><th>Machine</th><th>Connection</th><th>Demand</th><th>Temperature</th><th>Health</th></tr></thead>
          <tbody>{rows.map(m=>{
            const ratio=Math.min(100,Math.round((m.kw/(m.rt||maxPower))*100));
            return <tr key={m.id}>
              <td><button className="text-button" onClick={()=>nav(base+'/analytics?machine='+m.id)}>{m.n}</button><div className="mut">{m.ty} · {m.id}</div></td>
              <td><Pill k={m.online?'ok':'lav'}>{m.online?'Online':'No recent reading'}</Pill></td>
              <td><b>{fmt(m.kw,1)} kW</b><div className="power-meter"><i style={{width:ratio+'%'}}/></div></td>
              <td>{fmt(m.temp,1)} °C</td>
              <td><Pill k={m.health}>{({ok:'Normal',warn:'Attention',bad:'Critical'})[m.health]||'Check'}</Pill></td>
            </tr>;
          })}{!rows.length&&!isOperator&&<tr><td colSpan="5" className="mut">No machines registered yet.</td></tr>}</tbody>
        </table></div>
      </Card>

      <Card title="🔔 Needs attention" badge={visibleAlerts.length?`${visibleAlerts.length} open`:'All clear'}>
        {visibleAlerts.length?<div className="admin-alert-list">{visibleAlerts.slice(0,4).map((item,i)=><button className="admin-alert" key={item.id||i} onClick={()=>nav(base+'/alerts')}>
          <span className="alert-dot"/><span><b>{item.machine_name||item.machine_id||'Factory alert'}</b><span className="mut">{item.txt||'Review machine status'}</span></span><span aria-hidden="true">›</span>
        </button>)}<button className="g" onClick={()=>nav(base+'/alerts')}>Review all alerts</button></div>
        :<div className="empty-admin"><span>✓</span><b>All clear</b><p className="mut">No active alerts right now.</p></div>}
      </Card>
    </div>

    <Card title="Quick access"><div className="admin-shortcuts">{shortcuts.map(([label,icon,path])=><button key={path} onClick={()=>nav(path)}><span>{icon}</span><b>{label}</b><i>Open section →</i></button>)}</div></Card>
  </div>;
}
