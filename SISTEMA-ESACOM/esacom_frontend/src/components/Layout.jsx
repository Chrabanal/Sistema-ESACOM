import { useAuth } from "../context/AuthContext";
import { NavLink, useNavigate } from "react-router-dom";
import { menuPorUsuario } from "../utils/navigation";

const PERMISO_RUTA = {
  "/dashboard": "dashboard_gerencia",
  "/cierres-kpi": "dashboard_gerencia",
  "/ejecutivos": "dashboard_gerencia",
  "/supervisor": "mi_equipo",
  "/mi-portal": "mi_portal",
  "/accionables": "accionables",
  "/cobranza": "cobranza",
  "/apelaciones": "apelaciones",
  "/historico": "historico",
  "/base-datos": "base_datos",
  "/auditoria-kpi": "auditoria_kpi",
  "/cargar-datos": "cargar_datos",
  "/analisis": "analisis",
  "/soporte": "usuarios",
  "/permisos": "permisos",
  "/estado-sistema": "estado_sistema",
};

function puedeVerItem(user, item) {
  if (!user) return false;
  const permiso = item?.permiso || PERMISO_RUTA[item?.to];
  if (permiso) return !!user?.permisos?.[permiso];
  if (item?.href) return !!user?.permisos?.dashboard_gerencia;
  return true;
}

function Navegacion({ items, user }) {
  const visibles = items.filter((item) => puedeVerItem(user, item));

  return (
    <nav
      aria-label="Navegación principal"
      className="flex min-w-max items-center gap-1.5 lg:min-w-0 lg:flex-wrap"
    >
      {visibles.map((item) =>
        item.href ? (
          <a
            key={`${item.label}-${item.href}`}
            href={item.href}
            target="_blank"
            rel="noreferrer"
            className="whitespace-nowrap rounded-xl px-3 py-2 text-xs font-semibold text-gray-500 transition hover:bg-gray-100 hover:text-esacom-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-esacom-lime"
          >
            {item.label} ↗
          </a>
        ) : item.to ? (
          <NavLink
            key={`${item.label}-${item.to}`}
            to={item.to}
            className={({ isActive }) =>
              `whitespace-nowrap rounded-xl px-3 py-2 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-esacom-lime ${
                isActive
                  ? "bg-esacom-lime-light text-esacom-ink ring-1 ring-esacom-lime/30"
                  : "text-gray-500 hover:bg-gray-100 hover:text-esacom-ink"
              }`
            }
          >
            {item.label}
          </NavLink>
        ) : null
      )}
    </nav>
  );
}

export default function Layout({ titulo, children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const items = menuPorUsuario(user);
  const visibles = items.filter((item) => puedeVerItem(user, item));

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-[#f6f7f8]">
      <header className="sticky top-0 z-30 border-b border-gray-200 bg-white/95 shadow-[0_1px_0_rgba(15,23,42,0.03)] backdrop-blur-xl">
        <div className="mx-auto flex min-h-16 max-w-[1500px] items-center justify-between gap-3 px-3 sm:px-5">
          <button
            type="button"
            onClick={() => navigate("/")}
            className="flex shrink-0 items-center gap-2 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-esacom-lime"
            aria-label="Ir al inicio"
          >
            <img
              src="/esacom-logo.png"
              alt="ESACOM SpA"
              className="h-11 w-11 object-contain sm:h-12 sm:w-12"
            />
            <div className="hidden text-left leading-tight md:block">
              <p className="text-sm font-extrabold tracking-tight text-esacom-ink">ESACOM</p>
              <p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-esacom-lime-dark">CRM</p>
            </div>
          </button>

          <div className="flex min-w-0 items-center gap-2 sm:gap-3">
            <div className="hidden min-w-0 text-right sm:block">
              <p className="max-w-52 truncate text-xs font-semibold text-gray-700 lg:max-w-72">{user?.nombre}</p>
              <p className="text-[10px] uppercase tracking-wide text-gray-400">{user?.cargo}</p>
            </div>
            <div className="hidden h-8 w-px bg-gray-200 sm:block" />
            <button
              onClick={handleLogout}
              className="min-h-10 rounded-xl border border-gray-200 bg-white px-3 text-xs font-semibold text-gray-600 transition hover:border-gray-300 hover:bg-gray-50 hover:text-esacom-ink"
            >
              Salir
            </button>
          </div>
        </div>

        {visibles.length > 0 && (
          <div className="border-t border-gray-100 bg-white">
            <div className="mx-auto max-w-[1500px] overflow-x-auto px-2 py-2 scrollbar-none sm:px-5 lg:overflow-visible">
              <Navegacion items={items} user={user} />
            </div>
          </div>
        )}
      </header>

      <main className="mx-auto max-w-[1500px] px-3 py-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] sm:px-5 sm:py-6 lg:py-7">
        {titulo && (
          <div className="mb-5 flex items-center gap-3">
            <span className="h-7 w-1.5 rounded-full bg-esacom-lime" aria-hidden="true" />
            <h1 className="text-xl font-extrabold tracking-tight text-esacom-ink sm:text-2xl">{titulo}</h1>
          </div>
        )}
        {children}
      </main>
    </div>
  );
}
