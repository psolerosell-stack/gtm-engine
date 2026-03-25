import React, { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Login } from "@/pages/Login";
import { PipelineReview } from "@/pages/PipelineReview";
import { PartnerHealth } from "@/pages/PartnerHealth";
import { PartnerSourcing } from "@/pages/PartnerSourcing";
import { Placeholder } from "@/pages/Placeholder";
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
          <Route
            path="outbound"
            element={<Placeholder title="Outbound Partnerships" description="ICP-scored prospects, suggested approach, bulk outreach" />}
          />
          <Route
            path="referrals"
            element={<Placeholder title="Referrals" description="Active referral partners, leads submitted, conversion rate" />}
          />
          <Route
            path="coselling"
            element={<Placeholder title="Co-selling" description="Shared pipeline, deal stages, co-sell velocity, revenue split" />}
          />
          <Route
            path="onboarding"
            element={<Placeholder title="Onboarding" description="Checklist progress per partner, days since start, blockers" />}
          />
          <Route
            path="enablement"
            element={<Placeholder title="Enablement" description="Partners with low conversion, training completion, resources" />}
          />
          <Route
            path="expansion"
            element={<Placeholder title="Account Expansion" description="Existing clients with expansion signals, upsell opportunities" />}
          />
        </Route>
        <Route path="*" element={<Navigate to="/pipeline" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
