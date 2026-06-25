import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Building2,
  BarChart3,
  Sparkles,
  Settings,
  LogOut,
  Bell,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth";
import { useNotificationCount } from "@/hooks/useNotifications";

const NAV_MAIN = [
  { label: "Dashboard",   to: "/dashboard",   icon: LayoutDashboard },
  { label: "Partners",    to: "/partners",    icon: Building2 },
  { label: "Pipeline",    to: "/pipeline",    icon: BarChart3 },
  { label: "AI Copilot",  to: "/ai-copilot",  icon: Sparkles },
];

const NAV_BOTTOM = [
  { label: "Settings",    to: "/settings",    icon: Settings },
];

export function Sidebar() {
  const { user, logout } = useAuthStore();
  const { data: notifData } = useNotificationCount();
  const unread = notifData?.unread ?? 0;

  return (
    <aside className="w-56 min-h-screen bg-navy-900 flex flex-col shrink-0 border-r border-white/5">
      {/* Logo */}
      <div className="px-5 py-5 flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-accent-blue flex items-center justify-center shrink-0">
          <BarChart3 size={14} className="text-white" />
        </div>
        <span className="text-[15px] font-bold tracking-tight text-white">Partner OS</span>
      </div>

      {/* Main nav */}
      <nav className="flex-1 px-3 py-2 flex flex-col gap-0.5">
        {NAV_MAIN.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              isActive
                ? "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-white bg-white/10 border-l-2 border-accent-blue relative"
                : "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-muted hover:text-white hover:bg-white/5 transition-colors border-l-2 border-transparent"
            }
          >
            <Icon size={15} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Bottom nav */}
      <div className="px-3 pb-2 flex flex-col gap-0.5 border-t border-white/5 pt-2">
        {NAV_BOTTOM.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              isActive
                ? "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-white bg-white/10 border-l-2 border-accent-blue"
                : "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-muted hover:text-white hover:bg-white/5 transition-colors border-l-2 border-transparent"
            }
          >
            <Icon size={15} />
            {label}
          </NavLink>
        ))}
      </div>

      {/* User footer */}
      <div className="px-4 py-4 border-t border-white/5 flex items-center justify-between">
        <div className="min-w-0">
          <div className="text-xs text-white font-medium truncate">{user?.email}</div>
          <div className="text-[11px] text-muted mt-0.5">
            {user?.role ?? "user"}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {/* Notification bell */}
          <NavLink to="/notifications" className="relative text-muted hover:text-white transition-colors">
            <Bell size={15} />
            {unread > 0 && (
              <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-accent-red rounded-full text-[9px] font-bold text-white flex items-center justify-center leading-none">
                {unread > 9 ? "9+" : unread}
              </span>
            )}
          </NavLink>
          <button
            onClick={logout}
            className="text-muted hover:text-white transition-colors"
            title="Sign out"
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  );
}
