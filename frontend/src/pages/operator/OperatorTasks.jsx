import {useEffect,useState} from 'react';
import {Card,EmptyState,Pill} from '../../components/Ui.jsx';
import {taskService} from '../../services/taskService.js';

export default function OperatorTasks(){
  const [tasks,setTasks]=useState([]),[error,setError]=useState(''),[busy,setBusy]=useState(''),[filter,setFilter]=useState('All');
  const load=()=>taskService.list().then(items=>{setTasks(items);setError('')}).catch(err=>setError(err.message||'Could not load your tasks'));
  useEffect(()=>{load();const timer=setInterval(load,8000);return()=>clearInterval(timer)},[]);
  const update=async(task,status)=>{setBusy(task.id);setError('');try{await taskService.setStatus(task.id,status);setTasks(current=>current.map(item=>item.id===task.id?{...item,status}:item))}catch(err){setError(err.message||'Could not update task')}finally{setBusy('')}};
  const visible=filter==='All'?tasks:tasks.filter(task=>filter==='Completed'?task.status==='Completed':task.status!=='Completed');
  const counts={All:tasks.length,'To do':tasks.filter(task=>task.status!=='Completed').length,Completed:tasks.filter(task=>task.status==='Completed').length};
  return <Card title="🧰 My tasks" badge="Assigned to you">
    <p className="mut">Tasks assigned by your admin for machines linked to your account.</p>
    {error&&<div className="err" role="alert">{error}</div>}
    {!!tasks.length&&<div className="row" role="group" aria-label="Filter tasks" style={{marginBottom:12}}>{['All','To do','Completed'].map(label=><button type="button" key={label} className={'chip '+(filter===label?'on':'')} aria-pressed={filter===label} onClick={()=>setFilter(label)}>{label} · {counts[label]}</button>)}</div>}
    {visible.length?visible.map(task=><div key={task.id} className="item lav" style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:14,flexWrap:'wrap'}}>
      <div style={{flex:'1 1 300px'}}><b>{task.title}</b><div className="mut">{task.machine_name||task.machine_id}{task.due_date?' · Due '+task.due_date:''}</div>{task.description&&<div style={{marginTop:4}}>{task.description}</div>}</div>
      <div className="row"><Pill k={task.status==='Completed'?'ok':task.status==='In Progress'?'inf':'warn'}>{task.status}</Pill><select aria-label={'Update status for '+task.title} style={{width:'auto'}} disabled={busy===task.id} value={task.status} onChange={e=>update(task,e.target.value)}><option>Pending</option><option>In Progress</option><option>Completed</option></select></div>
    </div>):!error?<EmptyState>{tasks.length?'No tasks in this view. Choose another filter above.':'No tasks are assigned to you yet.'}</EmptyState>:null}
  </Card>;
}
