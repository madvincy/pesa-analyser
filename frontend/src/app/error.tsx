'use client'

import { useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { AlertTriangle, RefreshCw, Home } from 'lucide-react'
import Link from 'next/link'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error('Application error:', error)
  }, [error])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-red-50 via-background to-orange-50 dark:from-red-950/20 dark:via-background dark:to-orange-950/20 p-4">
      <div className="max-w-md w-full text-center space-y-6">
        <div className="flex justify-center">
          <div className="p-4 rounded-full bg-red-100 dark:bg-red-900/30">
            <AlertTriangle className="h-12 w-12 text-red-600 dark:text-red-400" />
          </div>
        </div>
        
        <div>
          <h1 className="text-3xl font-bold font-playfair mb-2">
            Something went wrong
          </h1>
          <p className="text-muted-foreground">
            We apologize for the inconvenience. Please try again or return home.
          </p>
          {error.message && (
            <div className="mt-4 p-3 bg-red-50 dark:bg-red-950/20 rounded-lg text-sm text-red-600 dark:text-red-400 text-left overflow-auto max-h-32">
              <code className="whitespace-pre-wrap">{error.message}</code>
            </div>
          )}
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Button onClick={reset} className="gap-2">
            <RefreshCw className="h-4 w-4" />
            Try Again
          </Button>
          <Link href="/">
            <Button variant="outline" className="gap-2 w-full sm:w-auto">
              <Home className="h-4 w-4" />
              Go Home
            </Button>
          </Link>
        </div>

        <p className="text-xs text-muted-foreground">
          Error ID: {error.digest || 'N/A'}
        </p>
      </div>
    </div>
  )
}
