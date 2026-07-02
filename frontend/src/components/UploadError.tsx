// frontend/src/components/UploadError.tsx
'use client'

import { AlertTriangle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

interface UploadErrorProps {
  error: string
  onRetry?: () => void
  onCancel?: () => void
}

export function UploadError({ error, onRetry, onCancel }: UploadErrorProps) {
  return (
    <Card className="border-red-200 bg-red-50/50 dark:bg-red-950/10">
      <CardContent className="p-4 flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
        <div className="flex-1">
          <h4 className="font-semibold text-red-600 dark:text-red-400">Upload Failed</h4>
          <p className="text-sm text-red-600/80 dark:text-red-400/80">{error}</p>
          <div className="flex gap-2 mt-2">
            {onRetry && (
              <Button size="sm" variant="outline" onClick={onRetry} className="gap-2">
                <RefreshCw className="h-3 w-3" />
                Retry
              </Button>
            )}
            {onCancel && (
              <Button size="sm" variant="ghost" onClick={onCancel}>
                Cancel
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}