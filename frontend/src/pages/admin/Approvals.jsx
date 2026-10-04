import {useState} from 'react';import {useApp} from '../../context/AppContext.jsx';import {useAuth} from '../../context/AuthContext.jsx';import {useData} from '../../context/DataContext.jsx';
import {Pill,ConfirmModal,EmptyState} from '../../components/Ui.jsx';import {requestService} from '../../services/requestService.js';
const ST={Pending:'warn',Approved:'ok','Changes Requested':'inf',Rejected:'bad',Completed:'lav'};
export default function Approvals(){const {t,toast}=useApp(),{user}=useAuth(),{requests,machines,reload}=useData(),[ask,setAsk]=useState(null);
return(<>{requests.length?requests.map(q=>{const m=machines.find(x=>x.id===q.m),open=['Pending','Changes Requested'].includes(q.status),B=(s,c,l)=><button className={c} onClick={()=>setAsk({id:q.id,s})}>{l||s}</button>;
return <div key={q.id} className="card" style={{marginBottom:12}}><div className="row sb"><b>{q.type==='stop'?'⏸️ Planned stop':'🌱 Sustainable mode'} · {m?m.n:q.m}</b><Pill k={ST[q.status]}>{q.status}</Pill></div>
<div className="mut">Requested by {q.by} · {q.reason}</div><div style={{margin:'6px 0'}}>Observed: {q.obs.join(', ')||'—'}{q.fb&&' — '+q.fb}</div><div className="mut">Suggested actions: {q.acts.join(' · ')}</div><div className="mut">Audit: {q.log.join(' → ')}</div>
<div className="row" style={{marginTop:8}}>{open&&<>{B('Approved','g',t('approve'))}{B('Changes Requested','','Request changes')}{B('Rejected','r',t('reject'))}</>}{q.status==='Approved'&&B('Completed','p','Mark completed')}</div></div>}):<EmptyState>{t('noreq')}</EmptyState>}
<ConfirmModal open={!!ask} message={ask&&`${ask.s}?`} onCancel={()=>setAsk(null)} onConfirm={async()=>{await requestService.setStatus(ask.id,ask.s,user.id);setAsk(null);await reload();toast('✔ '+ask.s)}}/></>)}
