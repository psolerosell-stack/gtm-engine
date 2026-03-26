import { NavLink } from "react-router-dom";
import { clsx } from "clsx";
import {
  GitBranch,
  Handshake,
  BookOpen,
  Zap,
  BarChart3,
  ArrowUpCircle,
  Heart,
  Search,
  Megaphone,
  LogOut,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth";

const NAV = [
  { label: "Pipeline Review", to: "/pipeline", icon: BarChart3 },
  { label: "Partner Health", to: "/health", icon: Heart },
  { label: "Partner Sourcing", to: "/sourcing", icon: Search },
  { label: "Outbound", to: "/outbound", icon: Megaphone },
  { label: "Referrals", to: "/referrals", icon: GitBranch },
  { label: "Co-selling", to: "/coselling", icon: Handshake },
  { label: "Onboarding", to: "/onboarding", icon: BookOpen },
  { label: "Enablement", to: "/enablement", icon: Zap },
  { label: "Expansion", to: "/expansion", icon: ArrowUpCircle },
];

export function Sidebar() {
  const { user, logout } = useAuthStore();

  return (
    <aside className="w-56 min-h-screen bg-gray-900 text-gray-100 flex flex-col">
      <div className="px-4 py-5 border-b border-gray-700">
        <span className="text-lg font-bold tracking-tight text-white">GTM Engine</span>
        <div className="text-xs text-gray-400 mt-0.5">{user?.email}</div>
      </div>

      <nav className="flex-1 py-4 space-y-0.5 px-2">
        {NAV.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors",
                isActive
                  ? "bg-blue-600 text-white"
                  : "text-gray-300 hover:bg-gray-800 hover:text-white"
              )
            }
          >
            <Icon size={15} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-4 border-t border-gray-700">
        <button
          onClick={logout}
          className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors"
        >
          <LogOut size={14} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
