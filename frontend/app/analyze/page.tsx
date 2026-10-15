"use client";

import QueryBox from "@/components/QueryBox";
import { ButtonLink, EmptyState, Loading, PageHeader } from "@/components/ui";
import { useStore } from "@/lib/store";

export default function QueryPage() {
  const { ready, connection } = useStore();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analyze a query"
        description="IndexCraft reads the database's own plan for this query, explains why it is slow and suggests a fix."
      />
      {!ready ? (
        <Loading />
      ) : connection ? (
        <QueryBox />
      ) : (
        <EmptyState
          title="Not connected"
          text="Connect to MySQL, PostgreSQL or SQLite first. The query runs on that database."
          action={<ButtonLink href="/">Go to Connect</ButtonLink>}
        />
      )}
    </div>
  );
}
