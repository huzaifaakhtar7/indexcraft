"use client";

import ConnectForm from "@/components/ConnectForm";
import { Loading, PageHeader } from "@/components/ui";
import { useStore } from "@/lib/store";

export default function ConnectPage() {
  const { ready } = useStore();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Connect to a database"
        description="Choose MySQL, PostgreSQL or SQLite. IndexCraft analyzes queries on it and tests every fix on a separate copy."
      />
      {ready ? <ConnectForm /> : <Loading />}
    </div>
  );
}
