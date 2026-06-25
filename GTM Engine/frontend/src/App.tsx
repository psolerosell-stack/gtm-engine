import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Login } from "@/pages/Login";
import { PipelineReview } from "@/pages/PipelineReview";
import Analytics from "@/pages/Analytics";
import Revenue from "@/pages/Revenue";
import Integrations from "@/pages/Integrations";
import Settings from "@/pages/Settings";
import Partners from "@/pages/Partners";
import PartnerDetail from "@/pages/PartnerDetail";
import Dashboard from "@/pages/Dashboard";
import AICopilot from "@/pages/AICopilot";
import NotificationsPage from "@/pages/Notifications";
import OpportunityDetail from "@/pages/OpportunityDetail";
import { useAuthStore } from "@/stores/auth";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loadUser } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated) loadUser();
  }, [isAuthenticated, loadUser]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="partners" element={<Partners />} />
          <Route path="partners/:id" element={<PartnerDetail />} />
          <Route path="pipeline" element={<PipelineReview />} />
          <Route path="pipeline/:id" element={<OpportunityDetail />} />
          <Route path="ai-copilot" element={<AICopilot />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="revenue" element={<Revenue />} />
          <Route path="integrations" element={<Integrations />} />
          <Route path="settings" element={<Settings />} />
          <Route path="notifications" element={<NotificationsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
