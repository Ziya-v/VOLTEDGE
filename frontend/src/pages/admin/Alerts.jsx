import {useEffect,useState} from 'react';
import {useApp} from '../../context/AppContext.jsx';
import {useData} from '../../context/DataContext.jsx';
import {adminService} from '../../services/adminService.js';
import {alertService} from '../../services/alertService.js';
import {EmptyState,Pill} from '../../components/Ui.jsx';

export default function Alerts(){
  const {t,toast}=useApp(),{alerts,reloadAlerts}=useData();
  const [ops,setOps]=useState([]),[error,setError]=useState(''),[saving,setSaving]=useState('');
  const activeCount=alerts.filter(alert=>alert.status!=='Resolved').length;
  useEffect(()=>{adminService.users().then(users=>setOps(users.filter(user=>user.role==='operator'))).catch(err=>setError(err.message||'Could not load operators'))},[]);
  const update=async(alert,values)=>{setError('');setSaving(alert.id);try{await alertService.update(alert.id,values);await reloadAlerts();toast('✔ Alert updated')}catch(err){setError(err.message||'Could not update alert')}finally{setSaving('')}};
  return <div className="card"><div className="row sb"><h2 style={{margin:0}}>🔔 Alerts</h2><Pill k={alerts.some(a=>a.s==='bad'&&a.status!=='Resolved')?'bad':'inf'}>{activeCount} active · {alerts.length-activeCount} resolved</Pill></div>
    <p className="mut">Operator reports sync here automatically. Assign a reported alert to an operator or update its status.</p>
    {error&&<div className="err" role="alert">{error}</div>}
    {alerts.length?alerts.map(alert=>{
      const reported=alert.source==='Operator report';
      const eligible=ops.filter(operator=>(operator.machines||[]).includes(alert.m));
      return <div key={alert.id} className={'item '+alert.s} style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:14,flexWrap:'wrap'}}>
        <div style={{minWidth:240,flex:'1 1 320px'}}><div><b>{alert.machine_name||alert.m}</b> · {alert.txt}</div>
          <div className="mut" style={{marginTop:4}}>{alert.source||'Alert'}{alert.reported_by_name?' · Reported by '+alert.reported_by_name:''}{alert.occurrences>1?' · Detected '+alert.occurrences+' times':''}{alert.created_at?' · '+new Date(alert.created_at).toLocaleString():''}</div>
        </div>
        {reported?<>
          <div className="row" style={{gap:8,flexWrap:'wrap'}}>
            <select style={{width:'auto',minWidth:150}} aria-label={'Assign '+alert.machine_name+' alert'} value={alert.assigned_to||''} disabled={saving===alert.id} onChange={e=>update(alert,{assigned_to:e.target.value||null})}>
              <option value="">Unassigned</option>{eligible.map(operator=><option key={operator.id} value={operator.id}>{operator.name}</option>)}
            </select>
            <select style={{width:'auto'}} aria-label={'Status for '+alert.machine_name+' alert'} value={alert.status} disabled={saving===alert.id} onChange={e=>update(alert,{status:e.target.value})}>
              <option>Open</option><option>Acknowledged</option><option>In Progress</option><option>Resolved</option>
            </select>
          </div>
        </>:<Pill k={alert.s==='bad'?'bad':'warn'}>Automatic detection</Pill>}
      </div>
    }):<EmptyState>{t('none')}</EmptyState>}
  </div>;
}
