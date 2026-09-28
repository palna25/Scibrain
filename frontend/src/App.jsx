import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext";
import { ResearchProvider } from "./context/ResearchContext";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Papers from "./pages/Papers";
import PaperDetails from "./pages/PaperDetails";
import Settings from "./pages/Settings";
import ResearchNotebook from "./pages/ResearchNotebook";
import KnowledgeGraph from "./pages/KnowledgeGraph";
import ResearchGaps from "./pages/ResearchGaps";
import AdminDashboard from "./pages/admin/AdminDashboard";
import AdminLayout from "./components/AdminLayout";
import AppLayout from "./components/AppLayout";


function ProtectedRoute({ children }) {
  const token = localStorage.getItem("scibrain_token");

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return children;
}


function AdminRoute({ children }) {
  const token = localStorage.getItem("scibrain_token");

  const user = JSON.parse(
    localStorage.getItem("scibrain_user") || "null"
  );

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  if (!user || user.role !== "admin") {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}


function App() {
  return (
    <ThemeProvider>
       <ResearchProvider>
    <BrowserRouter>

      <div className="min-h-screen bg-background text-foreground">

        <Routes>

          {/* ================= PUBLIC ================= */}

          <Route
            path="/"
            element={<Landing />}
          />

          <Route
            path="/login"
            element={<Login />}
          />

          <Route
            path="/register"
            element={<Register />}
          />


          {/* ================= RESEARCHER ================= */}

          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <Dashboard />
                </AppLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/papers"
            element={
              <ProtectedRoute>
                <Papers />
              </ProtectedRoute>
            }
          />

          <Route
            path="/papers/:paperId"
            element={
              <ProtectedRoute>
                <PaperDetails />
              </ProtectedRoute>
            }
          />

          <Route
             path="/research-notebook"
            element={<ResearchNotebook />}
          />
          <Route
            path="/knowledge-graph"
            element={
              <ProtectedRoute>
              <KnowledgeGraph />
              </ProtectedRoute>
            }
          />

          <Route
          path="/research-gaps"
          element={
            <ProtectedRoute>
              <ResearchGaps />
            </ProtectedRoute>
          }
        />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <Settings />
                </AppLayout>
              </ProtectedRoute>
            }
          />


          {/* ================= ADMIN ================= */}

          <Route
          path="/admin"
          element={
            <AdminRoute>
              <AdminLayout>
                <AdminDashboard />
              </AdminLayout>
            </AdminRoute>
          }
        />

          {/* ================= FALLBACK ================= */}

          <Route
            path="*"
            element={<Navigate to="/" replace />}
          />

        </Routes>

      </div>

    </BrowserRouter>
    </ResearchProvider>
    </ThemeProvider>
  );
}


export default App;