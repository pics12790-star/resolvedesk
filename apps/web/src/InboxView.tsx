import {useEffect,useState} from 'react';
import {Search,ArrowDownWideNarrow} from 'lucide-react';
import {api,statusLabel} from './api';
import type {Ticket,User} from './types';
import {TicketDetail} from './TicketDetail';

export function InboxView({tickets,selected,onSelect,refresh,user}:{tickets:Ticket[];selected:string;onSelect:(id:string)=>void;refresh:()=>void;user:User}){
 const [filter,setFilter]=useState('all'),[search,setSearch]=useState(''),[newest,setNewest]=useState(true),[detail,setDetail]=useState<Ticket|null>(null),[error,setError]=useState('');
 const visible=tickets.filter(t=>(filter==='all'||(filter==='review'?t.status==='awaiting_approval':t.status==='resolved'))&&`${t.subject} ${t.id} ${t.customer_name}`.toLowerCase().includes(search.toLowerCase())).sort((a,b)=>newest?b.created-a.created:a.created-b.created);
 const active=visible.find(t=>t.id===selected)?.id||visible[0]?.id;
 function reload(){if(active)api<Ticket>(`/tickets/${active}`).then(setDetail).catch(e=>setError(e.message));refresh();}
 useEffect(()=>{let cancelled=false;setDetail(null);if(active)api<Ticket>(`/tickets/${active}`).then(t=>{if(!cancelled)setDetail(t)}).catch(e=>{if(!cancelled)setError(e.message)});return()=>{cancelled=true};},[active]);
 const counts=[['Open tickets',tickets.filter(t=>!['resolved','rejected','escalated'].includes(t.status)).length],['Awaiting approval',tickets.filter(t=>t.status==='awaiting_approval').length],['Resolved',tickets.filter(t=>t.status==='resolved').length],['Escalated',tickets.filter(t=>t.status==='escalated').length]];
 return <><section className="stats" aria-label="Ticket overview">{counts.map(([label,count])=><div key={label}><span>{label}</span><strong>{count}</strong></div>)}</section><div className="inbox-toolbar"><div className="tabs">{[['all','All tickets'],['review','Needs review'],['resolved','Resolved']].map(([id,label])=><button key={id} onClick={()=>setFilter(id)} className={filter===id?'active':''}>{label}</button>)}</div><div className="list-controls"><label className="search-box"><Search size={17}/><input aria-label="Search tickets" placeholder="Search tickets…" value={search} onChange={e=>setSearch(e.target.value)}/></label><button className="secondary sort-button" onClick={()=>setNewest(!newest)}><ArrowDownWideNarrow size={16}/>{newest?'Newest first':'Oldest first'}</button></div></div>
 {error&&<div role="alert" className="error-banner">{error}</div>}
 <section className="inbox-layout"><div className="ticket-list" data-tour="ticket-list"><div className="list-count">{visible.length} {visible.length===1?'ticket':'tickets'}</div>{visible.map(t=><button key={t.id} className={`ticket-row ${active===t.id?'active':''}`} onClick={()=>onSelect(t.id)}><div className="ticket-row-title">{t.subject}</div><span className={`badge ${t.status}`}>{statusLabel(t.status)}</span><div className="ticket-row-meta">#{t.id} <span>·</span> {t.customer_name}</div></button>)}{!visible.length&&<div className="empty compact"><Search size={25}/><h3>No tickets found</h3><p>Try another search or filter.</p></div>}</div>
 {detail&&detail.id===active?<TicketDetail key={active} ticket={detail} user={user} reload={reload}/>:<div className="empty"><h3>{active?'Loading ticket…':'Your queue is clear'}</h3><p>{active?'Fetching the latest details.':'Tickets matching this view will appear here.'}</p></div>}</section></>
}
