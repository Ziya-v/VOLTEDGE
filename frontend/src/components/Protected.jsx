import {Navigate} from 'react-router-dom';import {useAuth} from '../context/AuthContext.jsx';
export default function Protected({role,children}){const {user}=useAuth();
if(!user)return <Navigate to="/login" replace/>;
if(role&&user.role!==role)return <Navigate to={user.role==='admin'?'/admin/overview':'/operator'} replace/>;return children}
