'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useSession } from 'next-auth/react'
import { motion, AnimatePresence } from 'framer-motion'
import Link from 'next/link'
import { useRouter, usePathname } from 'next/navigation'
import { 
  Menu, X, Sparkles, ArrowRight, LayoutDashboard,
  Home, Info, HelpCircle, MessageCircle, Star
} from 'lucide-react'
import { Button } from './ui/button'
import { ThemeToggle } from './theme-toggle'
import { AuthButtons } from './auth/AuthButtons'
import { useAutoLoginPrompt } from '@/hooks/useAutoLoginPrompt'
import { SocialLoginPopup } from './auth/SocialLoginPopup'

export function Navigation() {
  const { data: session } = useSession()
  const router = useRouter()
  const pathname = usePathname()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const { showPrompt, setShowPrompt } = useAutoLoginPrompt()
  const isMounted = useRef(true)

  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  useEffect(() => {
    const handleScroll = () => {
      if (isMounted.current) {
        setScrolled(window.scrollY > 10)
      }
    }
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  // Close mobile menu on route change
  useEffect(() => {
    if (mobileMenuOpen && isMounted.current) {
      setMobileMenuOpen(false)
    }
  }, [pathname])

  const navItems = [
    { label: 'Home', href: '/', icon: Home },
    { label: 'Features', href: '#features', icon: Sparkles },
    { label: 'How It Works', href: '#how-it-works', icon: HelpCircle },
    { label: 'Reviews', href: '#reviews', icon: Star },
    { label: 'Contact', href: '#contact', icon: MessageCircle },
  ]

  const handleGetStarted = useCallback(() => {
    if (session) {
      router.push('/dashboard')
    } else {
      router.push('/auth/signin')
    }
  }, [session, router])

  const toggleMobileMenu = useCallback(() => {
    setMobileMenuOpen(prev => !prev)
  }, [])

  return (
    <>
      <header className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled ? 'bg-background/95 backdrop-blur border-b' : 'bg-transparent'
      }`}>
        <div className="container flex h-16 items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-8 w-8 rounded bg-gradient-to-r from-primary to-blue-600 flex items-center justify-center">
              <span className="text-primary-foreground font-bold text-sm">PA</span>
            </div>
            <span className="font-bold text-lg gradient-text">Pesa Analyser</span>
          </Link>
          
          <nav className="hidden md:flex items-center gap-6 text-sm">
            {navItems.map((item) => (
              <Link
                key={item.label}
                href={item.href}
                className="text-muted-foreground hover:text-primary transition-colors"
                onClick={() => {
                  if (item.href.startsWith('#')) {
                    const element = document.getElementById(item.href.substring(1))
                    if (element) {
                      element.scrollIntoView({ behavior: 'smooth' })
                    }
                  }
                }}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <AuthButtons />
            
            <Button 
              variant="ghost" 
              size="icon" 
              className="md:hidden"
              onClick={toggleMobileMenu}
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
          </div>
        </div>
        
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="md:hidden border-t bg-background/95 backdrop-blur"
            >
              <div className="container py-4 space-y-3">
                {navItems.map((item) => (
                  <Link
                    key={item.label}
                    href={item.href}
                    className="flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors"
                    onClick={() => {
                      setMobileMenuOpen(false)
                      if (item.href.startsWith('#')) {
                        const element = document.getElementById(item.href.substring(1))
                        if (element) {
                          setTimeout(() => {
                            element.scrollIntoView({ behavior: 'smooth' })
                          }, 100)
                        }
                      }
                    }}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                ))}
                <div className="pt-3 border-t">
                  {session ? (
                    <Button 
                      className="w-full" 
                      onClick={() => {
                        setMobileMenuOpen(false)
                        router.push('/dashboard')
                      }}
                    >
                      <LayoutDashboard className="h-4 w-4 mr-2" />
                      Dashboard
                    </Button>
                  ) : (
                    <Button 
                      className="w-full gap-2"
                      onClick={() => {
                        setMobileMenuOpen(false)
                        handleGetStarted()
                      }}
                    >
                      <Sparkles className="h-4 w-4" />
                      Get Started
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      <SocialLoginPopup
        isOpen={showPrompt}
        onClose={() => setShowPrompt(false)}
        redirectTo="/dashboard"
      />
    </>
  )
}
