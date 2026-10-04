import {useState} from 'react';
import {useApp} from '../../context/AppContext.jsx';
import {useAuth} from '../../context/AuthContext.jsx';
import {useData} from '../../context/DataContext.jsx';
import {Card,EmptyState,Pill} from '../../components/Ui.jsx';
import {requestService} from '../../services/requestService.js';

const STATUS={Pending:'warn',Approved:'ok','Changes Requested':'inf',Rejected:'bad',Completed:'lav'};
export default function OperatorApprovals(){
  const {toast}=useApp(),{user}=useAuth(),{machines,requests,reload}=useData();
  const [form,setForm]=useState({m:'',type:'stop',window:'Next low-demand window',notes:''});
  const [error,setError]=useState(''),[busy,setBusy]=useState(false);
  const mine=requests.filter(request=>request.by===user.id);
  const submit=async event=>{event.preventDefault();if(!form.m){setError('Choose one of your assigned machines.');return}setError('');setBusy(true);try{await requestService.create({m:form.m,by:user.id,type:form.type,reason:form.type==='stop'?'Planned stop: '+form.window:(form.notes.trim()||'Sustainable operation review'),obs:form.notes.trim()?[form.notes.trim()]:[],fb:'',acts:form.type==='stop'?['Review requested stop window','Confirm production impact']:['Review machine energy use','Recommend operating adjustment']});await reload();setForm({...form,notes:''});toast('✔ Request sent to admin')}catch(err){setError(err.message||'Could not submit your request')}finally{setBusy(false)}};
  return <div className="grid">
    <Card wide title="✅ Request admin approval"><p className="mut">Submit a planned stop or ask for a sustainable operating change. The machine will not stop until an admin approves the request.</p>
      {error&&<div className="err" role="alert">{error}</div>}
      <form onSubmit={submit}><div className="grid"><div><label htmlFor="approval-machine">Assigned machine</label><select id="approval-machine" value={form.m} onChange={e=>setForm({...form,m:e.target.value})} required><option value="">Choose a machine</option>{machines.map(machine=><option key={machine.id} value={machine.id}>{machine.n}</option>)}</select></div>
        <div><label htmlFor="approval-type">Request type</label><select id="approval-type" value={form.type} onChange={e=>setForm({...form,type:e.target.value})}><option value="stop">Planned stop</option><option value="eco">Sustainable operating change</option></select></div>
        {form.type==='stop'&&<div><label htmlFor="approval-window">Low-demand window</label><input id="approval-window" value={form.window} onChange={e=>setForm({...form,window:e.target.value})}/></div>}
        <div><label htmlFor="approval-notes">What did you notice? (optional)</label><textarea id="approval-notes" rows="2" maxLength="1000" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})} placeholder="Add a short note for the admin"/></div>
      </div><button className="p" style={{marginTop:12}} disabled={busy||!machines.length}>{busy?'Sending…':'Send approval request'}</button></form>
    </Card>
    <Card wide title="📋 My approval requests">{mine.length?mine.map(request=>{const machine=machines.find(item=>item.id===request.m);return <div key={request.id} className="item inf" style={{marginBottom:8}}><div className="row sb"><b>{request.type==='stop'?'Planned stop':'Sustainable mode'} · {machine?.n||request.m}</b><Pill k={STATUS[request.status]||'lav'}>{request.status}</Pill></div><div>{request.reason}</div>{request.fb&&<div className="mut">{request.fb}</div>}<div className="mut">Observed: {(request.obs||[]).join(', ')||'—'}</div><div className="mut">Updates: {(request.log||[]).join(' → ')}</div></div>}):<EmptyState>You have not sent any approval requests yet.</EmptyState>}</Card>
  </div>;
}
