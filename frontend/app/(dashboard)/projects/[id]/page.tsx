"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * /projects/[id] has no UI of its own — it forwards to the
 * "overview" tab which carries the actual project content. The
 * parent layout (app/(dashboard)/projects/[id]/layout.tsx)
 * still wraps this page, so the redirect keeps the tabs and
 * header mounted.
 */
export default function ProjectIndexPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();

  useEffect(() => {
    if (params?.id) {
      router.replace(`/projects/${params.id}/overview`);
    }
  }, [params?.id, router]);

  return (
    <div className="flex items-center justify-center py-16 text-sm text-gray-500 dark:text-slate-400">
      Đang chuyển sang trang tổng quan…
    </div>
  );
}
