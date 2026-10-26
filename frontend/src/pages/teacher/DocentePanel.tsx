import { useAuth } from "@/context/AuthContext";

export default function DocentePanel() {
  const { usuario } = useAuth();

  return (
    <div className="p-6">
      <div className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-500">Docente</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-900">Panel del docente</h1>
        <p className="mt-2 text-slate-600">
          {usuario ? `Bienvenido(a), ${usuario.nombre_completo}.` : "Bienvenido(a)."}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
          <h2 className="text-lg font-semibold text-slate-800">Disponibilidad</h2>
          <p className="mt-2 text-sm text-slate-600">Consulta el estado del parqueadero y la ocupación por zona.</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
          <h2 className="text-lg font-semibold text-slate-800">Autorizaciones</h2>
          <p className="mt-2 text-sm text-slate-600">Revisa los permisos y accesos autorizados para tu perfil.</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
          <h2 className="text-lg font-semibold text-slate-800">Soporte</h2>
          <p className="mt-2 text-sm text-slate-600">Accede al mapa y a la información general del sistema.</p>
        </div>
      </div>
    </div>
  );
}
