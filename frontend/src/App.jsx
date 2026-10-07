import React, { Suspense, lazy } from 'react';
import PaymentPage from './pages/PaymentPage.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Transactions from './pages/Transactions.jsx';
const AnalystDashboard=lazy(()=>import('./pages/AnalystDashboard.jsx'));
const ResearchComparison=lazy(()=>import('./pages/ResearchComparison.jsx'));
const FailureReplay=lazy(()=>import('./pages/FailureReplay.jsx'));
const AdversarialLab=lazy(()=>import('./pages/AdversarialLab.jsx'));

export default function App(){
  const path=window.location.pathname;
  const route=path.match(/^\/payment\/([^/]+)(?:\/(review|context|intervention|result))?$/);
  if(path==='/analyst')return <Suspense fallback={<main className="route-loading">Loading analyst workspace…</main>}><AnalystDashboard/></Suspense>;
  if(path==='/transactions')return <Transactions/>;
  if(path==='/research/comparison')return <Suspense fallback={<main className="route-loading">Loading research workspace…</main>}><ResearchComparison/></Suspense>;
  if(path==='/research/failures')return <Suspense fallback={<main className="route-loading">Loading research workspace…</main>}><FailureReplay/></Suspense>;
  if(path==='/research/adversarial')return <Suspense fallback={<main className="route-loading">Loading research workspace…</main>}><AdversarialLab/></Suspense>;
  if(path==='/send'||path==='/demo'||route)return <PaymentPage libraryOnly={path==='/demo'} initialAttemptId={route?.[1]}/>;
  return <Dashboard/>;
}
