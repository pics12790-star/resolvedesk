import {useEffect,useState} from 'react';
import {Inbox,ClipboardList,ShieldCheck,Store,Plus,ArrowUpRight,PanelLeftClose} from 'lucide-react';
import {api,post} from './api';
import type {Ticket,User} from './types';
import {InboxView} from './InboxView';
import {Evaluations,Policies} from './Resources';
import {NewTicket} from './NewTicket';
import {DemoTour} from './DemoTour';

export default function App(){
 const [user,setUser]=useState<User|null>(null),[page,setPage]=useState('Inbox'),[tickets,setTickets]=useState<Ticket[]>([]),[selected,setSelected]=useState('T-1001'),[showNew,setShowNew]=useState(false),[error,setError]=useState(''),[mode,setMode]=useState(''),[navOpen,setNavOpen]=useState(false);
 const providerLabel=mode==='demo'?'Deterministic demo mode':mode==='luna'?'GPT Luna agent':'Gemini agent';
 const refresh=()=>api<Ticket[]>('/tickets').then(setTickets).catch(e=>setError(e.message));
 useEffect(()=>{api<User>('/auth/me').then(setUser).catch(()=>post<User>('/auth/demo',{identity:'reviewer'}).then(setUser).catch(e=>setError(e.message)));api<{agent_mode:string}>('/health').then(x=>setMode(x.agent_mode)).catch(()=>setError('The API is unavailable. Start the local server and refresh.'));},[]);
 useEffect(()=>{if(user)refresh();},[user]);
 async function switchUser(id:string){try{setUser(await post<User>('/auth/demo',{identity:id}));setPage('Inbox');setSelected('');}catch(e){setError((e as Error).message);}}
 return <div className="app-shell">
  <aside className={`sidebar ${navOpen?'open':''}`}><a href="#" className="brand" onClick={()=>setPage('Inbox')}>Resolve<span>Desk</span></a><div className="nav-label">Workspace</div><nav>{[{label:'Inbox',icon:Inbox},{label:'Evaluations',icon:ClipboardList,tour:'evaluations-nav'},{label:'Policies',icon:ShieldCheck}].filter(x=>x.label!=='Evaluations'||user?.role==='reviewer').map(({label,icon:Icon,tour})=><button key={label} data-tour={tour} className={`nav-item ${page===label?'selected':''}`} onClick={()=>{setPage(label);setNavOpen(false);}}><Icon size={20}/>{label}{page===label&&<span className="nav-dot"/>}</button>)}</nav>
   <div className="sidebar-bottom"><div className="store-label"><Store size={19}/><div>Demo store<small>Simulated transactions</small></div><span className="online-dot"/></div><label className="identity-label" htmlFor="identity">Demo identity</label><select id="identity" data-tour="identity-switcher" value={user?.id||'reviewer'} onChange={e=>switchUser(e.target.value)}><option value="reviewer">Jordan Smith · Reviewer</option><option value="maya">Maya Chen · Customer</option><option value="alex">Alex Rivera · Customer</option><option value="priya">Priya Kapoor · Customer</option></select><div className="provider-label">{providerLabel}<ArrowUpRight size={13}/></div></div>
  </aside>
  <main><button className="mobile-nav icon-button" aria-label="Toggle navigation" onClick={()=>setNavOpen(!navOpen)}><PanelLeftClose/></button><header className="page-header"><div><h1>{page==='Inbox'?'Support inbox':page}</h1><p>{page==='Inbox'?'Investigate with evidence. Resolve with confidence.':page==='Evaluations'?'Measure what works. Inspect what needs attention.':'The source of truth behind every resolution.'}</p></div><div className="header-actions"><DemoTour/>{page==='Inbox'&&<button className="primary" data-tour="new-ticket" onClick={()=>setShowNew(true)}><Plus size={18}/>New ticket</button>}</div></header>
   {error&&<div className="error-banner" role="alert">{error}<button onClick={()=>setError('')}>Dismiss</button></div>}
   {user&&(page==='Inbox'?<InboxView tickets={tickets} selected={selected} onSelect={setSelected} refresh={refresh} user={user}/>:page==='Evaluations'?<Evaluations/>:<Policies/>)}
   {!user&&!error&&<div className="empty">Connecting to your workspace…</div>}
   <footer>ResolveDesk <span>·</span> Evidence-backed customer support <span>·</span> Local portfolio demo</footer>
  </main>{showNew&&<NewTicket user={user} onClose={()=>setShowNew(false)} onCreated={t=>{setSelected(t.id);setShowNew(false);refresh();}}/>}
 </div>
}
