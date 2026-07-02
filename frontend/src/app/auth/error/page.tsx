'use client'

import { useSearchParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AlertTriangle, ArrowLeft, RefreshCw } from 'lucide-react'
import Link from 'next/link'

export default function AuthError() {
  const searchParams = useSearchParams()
  const error = searchParams.get('error')

  const errorMessages: Record<string, string> = {
    'OAuthSignin': 'Error starting the OAuth sign-in process.',
    'OAuthCallback': 'Error during OAuth callback.',
    'OAuthCreateAccount': 'Error creating OAuth account.',
    'EmailCreateAccount': 'Error creating email account.',
    'Callback': 'Error during callback.',
    'OAuthAccountNotLinked': 'Email already linked to another account.',
    'EmailSignin': 'Error sending email sign-in link.',
    'CredentialsSignin': 'Invalid email or password.',
    'SessionRequired': 'Please sign in to access this page.',
    'default': 'An authentication error occurred.',
  }

  const getErrorMessage = () => {
    if (error === 'OAuthCallback' || error === 'OAuthSignin') {
      if (error === 'OAuthCallback' && searchParams.get('error_description')?.includes('redirect_uri_mismatch')) {
        return 'The redirect URI doesn\'t match what\'s configured in Google Cloud Console. Please check your OAuth configuration.'
      }
      return 'OAuth authentication failed. Please make sure you have configured the correct redirect URIs in Google Cloud Console.'
    }
    return errorMessages[error || 'default'] || errorMessages.default
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-red-50 via-background to-orange-50 dark:from-red-950/20 dark:via-background dark:to-orange-950/20 p-4">
      <Card className="max-w-md w-full border-0 shadow-2xl">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <div className="p-3 rounded-full bg-red-100 dark:bg-red-900/30">
              <AlertTriangle className="h-12 w-12 text-red-600 dark:text-red-400" />
            </div>
          </div>
          <CardTitle className="text-2xl font-bold">Authentication Error</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="text-center">
            <p className="text-muted-foreground">{getErrorMessage()}</p>
            {error === 'OAuthCallback' && (
              <div className="mt-4 p-4 bg-yellow-50 dark:bg-yellow-950/20 rounded-lg text-left text-sm">
                <p className="font-semibold">🔧 How to fix:</p>
                <ol className="list-decimal list-inside mt-2 space-y-1 text-muted-foreground">
                  <li>Go to <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Google Cloud Console</a></li>
                  <li>Select your project and OAuth 2.0 Client ID</li>
                  <li>Add <code className="bg-muted px-1 py-0.5 rounded">http://localhost:3000/api/auth/callback/google</code> to Authorized redirect URIs</li>
                  <li>Save changes and try again</li>
                </ol>
              </div>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Button onClick={() => window.location.reload()} className="gap-2">
              <RefreshCw className="h-4 w-4" />
              Try Again
            </Button>
            <Link href="/auth/signin">
              <Button variant="outline" className="w-full gap-2">
                <ArrowLeft className="h-4 w-4" />
                Back to Sign In
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
