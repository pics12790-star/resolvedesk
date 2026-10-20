import type {Activity} from './types';
export const isWalkthrough=import.meta.env.VITE_APP_MODE==='walkthrough';
export const repositoryUrl='https://github.com/spiderkd/resolvedesk';
export async function api<T>(path:string, options:RequestInit={}):Promise<T>{
  if(isWalkthrough){const {demoApi}=await import('./walkthrough/api');return demoApi<T>(path,options);}
  const response=await fetch(`/api${path}`,{...options,headers:{'Content-Type':'application/json',...options.headers}});
  if(!response.ok){const data=await response.json().catch(()=>({detail:'Request failed'}));throw new Error(typeof data.detail==='string'?data.detail:'Please check the form and try again.');}
  return response.json();
}
export const post=<T>(path:string, body:unknown={})=>api<T>(path,{method:'POST',body:JSON.stringify(body)});
export function subscribeRun(id:string,onEvent:(event:Activity)=>void,onStatus:(status:string)=>void,onError:()=>void){
  if(isWalkthrough){
    let cancelled=false,cleanup:(()=>void)|undefined;
    import('./walkthrough/api').then(({subscribeDemoRun})=>{if(!cancelled)cleanup=subscribeDemoRun(id,onEvent,onStatus,onError)}).catch(()=>{if(!cancelled)onError()});
    return ()=>{cancelled=true;cleanup?.()};
  }
  const stream=new EventSource(`/api/runs/${id}/events`);
  stream.onmessage=e=>onEvent(JSON.parse(e.data));
  stream.addEventListener('status',e=>{const status=JSON.parse((e as MessageEvent).data).status;if(!['queued','running','resume_queued'].includes(status))stream.close();onStatus(status)});
  stream.onerror=()=>{stream.close();onError()};
  return ()=>stream.close();
}
export const statusLabel=(value:string)=>({new:'New',queued:'Queued',running:'Investigating',investigating:'Investigating',awaiting_approval:'Needs review',resume_queued:'Processing',resolved:'Resolved',escalated:'Escalated',needs_information:'Needs information',rejected:'Rejected',failed:'Failed'}[value]||value);
export const money=(cents:number)=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(cents/100);
