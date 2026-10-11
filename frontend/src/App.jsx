import React, { Suspense, lazy } from 'react';
import PaymentPage from './pages/PaymentPage.jsx';
import PaymentChat from './pages/PaymentChat.jsx';
const AnalystDashboard=lazy(()=>import('./pages/AnalystDashboard.jsx'));
const ResearchComparison=lazy(()=>import('./pages/ResearchComparison.jsx'));
const FailureReplay=lazy(()=>import('./pages/FailureReplay.jsx'));
const AdversarialLab=lazy(()=>import('./pages/AdversarialLab.jsx'));
const RecipientInvestigation=lazy(()=>import('./pages/RecipientInvestigation.jsx'));

export default function App(){
  const path=window.location.pathname;
  const route=path.match(/^\/payment\/([^/]+)(?:\/(review|context|intervention|result))?$/);
  if(path==='/analyst')return <Suspense fallback={<main className="route-loading">Loading analyst workspace…</main>}><AnalystDashboard/></Suspense>;
  if(path==='/investigate')return <Suspense fallback={<main className="route-loading">Loading recipient investigation…</main>}><RecipientInvestigation/></Suspense>;
  if(path==='/transactions')return <PaymentChat/>;
  if(path==='/research/comparison')return <Suspense fallback={<main className="route-loading">Loading research workspace…</main>}><ResearchComparison/></Suspense>;
  if(path==='/research/failures')return <Suspense fallback={<main className="route-loading">Loading research workspace…</main>}><FailureReplay/></Suspense>;
  if(path==='/research/adversarial')return <Suspense fallback={<main className="route-loading">Loading research workspace…</main>}><AdversarialLab/></Suspense>;
  if(path==='/send'||path==='/')return <PaymentChat/>;
  if(path==='/send/form'||path==='/demo'||route)return <PaymentPage libraryOnly={path==='/demo'} initialAttemptId={route?.[1]}/>;
  return <PaymentChat/>;
}
