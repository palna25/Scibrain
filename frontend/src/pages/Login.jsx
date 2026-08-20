import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BrainCircuit, Eye, EyeOff, ArrowRight, Loader2 } from "lucide-react";

function Login() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();

    setError("");
    setLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
        }),
      });

      const data = await response.json();
console.log("LOGIN RESPONSE:", data);
      if (!response.ok) {
        throw new Error(data.detail || "Invalid email or password.");
      }

    localStorage.setItem("scibrain_token", data.access_token);

    localStorage.setItem(
  "scibrain_user",
  JSON.stringify({
    id: data.user.id,
    full_name: data.user.full_name,
    email: data.user.email,
    role: data.user.role,
  })
);

if (data.user.role === "admin") {
  navigate("/admin");
} else {
  navigate("/dashboard");
}

    
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen overflow-hidden bg-background text-foreground">
      {/* Background */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-0 top-0 h-[500px] w-[500px] rounded-full bg-indigo-600/10 blur-[150px]" />
        <div className="absolute bottom-0 right-0 h-[450px] w-[450px] rounded-full bg-violet-600/10 blur-[150px]" />

        <div
          className="absolute inset-0 opacity-[0.025]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)",
            backgroundSize: "50px 50px",
          }}
        />
      </div>

      {/* Left branding panel */}
      <div className="relative hidden w-1/2 flex-col justify-between border-r border-white/[0.06] p-10 lg:flex">
        <Link to="/" className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-indigo-400/20 bg-indigo-500/10">
            <BrainCircuit className="h-5 w-5 text-indigo-400" />
          </div>

          <span className="text-xl font-semibold">
            Sci<span className="text-indigo-400">Brain</span>
          </span>
        </Link>

        <div className="max-w-lg">
          <p className="text-sm font-medium uppercase tracking-widest text-indigo-400">
            Research intelligence
          </p>

          <h1 className="mt-5 text-5xl font-semibold leading-tight text-white">
            Your research.
            <br />
            <span className="text-slate-500">Connected.</span>
          </h1>

          <p className="mt-6 max-w-md text-base leading-7 text-slate-400">
            Explore academic literature through semantic retrieval,
            knowledge graphs and intelligent research gap discovery.
          </p>
        </div>

        <p className="text-sm text-slate-600">
          © {new Date().getFullYear()} SciBrain
        </p>
      </div>

      {/* Login */}
      <div className="relative flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="mb-10 flex justify-center lg:hidden">
            <Link to="/" className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-indigo-400/20 bg-indigo-500/10">
                <BrainCircuit className="h-5 w-5 text-indigo-400" />
              </div>

              <span className="text-xl font-semibold">
                Sci<span className="text-indigo-400">Brain</span>
              </span>
            </Link>
          </div>

          <div className="rounded-2xl border border-white/[0.07] bg-slate-900/50 p-7 shadow-2xl shadow-black/30 backdrop-blur-xl sm:p-8">
            <div>
              <h2 className="text-2xl font-semibold text-white">
                Welcome back
              </h2>

              <p className="mt-2 text-sm text-slate-400">
                Sign in to continue your research journey.
              </p>
            </div>

            {error && (
              <div className="mt-6 rounded-xl border border-red-400/15 bg-red-400/5 px-4 py-3 text-sm text-red-300">
                {error}
              </div>
            )}

            <form onSubmit={handleLogin} className="mt-7 space-y-5">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-300">
                  Email
                </label>

                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className="w-full rounded-xl border border-slate-800 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-300">
                  Password
                </label>

                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    required
                    className="w-full rounded-xl border border-slate-800 bg-slate-950/80 px-4 py-3 pr-11 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10"
                  />

                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 transition hover:text-slate-300"
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="group flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-500 py-3 text-sm font-medium text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Signing in...
                  </>
                ) : (
                  <>
                    Sign in
                    <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
                  </>
                )}
              </button>
            </form>

            <div className="mt-7 border-t border-white/[0.06] pt-6 text-center text-sm text-slate-500">
              Don't have an account?{" "}
              <Link
                to="/register"
                className="font-medium text-indigo-400 transition hover:text-indigo-300"
              >
                Create one
              </Link>
            </div>
          </div>

          <div className="mt-6 text-center">
            <Link
              to="/"
              className="text-sm text-slate-600 transition hover:text-slate-400"
            >
              ← Back to SciBrain
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Login;