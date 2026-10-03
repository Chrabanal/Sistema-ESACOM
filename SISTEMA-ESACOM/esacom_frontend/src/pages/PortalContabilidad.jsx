import { Link } from "react-router-dom";
import Layout from "../components/Layout";
import { useAuth } from "../context/AuthContext";
import { menuPorUsuario } from "../utils/navigation";
const MODULOS=[
  ["cobranza","Cobranza","Gestiona pagos, vencimientos y verificaciones con trazabilidad de usuario.","/cobranza"],
  ["historico","Histórico","Consulta la evolución de estados y snapshots KPI.","/historico"],
  ["auditoria_kpi","Auditoría KPI","Consulta diferencias de pago/estado y controles KPI.","/auditoria-kpi"],
];
export default function PortalContabilidad(){const {user}=useAuth(); return <Layout titulo="Área de Contabilidad" items={menuPorUsuario(user)}>
  <div className="rounded-2xl border border-gray-200 bg-white p-5 mb-5"><p className="text-sm font-semibold text-gray-900">Gestión financiera y de cobranza</p><p className="text-sm text-gray-500 mt-1">Este perfil no administra usuarios ni modifica la base maestra ESACOM. Solo opera los módulos financieros habilitados.</p></div>
  <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">{MODULOS.filter(([k])=>user?.permisos?.[k]).map(([k,t,d,to])=><Link key={k} to={to} className="rounded-2xl border border-gray-200 bg-white p-5 hover:border-red-200 hover:shadow-sm transition"><p className="font-bold text-gray-900">{t}</p><p className="text-sm text-gray-500 mt-2 leading-relaxed">{d}</p><p className="text-xs font-semibold text-esacom-red mt-4">Abrir módulo →</p></Link>)}</div>
</Layout>}
