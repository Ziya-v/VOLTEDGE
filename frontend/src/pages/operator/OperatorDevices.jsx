import {useEffect,useState} from 'react';
import {useAuth} from '../../context/AuthContext.jsx';
import {useData} from '../../context/DataContext.jsx';
import {Card,EmptyState,Pill} from '../../components/Ui.jsx';
import {adminService} from '../../services/adminService.js';

export default function OperatorDevices(){
  const {user}=useAuth(),{machines}=useData(),[devices,setDevices]=useState([]),[error,setError]=useState('');
  useEffect(()=>{let active=true;const load=()=>adminService.devices().then(rows=>active&&setDevices(rows.filter(device=>(user.machines||[]).includes(device.machine_id)))).catch(err=>active&&setError(err.message||'Could not load device status'));load();const timer=setInterval(load,8000);return()=>{active=false;clearInterval(timer)}},[user.id]);
  return <Card title="📡 Devices on my machines" badge="Read only"><p className="mut">Connection status for devices linked to machines assigned to you. Ask your admin to register or configure devices.</p>{error&&<div className="err" role="alert">{error}</div>}{devices.length?<div className="table-scroll"><table><thead><tr><th>Device</th><th>Machine</th><th>Protocol</th><th>Status</th><th>Last seen</th></tr></thead><tbody>{devices.map(device=><tr key={device.device_id}><td><b>{device.name||device.device_id}</b><div className="mut">{device.device_id}</div></td><td>{device.machine_name||machines.find(machine=>machine.id===device.machine_id)?.n||device.machine_id}</td><td>{device.protocol||'—'}</td><td><Pill k={device.status==='Connected'?'ok':device.status==='Disabled'?'lav':'warn'}>{device.status||'Unknown'}</Pill></td><td>{device.last_seen?new Date(device.last_seen).toLocaleString():'No readings yet'}</td></tr>)}</tbody></table></div>:!error?<EmptyState>No devices are linked to your assigned machines.</EmptyState>:null}</Card>;
}
