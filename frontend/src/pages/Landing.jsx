import { Link } from "react-router-dom";
import {
  ArrowRight,
  BrainCircuit,
  Network,
  Search,
  Sparkles,
  GitBranch,
  FileText,
  Lightbulb,
} from "lucide-react";

function Landing() {
  return (
    <div className="min-h-screen overflow-hidden bg-background text-foreground">
      {/* =========================================================
          BACKGROUND
      ========================================================= */}

      <div className="pointer-events-none fixed inset-0">
        <div className="absolute left-1/4 top-0 h-[500px] w-[500px] rounded-full bg-indigo-600/10 blur-[140px]" />

        <div className="absolute right-0 top-1/3 h-[450px] w-[450px] rounded-full bg-violet-600/10 blur-[140px]" />

        <div
          className="absolute inset-0 opacity-[0.035]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.4) 1px, transparent 1px)",
            backgroundSize: "50px 50px",
          }}
        />
      </div>

      {/* =========================================================
          NAVBAR
      ========================================================= */}

      <nav className="relative z-10 border-b border-white/[0.06]">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6 lg:px-8">
          <Link to="/" className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-indigo-400/20 bg-indigo-500/10">
              <BrainCircuit className="h-5 w-5 text-indigo-400" />
            </div>

            <span className="text-xl font-semibold tracking-tight">
              Sci<span className="text-indigo-400">Brain</span>
            </span>
          </Link>

          <div className="hidden items-center gap-8 text-sm text-slate-400 md:flex">
            <a
              href="#features"
              className="transition hover:text-white"
            >
              Features
            </a>

            <a
              href="#how-it-works"
              className="transition hover:text-white"
            >
              How it works
            </a>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to="/login"
              className="rounded-lg px-4 py-2 text-sm text-slate-300 transition hover:bg-white/[0.05] hover:text-white"
            >
              Sign in
            </Link>

            <Link
              to="/register"
              className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400"
            >
              Get started
            </Link>
          </div>
        </div>
      </nav>

      {/* =========================================================
          HERO
      ========================================================= */}

      <main className="relative z-10">
        <section className="mx-auto max-w-7xl px-6 pb-28 pt-24 lg:px-8 lg:pt-32">
          <div className="mx-auto max-w-4xl text-center">

            {/* Badge */}

            <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-indigo-400/20 bg-indigo-500/[0.07] px-4 py-2 text-sm text-indigo-300">
              <Sparkles className="h-4 w-4" />
              Intelligent Research Analysis
            </div>

            {/* Heading */}

            <h1 className="text-5xl font-semibold tracking-tight text-white sm:text-6xl lg:text-7xl">
              Understand research.
              <span className="block bg-gradient-to-r from-indigo-400 via-violet-400 to-indigo-300 bg-clip-text text-transparent">
                Discover what comes next.
              </span>
            </h1>

            {/* Description */}

            <p className="mx-auto mt-7 max-w-2xl text-lg leading-8 text-slate-400">
              SciBrain helps researchers analyze academic papers,
              extract important research information, and organize
              literature into structured insights for further research
              exploration.
            </p>

            {/* CTA */}

            <div className="mt-10 flex flex-col justify-center gap-4 sm:flex-row">
              <Link
                to="/register"
                className="group inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-500 px-6 py-3.5 font-medium text-white shadow-xl shadow-indigo-500/20 transition hover:bg-indigo-400"
              >
                Start researching

                <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
              </Link>

              <Link
                to="/login"
                className="inline-flex items-center justify-center rounded-xl border border-slate-800 bg-slate-900/60 px-6 py-3.5 font-medium text-slate-200 transition hover:border-slate-700 hover:bg-slate-800/70"
              >
                Sign in
              </Link>
            </div>
          </div>

          {/* =====================================================
              PRODUCT PREVIEW
          ===================================================== */}

          <div className="relative mx-auto mt-20 max-w-5xl">
            <div className="absolute inset-0 rounded-3xl bg-indigo-500/10 blur-3xl" />

            <div className="relative overflow-hidden rounded-3xl border border-white/[0.08] bg-slate-950/80 p-2 shadow-2xl shadow-black/40 backdrop-blur-xl">
              <div className="rounded-2xl border border-white/[0.06] bg-slate-900/60 p-6">

                <div className="mb-6 flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-widest text-indigo-400">
                      Research Intelligence
                    </p>

                    <h3 className="mt-2 text-lg font-medium text-white">
                      Paper analysis workspace
                    </h3>
                  </div>

                  <div className="flex items-center gap-2 rounded-lg border border-indigo-400/10 bg-indigo-400/5 px-3 py-1.5 text-xs text-indigo-300">
                    <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
                    Analysis ready
                  </div>
                </div>

                {/* Actual capabilities */}

                <div className="grid gap-4 md:grid-cols-3">

                  <div className="rounded-xl border border-white/[0.06] bg-slate-950/70 p-5">
                    <FileText className="mb-4 h-5 w-5 text-indigo-400" />

                    <p className="text-sm text-slate-400">
                      Paper Processing
                    </p>

                    <p className="mt-2 text-lg font-semibold text-white">
                      PDF Analysis
                    </p>

                    <p className="mt-2 text-xs leading-5 text-slate-500">
                      Upload a research paper and extract its text for
                      analysis.
                    </p>
                  </div>

                  <div className="rounded-xl border border-white/[0.06] bg-slate-950/70 p-5">
                    <Search className="mb-4 h-5 w-5 text-violet-400" />

                    <p className="text-sm text-slate-400">
                      Research Information
                    </p>

                    <p className="mt-2 text-lg font-semibold text-white">
                      Structured Insights
                    </p>

                    <p className="mt-2 text-xs leading-5 text-slate-500">
                      Extract summaries, problems, methods, datasets,
                      metrics and findings.
                    </p>
                  </div>

                  <div className="rounded-xl border border-white/[0.06] bg-slate-950/70 p-5">
                    <Lightbulb className="mb-4 h-5 w-5 text-cyan-400" />

                    <p className="text-sm text-slate-400">
                      Research Exploration
                    </p>

                    <p className="mt-2 text-lg font-semibold text-white">
                      Research Foundation
                    </p>

                    <p className="mt-2 text-xs leading-5 text-slate-500">
                      Organize extracted information as a foundation for
                      deeper research discovery.
                    </p>
                  </div>

                </div>
              </div>
            </div>
          </div>
        </section>

        {/* =========================================================
            FEATURES
        ========================================================= */}

        <section
          id="features"
          className="border-y border-white/[0.05] bg-slate-950/40"
        >
          <div className="mx-auto max-w-7xl px-6 py-24 lg:px-8">

            <div className="max-w-2xl">
              <p className="text-sm font-medium uppercase tracking-widest text-indigo-400">
                Built for researchers
              </p>

              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                From papers to structured research insights.
              </h2>

              <p className="mt-4 text-sm leading-6 text-slate-500">
                SciBrain reduces the effort required to manually extract
                important information from academic literature.
              </p>
            </div>

            <div className="mt-12 grid gap-5 md:grid-cols-3">

              {/* Feature 1 */}

              <div className="group rounded-2xl border border-white/[0.07] bg-slate-900/50 p-6 transition hover:border-indigo-400/20 hover:bg-slate-900/80">
                <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-xl border border-indigo-400/15 bg-indigo-500/10">
                  <FileText className="h-5 w-5 text-indigo-400" />
                </div>

                <h3 className="text-lg font-medium text-white">
                  Paper Processing
                </h3>

                <p className="mt-3 text-sm leading-6 text-slate-400">
                  Upload academic PDFs and extract their text so the
                  research content can be processed systematically.
                </p>
              </div>

              {/* Feature 2 */}

              <div className="group rounded-2xl border border-white/[0.07] bg-slate-900/50 p-6 transition hover:border-indigo-400/20 hover:bg-slate-900/80">
                <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-xl border border-indigo-400/15 bg-indigo-500/10">
                  <Search className="h-5 w-5 text-indigo-400" />
                </div>

                <h3 className="text-lg font-medium text-white">
                  Structured Analysis
                </h3>

                <p className="mt-3 text-sm leading-6 text-slate-400">
                  Extract key research elements including the problem,
                  methodology, datasets, metrics, findings, limitations
                  and future work.
                </p>
              </div>

              {/* Feature 3 */}

              <div className="group rounded-2xl border border-white/[0.07] bg-slate-900/50 p-6 transition hover:border-indigo-400/20 hover:bg-slate-900/80">
                <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-xl border border-indigo-400/15 bg-indigo-500/10">
                  <Network className="h-5 w-5 text-indigo-400" />
                </div>

                <h3 className="text-lg font-medium text-white">
                  Research Knowledge
                </h3>

                <p className="mt-3 text-sm leading-6 text-slate-400">
                  Structure extracted research information so that
                  relationships between research concepts can be explored
                  as the knowledge layer develops.
                </p>
              </div>

            </div>
          </div>
        </section>

        {/* =========================================================
            HOW IT WORKS
        ========================================================= */}

        <section
          id="how-it-works"
          className="mx-auto max-w-7xl px-6 py-24 lg:px-8"
        >
          <div className="text-center">

            <p className="text-sm font-medium uppercase tracking-widest text-indigo-400">
              How SciBrain works
            </p>

            <h2 className="mt-3 text-3xl font-semibold text-white">
              Research analysis, step by step.
            </h2>

            <p className="mx-auto mt-4 max-w-2xl text-sm leading-6 text-slate-500">
              The current workflow begins with a research paper and
              transforms its raw content into structured information.
            </p>
          </div>

          <div className="mx-auto mt-14 grid max-w-4xl gap-5 md:grid-cols-4">

            {[
              ["01", "Upload", "Add an academic PDF to SciBrain."],
              [
                "02",
                "Extract",
                "Extract and clean the paper's text.",
              ],
              [
                "03",
                "Analyze",
                "Identify important research information.",
              ],
              [
                "04",
                "Explore",
                "Use the structured information for further research exploration.",
              ],
            ].map(([number, title, text]) => (
              <div
                key={number}
                className="relative text-center"
              >
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-indigo-400/20 bg-indigo-500/10 text-sm font-semibold text-indigo-400">
                  {number}
                </div>

                <h3 className="mt-4 font-medium text-white">
                  {title}
                </h3>

                <p className="mt-2 text-sm leading-6 text-slate-500">
                  {text}
                </p>
              </div>
            ))}

          </div>
        </section>

        {/* =========================================================
            FUTURE DIRECTION
        ========================================================= */}

        <section className="border-t border-white/[0.05] bg-slate-950/40">
          <div className="mx-auto max-w-7xl px-6 py-20 lg:px-8">

            <div className="mx-auto max-w-3xl text-center">

              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl border border-indigo-400/15 bg-indigo-500/10">
                <GitBranch className="h-5 w-5 text-indigo-400" />
              </div>

              <h2 className="mt-5 text-2xl font-semibold text-white">
                Toward connected research intelligence.
              </h2>

              <p className="mt-4 text-sm leading-7 text-slate-500">
                The structured paper information provides the foundation
                for future knowledge-graph exploration, contradiction
                analysis and research-gap discovery.
              </p>

            </div>
          </div>
        </section>
      </main>

      {/* =========================================================
          FOOTER
      ========================================================= */}

      <footer className="border-t border-white/[0.05]">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-8 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between lg:px-8">

          <div className="flex items-center gap-2">
            <BrainCircuit className="h-4 w-4 text-indigo-400" />
            <span>SciBrain</span>
          </div>

          <p>
            Intelligent research analysis platform.
          </p>

        </div>
      </footer>
    </div>
  );
}

export default Landing;