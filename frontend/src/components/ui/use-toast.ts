// src/components/ui/use-toast.ts
import { toast as sonnerToast } from "sonner";

// Export toast as an object with methods
export const toast = {
  success: (message: string, options?: any) =>
    sonnerToast.success(message, options),
  error: (message: string, options?: any) =>
    sonnerToast.error(message, options),
  info: (message: string, options?: any) => sonnerToast.info(message, options),
  warning: (message: string, options?: any) =>
    sonnerToast.warning(message, options),
  // Also support the default call for backward compatibility
  default: (message: string) => sonnerToast(message),
};

// Also export a function version for simple use
export function showToast(
  message: string,
  type: "success" | "error" | "info" | "warning" = "info",
) {
  return toast[type](message);
}

export function useToast() {
  return {
    toast,
    dismiss: (id?: string) => {
      if (id) sonnerToast.dismiss(id);
    },
    toasts: [],
  };
}
