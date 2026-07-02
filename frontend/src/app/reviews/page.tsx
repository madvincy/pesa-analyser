'use client'

import { ReviewsSection } from '@/components/ReviewsSection'
import { Navigation } from '@/components/Navigation'
import { Footer } from '@/components/Footer'
import { SessionProvider } from 'next-auth/react'
import { motion } from 'framer-motion'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Star, ArrowRight } from 'lucide-react'

export default function ReviewsPage() {
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
            <ReviewsSection />
          </motion.div>
          
          {/* Write Review CTA */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mt-12 max-w-3xl mx-auto"
          >
            <div className="bg-gradient-to-r from-primary/5 via-secondary/10 to-primary/5 rounded-2xl p-8 text-center border">
              <div className="flex justify-center mb-4">
                <div className="p-3 rounded-full bg-yellow-500/10">
                  <Star className="h-8 w-8 text-yellow-500" />
                </div>
              </div>
              <h3 className="text-2xl font-bold font-playfair mb-2">
                Share Your Experience
              </h3>
              <p className="text-muted-foreground mb-6 max-w-lg mx-auto">
                Help others make informed decisions by sharing your experience with Pesa Analyser
              </p>
              <Link href="/#contact">
                <Button size="lg" className="gap-2 group">
                  Write a Review
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
