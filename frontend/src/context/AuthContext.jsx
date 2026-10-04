import {createContext,useContext,useEffect,useState} from 'react';import {authService} from '../services/authService.js';
const Ctx=createContext();export const useAuth=()=>useContext(Ctx);
export function AuthProvider({children}){const [user,setUser]=useState(()=>authService.current());
useEffect(()=>{if(!user||import.meta.env.VITE_USE_LIVE_AUTH!=='true'||!localStorage.getItem('ve.token'))return;let live=true;const beat=()=>authService.heartbeat().catch(()=>{});beat();const timer=setInterval(()=>{if(live)beat()},20000);return()=>{live=false;clearInterval(timer)}},[user?.id]);
const login=async(id,pw,role)=>{const u=await authService.login(id,pw,role);setUser(u);return u};
const register=async(id,name,pw)=>{const u=await authService.register(id,name,pw);setUser(u);return u};
const logout=async()=>{await authService.logout();setUser(null)};
return <Ctx.Provider value={{user,login,register,logout}}>{children}</Ctx.Provider>}
