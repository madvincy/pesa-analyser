'use client'

import { FAQSection } from '@/components/FAQSection'
import { Navigation } from '@/components/Navigation'
import { Footer } from '@/components/Footer'
import { SessionProvider } from 'next-auth/react'
import { motion } from 'framer-motion'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { MessageCircle, ArrowRight } from 'lucide-react'

export default function FAQsPage() {
  return (
    <SessionProvider>
      <main className="min-h-screen bg-background pt-16">
        <Navigation />
        
        <div className="container py-12">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <FAQSection />
          </motion.div>
          
          {/* Contact CTA */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mt-12 max-w-3xl mx-auto"
          >
            <div className="bg-gradient-to-r from-primary/10 via-secondary/20 to-primary/10 rounded-2xl p-8 text-center border border-primary/20">
              <div className="flex justify-center mb-4">
                <div className="p-3 rounded-full bg-primary/10">
                  <MessageCircle className="h-8 w-8 text-primary" />
                </div>
              </div>
              <h3 className="text-2xl font-bold font-playfair mb-2">
                Still have questions?
              </h3>
              <p className="text-muted-foreground mb-6 max-w-lg mx-auto">
                Can&apos;t find what you&apos;re looking for? Our support team is here to help you.
              </p>
              <Link href="/#contact">
                <Button size="lg" className="gap-2 group">
                  Contact Us
                  <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
                </Button>
              </Link>
            </div>
          </motion.div>
        </div>
        
        <Footer />
      </main>
    </SessionProvider>
  )
}
