import {useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {Card,EmptyState,Pill} from '../../components/Ui.jsx';
import {useAuth} from '../../context/AuthContext.jsx';
import {useData} from '../../context/DataContext.jsx';
import {alertService} from '../../services/alertService.js';

export default function OperatorAlerts(){
  const {user}=useAuth(),{machines,recs,alerts,reloadAlerts}=useData(),navigate=useNavigate();
  const [busy,setBusy]=useState(''),[error,setError]=useState('');
  const detected=machines.flatMap(machine=>(recs[machine.id]||[]).map(item=>({machine,item}))).filter(row=>row.item.rule||row.item.esc);
  const myReports=alerts.filter(alert=>alert.source==='Operator report'&&(alert.reported_by===user.id||alert.assigned_to===user.id));
  const send=async({machine,item})=>{const id=machine.id+':'+item.rid;setBusy(id);setError('');try{await alertService.create({machine_id:machine.id,rule_id:item.rule||item.rid,title:`${machine.n}: ${item.rule||'Anomaly detected'}`,message:item.obs,severity:item.lvl==='bad'||item.esc?'critical':'warning',reading:{power_kw:machine.kw,power_factor:machine.pf,temperature:machine.temp,voltage:machine.voltage,current:machine.current,energy_kwh:machine.energy}});await reloadAlerts()}catch(err){setError(err.message||'Could not send alert')}finally{setBusy('')}};
  return <div className="grid">
    <Card wide title="🚨 Detected anomalies" badge={detected.length+' found'}>
      <p className="mut">Anomalies are calculated from your assigned machine readings. Send any item to admin; repeated reports update the same open alert.</p>
      {error&&<div className="err" role="alert">{error}</div>}
      {detected.length?detected.map(({machine,item})=>{const id=machine.id+':'+item.rid;return <div key={id} className={'item '+item.lvl} style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:12,flexWrap:'wrap'}}><span><b>{machine.n}</b> · {item.obs}</span><button className="p" disabled={busy===id} onClick={()=>send({machine,item})}>{busy===id?'Sending…':'Send alert to admin'}</button></div>}):<EmptyState>No anomalies detected on your assigned machines.</EmptyState>}
    </Card>
    <Card wide title="📨 Alerts shared with you or sent by you">
      {myReports.length?myReports.map(alert=><div key={alert.id} className={'item '+alert.s} style={{display:'flex',justifyContent:'space-between',gap:12,flexWrap:'wrap'}}><span><b>{alert.machine_name||alert.m}</b> · {alert.txt}{alert.reported_by_name&&alert.reported_by!==user.id?' · Reported by '+alert.reported_by_name:''}</span><span><Pill k={alert.status==='Resolved'?'ok':alert.s==='bad'?'bad':'warn'}>{alert.status}</Pill>{alert.assigned_to_name?' · Assigned to '+alert.assigned_to_name:''}</span></div>):<EmptyState>No shared anomaly alerts yet. When a machine anomaly appears above, send it to your admin.</EmptyState>}
    </Card>
    <div className="wide"><button className="g" onClick={()=>navigate('/operator/overview')}>Back to machine overview</button></div>
  </div>;
}
