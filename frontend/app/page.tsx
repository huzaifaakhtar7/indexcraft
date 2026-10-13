"use client";

import { useEffect, useState } from "react";
import ConnectForm from "@/components/ConnectForm";
import { getHealth } from "@/lib/api";

export default function ConnectPage() {
  const [backend, setBackend] = useState("Checking backend...");

  useEffect(() => {
    getHealth()
      .then((d) => setBackend(d.message))
      .catch(() => setBackend("Backend not reachable on localhost:8000"));
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Connect to a database</h1>
      <p className="rounded bg-white p-3 text-sm shadow">{backend}</p>
      <ConnectForm />
    </div>
  );
}
