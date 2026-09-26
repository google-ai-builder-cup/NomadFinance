import { useSyncExternalStore } from "react";

export type ToastVariant = "info" | "error";

export interface ToastAction {
  /** i18n key of the button label. */
  labelKey: string;
  onClick: () => void;
}

export interface ToastOptions {
  /** A toast with the same id replaces the earlier one instead of stacking a copy. */
  id?: string;
  /** i18n key, translated when shown so a language switch also changes open toasts. */
  messageKey: string;
  variant?: ToastVariant;
  action?: ToastAction;
  /** Milliseconds before it closes itself; null keeps it until the person closes it. */
  duration?: number | null;
  /** Runs when the person closes it with the close button (not after the action button). */
  onDismiss?: () => void;
}

export interface Toast {
  id: string;
  messageKey: string;
  variant: ToastVariant;
  action?: ToastAction;
  duration: number | null;
  onDismiss?: () => void;
}

// More than three at once is noise on a phone screen; the oldest goes first.
const MAX_VISIBLE = 3;
const DEFAULT_DURATION_MS = 6000;
// Errors stay longer: people may be reading slowly in their second language.
const ERROR_DURATION_MS = 10000;

let toasts: readonly Toast[] = [];
let nextId = 0;
const listeners = new Set<() => void>();

function setToasts(next: readonly Toast[]): void {
  toasts = next;
  listeners.forEach((listener) => listener());
}

/**
 * Show a toast. Works outside React too (query cache, service worker callbacks).
 *
 * Returns:
 *   The toast id, for `dismissToast`.
 */
export function toast(options: ToastOptions): string {
  const id = options.id ?? `toast-${++nextId}`;
  const variant = options.variant ?? "info";
  const defaultDuration = variant === "error" ? ERROR_DURATION_MS : DEFAULT_DURATION_MS;
  const item: Toast = {
    id,
    messageKey: options.messageKey,
    variant,
    action: options.action,
    duration: options.duration === undefined ? defaultDuration : options.duration,
    onDismiss: options.onDismiss,
  };
  setToasts([...toasts.filter((existing) => existing.id !== id), item].slice(-MAX_VISIBLE));
  return id;
}

export function dismissToast(id: string): void {
  setToasts(toasts.filter((existing) => existing.id !== id));
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function snapshot(): readonly Toast[] {
  return toasts;
}

/** The toasts on screen now, oldest first. */
export function useToasts(): readonly Toast[] {
  return useSyncExternalStore(subscribe, snapshot);
}
