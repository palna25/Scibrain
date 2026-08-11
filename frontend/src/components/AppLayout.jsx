
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

function AppLayout({ children }) {
  return (
    <div className="min-h-screen bg-background text-foreground">

      {/* Ambient background */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">

        <div className="absolute left-[20%] top-[-20%] h-[500px] w-[500px] rounded-full bg-cyan-500/[0.025] blur-[120px]" />

        <div className="absolute bottom-[-20%] right-[-10%] h-[500px] w-[500px] rounded-full bg-indigo-500/[0.02] blur-[120px]" />

      </div>

      {/* Sidebar */}
      <Sidebar />

      {/* Main application */}
      <div className="relative ml-[250px] min-h-screen">

        {/* Topbar */}
        <Topbar />

        {/* Page content */}
        <main className="p-8">
          {children}
        </main>

      </div>

    </div>
  );
}

export default AppLayout;
