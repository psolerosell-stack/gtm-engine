import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { BarChart3 } from "lucide-react";
import { useAuthStore } from "@/stores/auth";

export function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch {
      setError("Email o contraseña incorrectos");
    } finally {
      setLoading(false);
    }
  }

  const INPUT = "w-full bg-navy-800 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-accent-blue focus:border-transparent";

  return (
    <div className="min-h-screen flex items-center justify-center bg-navy-900">
      <div className="w-full max-w-sm px-4">
        {/* Logo */}
        <div className="flex items-center gap-3 justify-center mb-8">
          <div className="w-9 h-9 rounded-xl bg-accent-blue flex items-center justify-center">
            <BarChart3 size={18} className="text-white" />
          </div>
          <span className="text-xl font-bold text-white tracking-tight">Partner OS</span>
        </div>

        <div className="bg-navy-800 border border-white/10 rounded-2xl p-8 shadow-2xl">
          <h1 className="text-lg font-semibold text-white mb-1">Bienvenido</h1>
          <p className="text-sm text-white/40 mb-6">Accede a tu cuenta</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-white/50 mb-1">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={INPUT}
                placeholder="tu@empresa.io"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-white/50 mb-1">Contraseña</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={INPUT}
              />
            </div>

            {error && (
              <p className="text-xs text-accent-red bg-accent-red/10 rounded-lg px-3 py-2">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-accent-blue hover:bg-blue-600 text-white font-medium rounded-lg py-2.5 text-sm transition-colors disabled:opacity-50"
            >
              {loading ? "Iniciando sesión…" : "Iniciar sesión"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
