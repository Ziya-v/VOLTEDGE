import {useState} from 'react';
import {Navigate,useNavigate} from 'react-router-dom';
import TopBar from '../components/TopBar.jsx';
import {useApp} from '../context/AppContext.jsx';
import {useAuth} from '../context/AuthContext.jsx';
import {AUTH_MOCK} from '../services/api.js';

const home=u=>u.role==='admin'?'/admin/overview':'/operator';

export default function Login(){
  const {t}=useApp(),{user,login,register}=useAuth(),nav=useNavigate();
  const [reg,setReg]=useState(false);
  const [f,setF]=useState({id:'',name:'',pw:'',pw2:''}),[err,setErr]=useState(''),[busy,setBusy]=useState(false);
  if(user)return <Navigate to={home(user)} replace/>;
  const set=k=>e=>setF({...f,[k]:e.target.value});
  const submit=async e=>{
    e.preventDefault();setErr('');const id=f.id.trim().toUpperCase();
    if(!id)return setErr(t('e1'));if(!f.pw)return setErr(t('e2'));
    if(reg){if(f.pw.length<8)return setErr(t('e7'));if(f.pw!==f.pw2)return setErr(t('e6'))}
    if(reg&&!f.name.trim())return setErr('Enter the employee name');
    setBusy(true);
    try{const u=reg?await register(id,f.name.trim(),f.pw):await login(id,f.pw);nav(home(u))}
    catch(x){setErr((x.code&&t(x.code))||x.message)}finally{setBusy(false)}
  };
  return <><TopBar/><form className="login card" onSubmit={submit} noValidate>
    <div style={{fontSize:48}}>⚡</div><h2 style={{margin:'4px 0'}}>VoltEdge</h2><div className="mut">{t('tag')}</div>
    {!reg&&<p className="mut">Sign in with your account. VoltEdge opens the dashboard for your assigned role.</p>}
    {reg&&<p className="mut">New accounts are created with the Operator role. Admin accounts are set up by the project owner.</p>}
    {reg&&<><label htmlFor="name">Employee name</label><input id="name" autoComplete="name" value={f.name} onChange={set('name')}/></>}
    <label htmlFor="id">🪪 {t('eid')}</label><input id="id" autoComplete="username" value={f.id} onChange={set('id')} placeholder="EMP1001"/>
    <label htmlFor="pw">🔒 {t('pw')}</label><input id="pw" type="password" autoComplete={reg?'new-password':'current-password'} value={f.pw} onChange={set('pw')}/>
    {reg&&<><label htmlFor="pw2">🔒 {t('pw2')}</label><input id="pw2" type="password" value={f.pw2} onChange={set('pw2')}/></>}
    <div className="err" role="alert">{err}</div><button className="p" style={{width:'100%'}} disabled={busy}>{reg?t('reg'):t('login')}</button>
    <p style={{textAlign:'center'}}><a href="#" onClick={e=>{e.preventDefault();setReg(!reg);setErr('')}}>{reg?t('have'):t('newhere')}</a></p>
    {AUTH_MOCK&&<div className="mut" style={{textAlign:'center'}}>Demo: EMP1001 / operator123 · ADM0001 / admin123</div>}
  </form></>;
}
