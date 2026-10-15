"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "./ui";

interface Props {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  checkboxLabel?: string;
  danger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export default function ConfirmDialog({ open, title, children, confirmLabel, checkboxLabel, danger, loading, onConfirm, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      setChecked(false);
      dialog.showModal();
    }
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={(e) => {
        if (loading) e.preventDefault();
      }}
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-xl border border-slate-200 bg-white p-0 shadow-xl backdrop:bg-slate-900/40"
    >
      <div className="px-6 pt-5">
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        <div className="mt-3 space-y-3 text-sm text-slate-600">{children}</div>
        {checkboxLabel && (
          <label className="mt-4 flex items-start gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-slate-300 accent-indigo-600"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
            />
            {checkboxLabel}
          </label>
        )}
      </div>
      <div className="mt-6 flex justify-end gap-2 border-t border-slate-100 bg-slate-50 px-6 py-3">
        <Button variant="secondary" onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          variant={danger ? "danger" : "primary"}
          onClick={onConfirm}
          loading={loading}
          disabled={Boolean(checkboxLabel) && !checked}
        >
          {confirmLabel}
        </Button>
      </div>
    </dialog>
  );
}
