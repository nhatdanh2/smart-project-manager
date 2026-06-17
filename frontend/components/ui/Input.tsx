"use client";

import { forwardRef } from "react";

import { cn } from "@/lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, invalid, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(
          "w-full rounded-md border bg-white px-3 py-2 text-sm transition-colors",
          "border-gray-300 text-gray-900 placeholder:text-gray-400",
          "focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary",
          "dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          invalid && "border-red-500 focus:border-red-500 focus:ring-red-500",
          className
        )}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, invalid, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(
          "w-full rounded-md border bg-white px-3 py-2 text-sm transition-colors",
          "border-gray-300 text-gray-900 placeholder:text-gray-400",
          "focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary",
          "dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          invalid && "border-red-500 focus:border-red-500 focus:ring-red-500",
          className
        )}
        {...props}
      />
    );
  }
);
Textarea.displayName = "Textarea";

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, invalid, children, ...props }, ref) => {
    return (
      <select
        ref={ref}
        className={cn(
          "w-full rounded-md border bg-white px-3 py-2 text-sm transition-colors",
          "border-gray-300 text-gray-900",
          "focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary",
          "dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          invalid && "border-red-500 focus:border-red-500 focus:ring-red-500",
          className
        )}
        {...props}
      >
        {children}
      </select>
    );
  }
);
Select.displayName = "Select";
