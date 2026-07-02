'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { signIn } from 'next-auth/react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  X, Chrome, Facebook, Mail, Sparkles, ArrowRight, Loader2, AlertCircle
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useRouter } from 'next/navigation'

interface SocialLoginPopupProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
  redirectTo?: string
}

export function SocialLoginPopup({ 
  isOpen, 
  onClose, 
  onSuccess,
  redirectTo = '/dashboard' 
}: SocialLoginPopupProps) {
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [email, setEmail] = useState('')
  const [showEmailInput, setShowEmailInput] = useState(false)
  const router = useRouter()
  const isMounted = useRef(true)

  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  const handleProviderSignIn = useCallback(async (provider: string) => {
    if (loading) return
    
    setLoading(provider)
    setError(null)
    
    try {
      localStorage.setItem('lastLoginProvider', provider)
      
      const result = await signIn(provider, {
        callbackUrl: redirectTo,
        redirect: false,
      })

      if (result?.error) {
        setError(`Failed to sign in with ${provider}. Please try again.`)
        setLoading(null)
        return
      }

      if (result?.ok) {
        localStorage.setItem('authMethod', provider)
        if (isMounted.current) {
          onSuccess?.()
          onClose()
          router.push(redirectTo)
        }
      }
    } catch (error) {
      if (isMounted.current) {
        setError('An unexpected error occurred. Please try again.')
        setLoading(null)
      }
    }
  }, [loading, redirectTo, onSuccess, onClose, router])

  const handleEmailSignIn = useCallback(async () => {
    if (!email || loading) return

    setLoading('email')
    setError(null)

    try {
      const result = await signIn('email', {
        email,
        callbackUrl: redirectTo,
        redirect: false,
      })

      if (result?.error) {
        setError('Failed to send magic link. Please try again.')
        setLoading(null)
        return
      }

      setShowEmailInput(false)
      setLoading(null)
      localStorage.setItem('userEmail', email)
      localStorage.setItem('authMethod', 'email')
      
      setError('✨ Magic link sent! Check your email.')
      
      setTimeout(() => {
        if (isMounted.current) {
          onClose()
          router.push(redirectTo)
        }
      }, 3000)
    } catch (error) {
      if (isMounted.current) {
        setError('An unexpected error occurred. Please try again.')
        setLoading(null)
      }
    }
  }, [email, loading, redirectTo, onClose, router])

  const handleClose = useCallback(() => {
    if (!loading) {
      onClose()
    }
  }, [loading, onClose])

  if (!isOpen) return null

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
            onClick={handleClose}
          />

          <motion.div
            initial={{ scale: 0.9, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.9, opacity: 0, y: 20 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <Card className="w-full max-w-md relative overflow-hidden border-0 shadow-2xl">
              <button
                onClick={handleClose}
                className="absolute right-4 top-4 z-10 p-1 rounded-full hover:bg-muted transition-colors"
                disabled={!!loading}
                aria-label="Close"
              >
                <X className="h-5 w-5 text-muted-foreground" />
              </button>

              <CardContent className="p-6 pt-8">
                <div className="flex justify-center mb-4">
                  <div className="relative">
                    <div className="h-16 w-16 rounded-full bg-gradient-to-r from-primary to-blue-600 flex items-center justify-center">
                      <Sparkles className="h-8 w-8 text-white" />
                    </div>
                  </div>
                </div>

                <div className="text-center mb-6">
                  <h2 className="text-2xl font-bold font-playfair">Welcome Back! 👋</h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    Sign in to continue to your dashboard
                  </p>
                </div>

                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`mb-4 p-3 rounded-lg text-sm flex items-start gap-2 ${
                      error.includes('✨') 
                        ? 'bg-green-50 text-green-700 dark:bg-green-950/20 dark:text-green-400'
                        : 'bg-red-50 text-red-700 dark:bg-red-950/20 dark:text-red-400'
                    }`}
                  >
                    <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                    <span>{error}</span>
                  </motion.div>
                )}

                <div className="space-y-3">
                  <Button
                    variant="outline"
                    className="w-full h-12 gap-3 relative overflow-hidden group hover:border-primary/50 transition-all"
                    onClick={() => handleProviderSignIn('google')}
                    disabled={!!loading}
                  >
                    {loading === 'google' ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <>
                        <Chrome className="h-5 w-5 text-[#4285F4]" />
                        <span>Continue with Google</span>
                      </>
                    )}
                  </Button>

                  <Button
                    variant="outline"
                    className="w-full h-12 gap-3 relative overflow-hidden group hover:border-primary/50 transition-all"
                    onClick={() => handleProviderSignIn('facebook')}
                    disabled={!!loading}
                  >
                    {loading === 'facebook' ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <>
                        <Facebook className="h-5 w-5 text-[#1877F2]" />
                        <span>Continue with Facebook</span>
                      </>
                    )}
                  </Button>

                  <div className="relative my-4">
                    <div className="absolute inset-0 flex items-center">
                      <span className="w-full border-t" />
                    </div>
                    <div className="relative flex justify-center text-xs uppercase">
                      <span className="bg-background px-2 text-muted-foreground">
                        Or continue with
                      </span>
                    </div>
                  </div>

                  {!showEmailInput ? (
                    <Button
                      variant="ghost"
                      className="w-full gap-2 text-muted-foreground hover:text-foreground"
                      onClick={() => setShowEmailInput(true)}
                      disabled={!!loading}
                    >
                      <Mail className="h-4 w-4" />
                      <span>Sign in with Email</span>
                    </Button>
                  ) : (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      className="space-y-3"
                    >
                      <div className="flex gap-2">
                        <div className="relative flex-1">
                          <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                          <input
                            type="email"
                            placeholder="Enter your email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full h-10 pl-10 pr-3 rounded-md border border-input bg-background text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            disabled={loading === 'email'}
                          />
                        </div>
                        <Button
                          onClick={handleEmailSignIn}
                          disabled={loading === 'email' || !email}
                        >
                          {loading === 'email' ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <ArrowRight className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-xs text-muted-foreground"
                        onClick={() => setShowEmailInput(false)}
                      >
                        ← Back to social login
                      </Button>
                    </motion.div>
                  )}
                </div>

                <div className="mt-6 pt-4 border-t text-center">
                  <p className="text-xs text-muted-foreground">
                    By continuing, you agree to our{' '}
                    <a href="/terms" className="text-primary hover:underline">
                      Terms of Service
                    </a>
                    {' '}and{' '}
                    <a href="/privacy-policy" className="text-primary hover:underline">
                      Privacy Policy
                    </a>
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    🔒 Your data is encrypted and secure
                  </p>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
