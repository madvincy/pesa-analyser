'use client'

import { useState } from 'react'
import { signIn, signOut, useSession } from 'next-auth/react'
import { Button } from '@/components/ui/button'
import { 
  User, LogOut, Loader2, Chrome, Facebook,
  Mail, ChevronDown, Sparkles
} from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { SocialLoginPopup } from './SocialLoginPopup'

export function AuthButtons() {
  const { data: session, status } = useSession()
  const [showPopup, setShowPopup] = useState(false)
  const [loading, setLoading] = useState<string | null>(null)

  const handleSignIn = () => {
    setShowPopup(true)
  }

  const handleProviderSignIn = async (provider: string) => {
    setLoading(provider)
    await signIn(provider, { callbackUrl: '/dashboard' })
    setLoading(null)
  }

  if (status === 'loading') {
    return (
      <Button variant="ghost" size="icon" disabled>
        <Loader2 className="h-4 w-4 animate-spin" />
      </Button>
    )
  }

  if (session) {
    return (
      <>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="gap-2">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="bg-primary/10 text-primary">
                  {session.user?.name?.[0] || 'U'}
                </AvatarFallback>
              </Avatar>
              <span className="hidden md:inline">{session.user?.name}</span>
              <ChevronDown className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => window.location.href = '/dashboard'}>
              <User className="mr-2 h-4 w-4" />
              Dashboard
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => signOut()}>
              <LogOut className="mr-2 h-4 w-4" />
              Sign Out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </>
    )
  }

  return (
    <>
      <Button 
        variant="outline" 
        className="gap-2"
        onClick={handleSignIn}
      >
        <Sparkles className="h-4 w-4" />
        Sign In
      </Button>

      <SocialLoginPopup
        isOpen={showPopup}
        onClose={() => setShowPopup(false)}
        onSuccess={() => setShowPopup(false)}
        redirectTo="/dashboard"
      />
    </>
  )
}
