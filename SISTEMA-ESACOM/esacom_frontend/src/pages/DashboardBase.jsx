import Layout from "../components/Layout";
import { useAuth } from "../context/AuthContext";

export default function DashboardBase() {
  const { user } = useAuth();

  return (
    <Layout titulo="Inicio">
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <p className="text-sm text-gray-500">
          Bienvenido al Sistema ESACOM
        </p>

        <h2 className="mt-2 text-xl font-bold text-gray-900">
          {user?.nombre}
        </h2>

        <div className="mt-4">
          <p className="text-sm text-gray-500">Perfil</p>
          <p className="font-semibold text-gray-800">
            {user?.cargo}
          </p>
        </div>

        <p className="mt-6 text-sm text-gray-500">
          Los módulos de cada perfil se incorporarán en los siguientes bloques.
        </p>
      </div>
    </Layout>
  );
}