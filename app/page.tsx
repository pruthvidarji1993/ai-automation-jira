export default function Home() {
  return (
    <div className="flex flex-1 items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="w-full max-w-2xl px-8 py-24 sm:px-12">
        <h1 className="text-4xl font-semibold tracking-tight text-black dark:text-zinc-50">
          AI Workflow
        </h1>
        <p className="mt-3 text-lg text-zinc-600 dark:text-zinc-400">
          Ticket in, reviewed PR out — an opinionated pipeline for Claude Code and GitHub Copilot Chat.
        </p>
        <p className="mt-8 text-sm leading-6 text-zinc-500 dark:text-zinc-500">
          Seven stages — <span className="font-mono text-zinc-700 dark:text-zinc-300">intake → research → plan → implement → test → review → ship</span> — with two human gates for plan and diff approval. Same procedures available as Claude skills or Copilot prompt files; pick the client that fits your flow.
        </p>
      </main>
    </div>
  );
}
