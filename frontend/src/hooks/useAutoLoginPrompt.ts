'use client'

import { useState, useEffect, useRef } from 'react'
import { useSession } from 'next-auth/react'
import { usePathname } from 'next/navigation'

export function useAutoLoginPrompt() {
  const { data: session, status } = useSession()
  const pathname = usePathname()
  const [showPrompt, setShowPrompt] = useState(false)
  const hasPrompted = useRef(false)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    // Don't show on auth pages or if already authenticated
    if (
      status === 'loading' ||
      status === 'authenticated' ||
      pathname?.startsWith('/auth') ||
      pathname?.startsWith('/admin')
    ) {
      setShowPrompt(false)
      return
    }

    // Check if user has already been prompted
    const prompted = localStorage.getItem('authPromptShown')
    const lastVisit = localStorage.getItem('lastVisit')
    const now = Date.now()

    // Show prompt if:
    // 1. Never prompted before, or
    // 2. It's been more than 7 days since last visit, or
    // 3. User has a saved provider preference
    const hasProvider = localStorage.getItem('lastLoginProvider')
    const shouldShow = !prompted || 
      (lastVisit && (now - parseInt(lastVisit)) > 7 * 24 * 60 * 60 * 1000) ||
      (hasProvider && !session)

    if (shouldShow && !hasPrompted.current && !showPrompt) {
      // Clear any existing timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }

      // Add a delay to let the page load
      timeoutRef.current = setTimeout(() => {
        if (!hasPrompted.current && !session) {
          setShowPrompt(true)
          hasPrompted.current = true
          localStorage.setItem('authPromptShown', 'true')
          localStorage.setItem('lastVisit', now.toString())
        }
      }, 3000)
    }

    // Update last visit
    localStorage.setItem('lastVisit', now.toString())

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [status, session, pathname, showPrompt])

  return {
    showPrompt,
    setShowPrompt,
  }
}
