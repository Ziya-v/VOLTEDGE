import {useEffect,useState} from 'react';
import {useAuth} from '../../context/AuthContext.jsx';
import {useData} from '../../context/DataContext.jsx';
import {Card,EmptyState,Pill} from '../../components/Ui.jsx';
import {api} from '../../services/api.js';
import {adminService} from '../../services/adminService.js';

const LIVE=import.meta.env.VITE_USE_LIVE_AUTH==='true';
export default function OperatorPeople(){
  const {user}=useAuth(),{machines}=useData(),[team,setTeam]=useState([]),[error,setError]=useState('');
  useEffect(()=>{let active=true;const load=()=>{const request=LIVE?api.get('/team'):adminService.users().then(users=>users.filter(person=>person.id!==user.id&&(person.machines||[]).some(id=>(user.machines||[]).includes(id))));request.then(rows=>active&&setTeam(rows)).catch(err=>active&&setError(err.message||'Could not load your team'))};load();const timer=setInterval(load,15000);return()=>{active=false;clearInterval(timer)}},[user.id]);
  return <div className="grid">
    <Card wide title="👤 My account"><div className="tiles"><div className="tile inf"><b>{user.name}</b><div className="mut">Employee name</div></div><div className="tile inf"><b>{user.id}</b><div className="mut">Employee ID</div></div><div className="tile inf"><b>Operator</b><div className="mut">Account role</div></div></div><h3>Machines assigned to me</h3>{machines.length?<div className="row">{machines.map(machine=><Pill key={machine.id}>{machine.n}</Pill>)}</div>:<p className="mut">No machines assigned. Ask your admin to assign one in People.</p>}</Card>
    <Card wide title="👥 Teammates on my machines">{error&&<div className="err" role="alert">{error}</div>}{team.length?team.filter(person=>person.id!==user.id).map(person=><div key={person.id} className="item inf" style={{display:'flex',justifyContent:'space-between',gap:12,flexWrap:'wrap'}}><span><b>{person.name}</b><span className="mut"> · {person.id} · {person.machines.map(id=>machines.find(m=>m.id===id)?.n||id).join(', ')}</span></span><Pill k={person.sessionActive?'ok':'lav'}>{person.sessionActive?'Active':'Inactive'}</Pill></div>):!error?<EmptyState>No teammates are currently assigned to your machines.</EmptyState>:null}</Card>
  </div>;
}
