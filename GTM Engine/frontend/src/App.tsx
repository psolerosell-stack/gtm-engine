import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Login } from "@/pages/Login";
import { PipelineReview } from "@/pages/PipelineReview";
import { PartnerHealth } from "@/pages/PartnerHealth";
import { PartnerSourcing } from "@/pages/PartnerSourcing";
import { Outbound } from "@/pages/Outbound";
import { Referrals } from "@/pages/Referrals";
import { CoSelling } from "@/pages/CoSelling";
import { Onboarding } from "@/pages/Onboarding";
import { Enablement } from "@/pages/Enablement";
import { Expansion } from "@/pages/Expansion";
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
          <Route index element={<Navigate to="/pipeline" replace />} />
          <Route path="pipeline" element={<PipelineReview />} />
          <Route path="health" element={<PartnerHealth />} />
          <Route path="sourcing" element={<PartnerSourcing />} />
          <Route path="outbound" element={<Outbound />} />
          <Route path="referrals" element={<Referrals />} />
          <Route path="coselling" element={<CoSelling />} />
          <Route path="onboarding" element={<Onboarding />} />
          <Route path="enablement" element={<Enablement />} />
          <Route path="expansion" element={<Expansion />} />
        </Route>
        <Route path="*" element={<Navigate to="/pipeline" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
