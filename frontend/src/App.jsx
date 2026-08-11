/* import Sidebar from "./components/Sidebar";
import Navbar from "./components/Navbar";
import Dashboard from "./pages/Dashboard";
import PaperUpload from "./pages/PaperUpload";


function App(){

 return (

  <div className="flex min-h-screen bg-slate-950">

    <Sidebar/>

    <div className="
        flex-1
        flex
        flex-col
      ">


        <Navbar/>


        <main
          className="
            flex-1
            p-8
            overflow-auto
          "
        >

      
      <Dashboard/>
      <PaperUpload/>
    </main>

  </div>
  </div>

 )

}


export default App; */


import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Settings from "./pages/Settings";

import AppLayout from "./components/AppLayout";


function ProtectedRoute({ children }) {
  const token = localStorage.getItem("scibrain_token");

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return children;
}


function App() {
  return (
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


          {/* ================= PROTECTED ================= */}

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
            path="/settings"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <Settings />
                </AppLayout>
              </ProtectedRoute>
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
  );
}


export default App;
