import {createContext,useCallback,useContext,useEffect,useState} from 'react';
import {D,LANGS} from '../i18n/translations.js';
const Ctx=createContext();export const useApp=()=>useContext(Ctx);
export function AppProvider({children}){
const [lang,setLang]=useState(localStorage.getItem('ve.lang')||'en'),[theme,setTheme]=useState(localStorage.getItem('ve.theme')||'mist'),[msg,setMsg]=useState('');
useEffect(()=>{localStorage.setItem('ve.lang',lang);document.documentElement.lang=lang},[lang]);
useEffect(()=>{localStorage.setItem('ve.theme',theme);document.body.dataset.theme=theme},[theme]);
const t=k=>(D[lang]&&D[lang][k])||D.en[k]||k;
const toast=useCallback(m=>{setMsg(m);setTimeout(()=>setMsg(''),2200)},[]);
return <Ctx.Provider value={{lang,setLang,theme,setTheme,t,toast,languages:Object.keys(D),LANGS}}>{children}{msg&&<div className="toast" role="status">{msg}</div>}</Ctx.Provider>}
