import {useState} from 'react';
import {isWalkthrough} from './api';
import {EventData,Joyride,STATUS,Step} from 'react-joyride';
import {Map} from 'lucide-react';

const steps:Step[]=[
 {target:'[data-tour="identity-switcher"]',skipBeacon:true,title:'Choose a demo role',content:'Switch between customer and reviewer identities. For the full approval flow, use Jordan Smith as the reviewer.'},
 {target:'[data-tour="new-ticket"]',skipBeacon:true,title:'Create a customer issue',content:isWalkthrough?'Choose a saved enquiry workflow, edit its details, and create a sample order if needed.':'Open a ticket from here. If you need an order number, the form can create one by buying a seeded demo product first.'},
 {target:'[data-tour="ticket-list"]',skipBeacon:true,title:'Select a ticket',content:'The inbox is the working queue. Pick an existing ticket or the one you just created to inspect the support case.'},
 {target:'[data-tour="run-agent"]',skipBeacon:true,title:'Start the investigation',content:isWalkthrough?'Replay a captured Luna investigation: classification, cited policies, order checks, and a resolution ready for review. No live API calls are made.':'This kicks off the LangGraph agent: classify intent, retrieve policies, call commerce tools, and draft a policy-backed resolution.'},
 {target:'[data-tour="evidence-panel"]',skipBeacon:true,title:'Inspect evidence',content:'Order data, retrieved policy chunks, citations, and store facts appear here so the answer is explainable.'},
 {target:'[data-tour="audit-timeline"]',skipBeacon:true,title:'Follow the audit trail',content:'Every major step is logged: classification, retrieval, tool calls, validation, approval, and final receipt.'},
 {target:'[data-tour="approval-panel"]',skipBeacon:true,title:'Review the proposal',content:'Replacement and refund actions pause for reviewer approval before the simulated store changes.'},
 {target:'[data-tour="evaluations-nav"]',skipBeacon:true,title:'Show benchmark results',content:'Reviewer users can open Evaluations to show saved benchmark runs, retrieval metrics, mutation safety, and latency.'},
];

export function DemoTour(){
 const [run,setRun]=useState(false);
 function onJoyride(data:EventData){
  if(data.status===STATUS.FINISHED||data.status===STATUS.SKIPPED)setRun(false);
 }
 return <>
  <button type="button" className="secondary tour-button" onClick={()=>setRun(true)}><Map size={16}/>Demo tour</button>
  <Joyride
   run={run}
   steps={steps}
   continuous
   scrollToFirstStep
   onEvent={onJoyride}
   options={{overlayColor:'rgba(10, 23, 42, .62)',primaryColor:'#075cf0',spotlightPadding:10,textColor:'#263b5e',zIndex:10000}}
   styles={{
    spotlight:{stroke:'#075cf0',strokeWidth:3},
    tooltip:{borderRadius:8,fontSize:13},
    tooltipTitle:{fontSize:15},
    buttonPrimary:{borderRadius:6},
    buttonBack:{color:'#526887'},
    buttonSkip:{color:'#526887'},
   }}
   locale={{back:'Back',close:'Close',last:'Finish',next:'Next',skip:'Skip'}}
  />
 </>;
}
