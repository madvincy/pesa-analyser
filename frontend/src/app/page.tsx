'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { UploadZone } from '@/components/UploadZone'
import { Dashboard } from '@/components/Dashboard'
import { Footer } from '@/components/Footer'
import { Navigation } from '@/components/Navigation'
import { HeroSection } from '@/components/HeroSection'
import { FeaturesSection } from '@/components/FeaturesSection'
import { HowItWorksSection } from '@/components/HowItWorksSection'
import { AboutUsSection } from '@/components/AboutUsSection'
import { TestimonialsSection } from '@/components/TestimonialsSection'
import { SupportedStatementsSection } from '@/components/SupportedStatementsSection'
import { ContactSection } from '@/components/ContactSection'

export default function Home() {
  const [analysisId, setAnalysisId] = useState<string | null>(null)

  return (
    <main className="min-h-screen bg-background pt-16">
      <Navigation />
      
      {!analysisId ? (
        <div className="space-y-0">
          <HeroSection />
          <div id="features"><FeaturesSection /></div>
          <div id="how-it-works"><HowItWorksSection /></div>
          <div id="about"><AboutUsSection /></div>
          <div id="reviews"><TestimonialsSection /></div>
          <SupportedStatementsSection />
          
          <section className="py-20 gradient-bg">
            <div className="container">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="text-center mb-8"
              >
                <h2 className="text-3xl md:text-4xl font-bold font-playfair mb-4">
                  Ready to <span className="gradient-text">Analyze</span> Your Finances?
                </h2>
                <p className="text-muted-foreground max-w-2xl mx-auto">
                  Upload your statement now and get instant insights
                </p>
              </motion.div>
              <UploadZone onUploadComplete={(id) => setAnalysisId(id)} />
            </div>
          </section>
          
          <div id="contact"><ContactSection /></div>
        </div>
      ) : (
        <div className="container py-8">
          <Dashboard analysisId={analysisId} />
        </div>
      )}
      
      <Footer />
    </main>
  )
}
