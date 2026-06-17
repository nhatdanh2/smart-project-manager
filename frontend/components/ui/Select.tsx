"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  // Reserved for future ``variant``/``size`` props.
  variant?: "default";
}

/**
 * Lightweight native ``<select>`` wrapper that picks up the same
 * ``input`` styling the rest of the UI uses.  Implemented as a
 * thin shim so we don't need to ship Radix's ``@radix-ui/react-select``
 * in the frontend bundle.
 */
export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <select
        ref={ref}
        className={cn("input pr-8 appearance-none", className)}
        {...props}
      >
        {children}
      </select>
    );
  }
);
Select.displayName = "Select";
