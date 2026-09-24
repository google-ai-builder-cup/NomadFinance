import { Button } from "@/components/ui/button";

// Bootstrap placeholder (NF-P1-007) proving Vite + React + TS + Tailwind + shadcn/ui
// are wired together. Replaced by the real app shell in NF-P1-010.
function App() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background text-foreground">
      <h1 className="text-3xl font-bold tracking-tight">NomadFinance</h1>
      <p className="text-muted-foreground">Frontend bootstrap — NF-P1-007</p>
      <Button>It works</Button>
    </main>
  );
}

export default App;
