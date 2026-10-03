import { Link } from "react-router-dom";
import Layout from "../components/Layout";
import { useAuth } from "../context/AuthContext";
import { menuPorUsuario } from "../utils/navigation";

const MODULOS = [
  ["accionables","Accionables","Prioriza casos próximos a vencer y gestión operativa del día."],
  ["apelaciones","Apelaciones","Detecta, revisa y prepara casos para apelación a Claro."],
  ["historico","Histórico","Consulta evolución de snapshots y comportamiento por camada."],
  ["base_datos","Base de Datos","Revisa estado de las fuentes ESACOM y cargas disponibles."],
  ["auditoria_kpi","Auditoría KPI","Analiza cruces, diferencias y alertas entre ESACOM y Claro."],
  ["cargar_datos","Carga de Datos","Carga controlada de KPI y fuentes autorizadas."],
  ["analisis","Análisis","Indicadores globales de operación para seguimiento interno."],
];
const RUTAS={accionables:"/accionables",apelaciones:"/apelaciones",historico:"/historico",base_datos:"/base-datos",auditoria_kpi:"/auditoria-kpi",cargar_datos:"/cargar-datos",analisis:"/analisis"};
export default function PortalOperaciones(){
  const {user}=useAuth();
  return <Layout titulo="Área de Operaciones" items={menuPorUsuario(user)}>
    <div className="rounded-2xl border border-gray-200 bg-white p-5 mb-5">
      <p className="text-sm font-semibold text-gray-900">Centro operativo ESACOM</p>
      <p className="text-sm text-gray-500 mt-1">Acceso global solo a los módulos habilitados por Gerencia/Soporte. Las ventas y ejecutivos siguen teniendo como fuente maestra a ESACOM.</p>
    </div>
    <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
      {MODULOS.filter(([k])=>user?.permisos?.[k]).map(([k,t,d])=><Link key={k} to={RUTAS[k]} className="rounded-2xl border border-gray-200 bg-white p-5 hover:border-red-200 hover:shadow-sm transition">
        <p className="font-bold text-gray-900">{t}</p><p className="text-sm text-gray-500 mt-2 leading-relaxed">{d}</p><p className="text-xs font-semibold text-esacom-red mt-4">Abrir módulo →</p>
      </Link>)}
    </div>
  </Layout>;
}
