"use client";

import { useState } from "react";

import { colorFromName, initials } from "@/lib/utils";
import type { PresenceMember } from "@/hooks/useProjectPresence";

interface Props {
  members: PresenceMember[];
  maxVisible?: number;
}

/**
 * Stack of online-user avatars.  Hover the cluster to see all names
 * in a popover.  Self is rendered last with a subtle ring.
 */
export function PresenceAvatars({ members, maxVisible = 5 }: Props) {
  const visible = members.slice(0, maxVisible);
  const overflow = members.length - visible.length;
  const [showAll, setShowAll] = useState(false);

  if (members.length === 0) {
    return (
      <span className="text-xs text-muted italic">Chỉ có mình bạn</span>
    );
  }

  return (
    <div className="relative">
      <div
        className="flex -space-x-2 cursor-pointer"
        onClick={() => setShowAll((s) => !s)}
      >
        {visible.map((m) => {
          const color = colorFromName(m.name);
          return (
            <div
              key={m.userId}
              title={m.name}
              className="w-7 h-7 rounded-full text-white text-[10px] font-semibold flex items-center justify-center ring-2 ring-white dark:ring-slate-900"
              style={{ background: color }}
            >
              {initials(m.name)}
            </div>
          );
        })}
        {overflow > 0 && (
          <div
            className="w-7 h-7 rounded-full bg-gray-200 dark:bg-slate-700 text-gray-600 dark:text-slate-300 text-[10px] font-semibold flex items-center justify-center ring-2 ring-white dark:ring-slate-900"
            title={`+${overflow} nữa`}
          >
            +{overflow}
          </div>
        )}
      </div>
      {showAll && (
        <div className="absolute top-full mt-2 right-0 z-30 bg-white dark:bg-slate-900 border border-subtle rounded-md shadow-lg p-2 min-w-[160px]">
          <div className="text-xs font-semibold text-muted mb-1 px-2">
            Đang online ({members.length})
          </div>
          {members.map((m) => (
            <div
              key={m.userId}
              className="flex items-center gap-2 px-2 py-1 rounded hover:bg-gray-50 dark:hover:bg-slate-800"
            >
              <div
                className="w-5 h-5 rounded-full text-white text-[9px] font-semibold flex items-center justify-center"
                style={{ background: colorFromName(m.name) }}
              >
                {initials(m.name)}
              </div>
              <span className="text-xs dark:text-slate-200">{m.name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
