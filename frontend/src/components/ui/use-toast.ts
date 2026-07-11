import { toast as sonnerToast } from "sonner"

type ToastVariant = "default" | "destructive" | "success" | "info" | "warning"

interface ToastConfig {
  title?: string
  description?: string
  variant?: ToastVariant
  [key: string]: any
}

function baseToast(input: string | ToastConfig, options?: any) {
  // Plain string call: toast("Saved!")
  if (typeof input === "string") {
    return sonnerToast(input, options)
  }

  // Object call (shadcn-style): toast({ title, description, variant })
  const { title, description, variant, ...rest } = input
  const message = title || description || ""
  const opts = { description: title ? description : undefined, ...rest }

  switch (variant) {
    case "destructive":
      return sonnerToast.error(message, opts)
    case "info":
      return sonnerToast.info(message, opts)
    case "warning":
      return sonnerToast.warning(message, opts)
    default:
      return sonnerToast.success(message, opts)
  }
}

// Merge the callable function with the method shortcuts
export const toast = Object.assign(baseToast, {
  success: (message: string, options?: any) =>
    sonnerToast.success(message, options),
  error: (message: string, options?: any) =>
    sonnerToast.error(message, options),
  info: (message: string, options?: any) => sonnerToast.info(message, options),
  warning: (message: string, options?: any) =>
    sonnerToast.warning(message, options),
  default: (message: string) => sonnerToast(message),
})

export function showToast(
  message: string,
  type: "success" | "error" | "info" | "warning" = "info",
) {
  return toast[type](message)
}

export function useToast() {
  return {
    toast,
    dismiss: (id?: string) => {
      if (id) sonnerToast.dismiss(id)
    },
    toasts: [],
  }
}
