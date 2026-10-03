import React from 'react';
import PaymentPage from './pages/PaymentPage.jsx';
import AnalystDashboard from './pages/AnalystDashboard.jsx';

export default function App(){
  const path=window.location.pathname;
  if(path==='/analyst')return <AnalystDashboard/>;
  return <PaymentPage libraryOnly={path==='/demo'}/>;
}
