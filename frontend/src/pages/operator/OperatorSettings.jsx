import {useApp} from '../../context/AppContext.jsx';
import {useAuth} from '../../context/AuthContext.jsx';
import {useData} from '../../context/DataContext.jsx';
import {Card} from '../../components/Ui.jsx';

export default function OperatorSettings(){
  const {user}=useAuth(),{machines}=useData(),{lang,setLang,theme,setTheme,LANGS,languages}=useApp();
  return <div className="grid">
    <Card title="⚙️ My account"><p><b>{user.name}</b> · {user.id}</p><p className="mut">Role: Operator. For a name or machine assignment change, contact your admin.</p><h3>Assigned machines</h3>{machines.length?machines.map(machine=><div key={machine.id} className="item inf">{machine.n} · {machine.id}</div>):<div className="mut">No machines assigned.</div>}</Card>
    <Card title="🎨 Display preferences"><label htmlFor="operator-language">Language</label><select id="operator-language" value={lang} onChange={event=>setLang(event.target.value)}>{languages.map(code=><option key={code} value={code}>{LANGS[code]}</option>)}</select><label htmlFor="operator-theme">Theme</label><select id="operator-theme" value={theme} onChange={event=>setTheme(event.target.value)}><option value="mist">🌤️ Mist</option><option value="sage">🌿 Sage</option><option value="dusk">🌙 Dusk</option></select><p className="mut">Your preferences are saved in this browser.</p></Card>
  </div>;
}
