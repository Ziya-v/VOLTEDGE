import {useEffect,useState} from 'react';import {analyticsService} from '../services/analyticsService.js';
export const validRange=v=>v.rg!=='Custom'||(v.from&&v.to&&v.from<=v.to);
export function useSeries(machines,range){const [d,setD]=useState(null);const key=machines.map(m=>m.id).join()+JSON.stringify(range);
useEffect(()=>{let on=true;if(!machines.length||!validRange(range)){setD(null);return}const load=()=>analyticsService.series(machines,range).then(x=>on&&setD(x)).catch(()=>{});setD(null);load();const timer=setInterval(load,5000);return()=>{on=false;clearInterval(timer)}},[key]);return d}
