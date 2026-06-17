"use client";

import { useParams } from "next/navigation";

import { WebhooksPanel } from "@/components/WebhooksPanel";

export default function WebhooksPage() {
  const params = useParams<{ id: string }>();
  if (!params?.id) return null;
  return (
    <div className="max-w-3xl mx-auto p-6">
      <WebhooksPanel projectId={params.id} />
    </div>
  );
}
