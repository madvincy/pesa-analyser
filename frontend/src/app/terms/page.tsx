'use client'

import { Card, CardContent } from '@/components/ui/card'
import { Navigation } from '@/components/Navigation'
import { Footer } from '@/components/Footer'
import { SessionProvider } from 'next-auth/react'
import { motion } from 'framer-motion'
import { FileCheck, Scale, AlertCircle, Users, Shield, Gavel, CreditCard, Mail, ArrowRight } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'

export default function TermsAndConditions() {
  return (
    <SessionProvider>
      <main className="min-h-screen bg-background pt-16">
        <Navigation />
        
        <div className="container py-12 max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="space-y-8"
          >
            {/* Header */}
            <div className="text-center space-y-4">
              <div className="flex justify-center">
                <div className="p-3 rounded-full bg-primary/10">
                  <Scale className="h-10 w-10 text-primary" />
                </div>
              </div>
              <h1 className="text-4xl font-bold tracking-tight font-playfair">Terms and Conditions</h1>
              <p className="text-muted-foreground">
                Last Updated: {new Date().toLocaleDateString('en-KE', { year: 'numeric', month: 'long', day: 'numeric' })}
              </p>
              <p className="text-muted-foreground max-w-2xl mx-auto">
                Please read these terms carefully before using Pesa Analyser.
              </p>
            </div>

            {/* Quick Summary */}
            <Card className="bg-primary/5 border-primary/20">
              <CardContent className="py-6">
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="flex items-start gap-3">
                    <Shield className="h-5 w-5 text-primary mt-0.5" />
                    <div>
                      <h4 className="font-semibold text-sm">Legal Agreement</h4>
                      <p className="text-sm text-muted-foreground">By using our service, you agree to these terms</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Users className="h-5 w-5 text-primary mt-0.5" />
                    <div>
                      <h4 className="font-semibold text-sm">Your Rights</h4>
                      <p className="text-sm text-muted-foreground">You retain ownership of your data</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Gavel className="h-5 w-5 text-primary mt-0.5" />
                    <div>
                      <h4 className="font-semibold text-sm">Governing Law</h4>
                      <p className="text-sm text-muted-foreground">These terms are governed by Kenyan law</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Terms Content */}
            <div className="space-y-6">
              <section>
                <h2 className="text-2xl font-semibold flex items-center gap-2 font-playfair">
                  <FileCheck className="h-6 w-6" />
                  Acceptance of Terms
                </h2>
                <Card>
                  <CardContent className="space-y-4 pt-6">
                    <p className="text-muted-foreground">
                      By accessing or using Pesa Analyser, you agree to be bound by these Terms and Conditions. 
                      If you do not agree to these terms, please do not use our service.
                    </p>
                    <div className="bg-yellow-50 dark:bg-yellow-950/10 p-4 rounded-lg border border-yellow-200 dark:border-yellow-800">
                      <h4 className="font-semibold flex items-center gap-2">
                        <AlertCircle className="h-5 w-5 text-yellow-600" />
                        Important Notice
                      </h4>
                      <p className="text-sm text-muted-foreground mt-1">
                        These terms constitute a legally binding agreement between you and Pesa Analyser Ltd.
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </section>

              <section>
                <h2 className="text-2xl font-semibold flex items-center gap-2 font-playfair">
                  <Users className="h-6 w-6" />
                  User Accounts
                </h2>
                <Card>
                  <CardContent className="space-y-4 pt-6">
                    <ul className="list-disc list-inside text-muted-foreground space-y-2">
                      <li>You must be 18 years or older to use this service</li>
                      <li>You are responsible for maintaining the confidentiality of your account credentials</li>
                      <li>You agree to provide accurate and complete information</li>
                      <li>You are solely responsible for all activities that occur under your account</li>
                    </ul>
                  </CardContent>
                </Card>
              </section>

              <section>
                <h2 className="text-2xl font-semibold flex items-center gap-2 font-playfair">
                  <CreditCard className="h-6 w-6" />
                  Payments and Fees
                </h2>
                <Card>
                  <CardContent className="space-y-4 pt-6">
                    <div>
                      <h3 className="font-medium">Pricing Structure</h3>
                      <ul className="list-disc list-inside text-muted-foreground space-y-1 mt-2">
                        <li><strong>Free Tier:</strong> Basic summary charts (1-month statements)</li>
                        <li><strong>Basic Analysis:</strong> KES 50 - 6-month detailed analysis</li>
                        <li><strong>Premium Analysis:</strong> KES 150 - Full analysis with 20+ insights</li>
                        <li><strong>Credit-Ready Report:</strong> KES 500 - Comprehensive PDF report</li>
                      </ul>
                    </div>
                  </CardContent>
                </Card>
              </section>

              <section>
                <h2 className="text-2xl font-semibold flex items-center gap-2 font-playfair">
                  <AlertCircle className="h-6 w-6" />
                  Disclaimer
                </h2>
                <Card>
                  <CardContent className="space-y-4 pt-6">
                    <div className="bg-red-50 dark:bg-red-950/10 p-4 rounded-lg border border-red-200 dark:border-red-800">
                      <h4 className="font-semibold text-red-700 dark:text-red-400">Important Disclaimer</h4>
                      <ul className="list-disc list-inside text-muted-foreground space-y-1 mt-2">
                        <li>Pesa Analyser provides financial insights but does NOT constitute financial advice</li>
                        <li>We are not responsible for financial decisions made based on our analysis</li>
                        <li>Results are based on the data you provide - accuracy depends on data quality</li>
                      </ul>
                    </div>
                  </CardContent>
                </Card>
              </section>

              <section>
                <h2 className="text-2xl font-semibold flex items-center gap-2 font-playfair">
                  <Mail className="h-6 w-6" />
                  Contact Information
                </h2>
                <Card>
                  <CardContent className="space-y-4 pt-6">
                    <p className="text-muted-foreground">
                      If you have any questions about these terms, please contact us:
                    </p>
                    <ul className="space-y-1 text-muted-foreground">
                      <li><strong>Email:</strong> legal@pesaanalyser.com</li>
                      <li><strong>Phone:</strong> +254 700 123 456</li>
                      <li><strong>Address:</strong> Pesa Analyser Ltd, Nairobi, Kenya</li>
                    </ul>
                    <Link href="/#contact">
                      <Button variant="outline" className="gap-2 mt-2">
                        Contact Us
                        <ArrowRight className="h-4 w-4" />
                      </Button>
                    </Link>
                  </CardContent>
                </Card>
              </section>
            </div>
          </motion.div>
        </div>
        
        <Footer />
      </main>
    </SessionProvider>
  )
}
