import {Routes,Route,Navigate} from 'react-router-dom';
import Protected from './components/Protected.jsx';import Shell from './components/Shell.jsx';import {DataProvider} from './context/DataContext.jsx';
import Login from './pages/Login.jsx';import OperatorHome from './pages/operator/OperatorHome.jsx';
import Overview from './pages/admin/Overview.jsx';import Analytics from './pages/admin/Analytics.jsx';import AIInsights from './pages/admin/AIInsights.jsx';
import Alerts from './pages/admin/Alerts.jsx';import Approvals from './pages/admin/Approvals.jsx';import Reports from './pages/admin/Reports.jsx';
import {Maintenance,People,Devices,Settings} from './pages/admin/Manage.jsx';
import Optimization from './pages/admin/Optimization.jsx';
import Tasks from './pages/admin/Tasks.jsx';
import OperatorAlerts from './pages/operator/OperatorAlerts.jsx';import OperatorMaintenance from './pages/operator/OperatorMaintenance.jsx';import OperatorTasks from './pages/operator/OperatorTasks.jsx';
import OperatorApprovals from './pages/operator/OperatorApprovals.jsx';import OperatorPeople from './pages/operator/OperatorPeople.jsx';import OperatorDevices from './pages/operator/OperatorDevices.jsx';import OperatorSettings from './pages/operator/OperatorSettings.jsx';
const A=(el)=><Protected role="admin">{el}</Protected>;
const O=(el)=><Protected role="operator">{el}</Protected>;
export default function App(){return(<Routes>
<Route path="/login" element={<Login/>}/>
<Route element={<Protected><DataProvider><Shell/></DataProvider></Protected>}>
<Route path="/operator" element={<Navigate to="/operator/overview" replace/>}/>
<Route path="/operator/overview" element={O(<OperatorHome/>)}/>
<Route path="/operator/analytics" element={O(<Analytics/>)}/><Route path="/operator/optimization" element={O(<Optimization/>)}/><Route path="/operator/alerts" element={O(<OperatorAlerts/>)}/>
<Route path="/operator/ai" element={O(<AIInsights/>)}/><Route path="/operator/approvals" element={O(<OperatorApprovals/>)}/>
<Route path="/operator/people" element={O(<OperatorPeople/>)}/><Route path="/operator/devices" element={O(<OperatorDevices/>)}/>
<Route path="/operator/maintenance" element={O(<OperatorMaintenance/>)}/><Route path="/operator/tasks" element={O(<OperatorTasks/>)}/>
<Route path="/operator/settings" element={O(<OperatorSettings/>)}/><Route path="/operator/reports" element={O(<Reports/>)}/>
<Route path="/admin" element={<Navigate to="/admin/overview" replace/>}/>
<Route path="/admin/overview" element={A(<Overview/>)}/><Route path="/admin/analytics" element={A(<Analytics/>)}/><Route path="/admin/optimization" element={A(<Optimization/>)}/>
<Route path="/admin/ai" element={A(<AIInsights/>)}/><Route path="/admin/alerts" element={A(<Alerts/>)}/>
<Route path="/admin/maintenance" element={A(<Maintenance/>)}/><Route path="/admin/approvals" element={A(<Approvals/>)}/>
<Route path="/admin/people" element={A(<People/>)}/><Route path="/admin/devices" element={A(<Devices/>)}/>
<Route path="/admin/tasks" element={A(<Tasks/>)}/>
<Route path="/admin/settings" element={A(<Settings/>)}/><Route path="/admin/reports" element={A(<Reports/>)}/>
</Route><Route path="*" element={<Navigate to="/login" replace/>}/></Routes>)}
