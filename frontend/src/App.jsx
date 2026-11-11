import { useEffect, useState } from "react";

export default function App() {
  const [health, setHealth] = useState("...");

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((d) => setHealth(d.status))
      .catch(() => setHealth("sin conexión"));
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-3xl font-bold">TechSupport S.A.</h1>
      <p className="text-gray-500">Backend: {health}</p>
    </main>
  );
}
