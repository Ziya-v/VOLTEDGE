import {useEffect,useState} from 'react';
import {Card,EmptyState,Pill} from '../../components/Ui.jsx';
import {adminService} from '../../services/adminService.js';

export default function OperatorMaintenance(){
  const [rows,setRows]=useState([]),[error,setError]=useState('');
  const load=()=>adminService.maintenance().then(setRows).catch(err=>setError(err.message||'Could not load maintenance information'));
  useEffect(()=>{load();const timer=setInterval(load,15000);return()=>clearInterval(timer)},[]);
  return <Card title="🔧 Machine maintenance" badge="Your assigned machines">
    <p className="mut">Maintenance notes and schedules for machines assigned to you. Contact your admin if a schedule needs to be added or changed.</p>
    {error&&<div className="err" role="alert">{error}</div>}
    {rows.length?rows.map((row,index)=>{const status=row.status||row.st||'Not scheduled';const level=/overdue|due|urgent/i.test(status)?'warn':/complete|ok|normal/i.test(status)?'ok':'lav';return <div key={row.machine_id||index} className="item inf" style={{display:'flex',justifyContent:'space-between',gap:12,flexWrap:'wrap'}}>
      <div><b>{row.machine_name||row.m||row.machine_id}</b><div className="mut">{row.notes||row.t||'Maintenance schedule'}</div>{row.next_due&&<div className="mut">Next due: {new Date(row.next_due).toLocaleDateString()}</div>}</div><Pill k={level}>{status}</Pill>
    </div>}):!error?<EmptyState>No maintenance entries are recorded for your machines.</EmptyState>:null}
  </Card>;
}
