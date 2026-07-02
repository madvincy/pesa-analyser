'use client'

import { Card, CardContent } from '@/components/ui/card'
import { Navigation } from '@/components/Navigation'
import { Footer } from '@/components/Footer'
import { SessionProvider } from 'next-auth/react'
import { motion } from 'framer-motion'
import { Shield, Lock, Eye, Database, Trash2, UserCheck, Mail, FileText, ArrowRight } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'

export default function PrivacyPolicy() {
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
                  <Shield className="h-10 w-10 text-primary" />
                </div>
              </div>
              <h1 className="text-4xl font-bold tracking-tight font-playfair">Privacy Policy</h1>
              <p className="text-muted-foreground">
                Last Updated: {new Date().toLocaleDateString('en-KE', { year: 'numeric', month: 'long', day: 'numeric' })}
              </p>
              <p className="text-muted-foreground max-w-2xl mx-auto">
                Your privacy is important to us. This policy explains how we collect, use, and protect your personal information.
              </p>
            </div>

            {/* Quick Summary */}
            <Card className="bg-primary/5 border-primary/20">
              <CardContent className="py-6">
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="flex items-start gap-3">
                    <Lock className="h-5 w-5 text-primary mt-0.5" />
                    <div>
                      <h4 className="font-semibold text-sm">Data Protection</h4>
                      <p className="text-sm text-muted-foreground">We use bank-grade encryption to protect your data</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Trash2 className="h-5 w-5 text-primary mt-0.5" />
                    <div>
                      <h4 className="font-semibold text-sm">Data Deletion</h4>
                      <p className="text-sm text-muted-foreground">You can delete your data at any time</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <UserCheck className="h-5 w-5 text-primary mt-0.5" />
                    <div>
                      <h4 className="font-semibold text-sm">Your Rights</h4>
                      <p className="text-sm text-muted-foreground">You have full control over your personal data</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Full Policy */}
            <div className="space-y-6">
              <section>
                <h2 className="text-2xl font-semibold flex items-center gap-2 font-playfair">
                  <FileText className="h-6 w-6" />
                  Information We Collect
                </h2>
                <Card>
                  <CardContent className="space-y-4 pt-6">
                    <div>
                      <h3 className="font-medium">Personal Information</h3>
                      <ul className="list-disc list-inside text-muted-foreground space-y-1 mt-2">
                        <li>Name and email address (for account creation and report delivery)</li>
                        <li>Phone number (for M-PESA payment verification)</li>
                        <li>IP address and browser information (for security and analytics)</li>
                      </ul>
                    </div>
                    <div>
                      <h3 className="font-medium">Financial Data</h3>
                      <ul className="list-disc list-inside text-muted-foreground space-y-1 mt-2">
                        <li>Transaction amounts and categories (anonymized)</li>
                        <li>Spending patterns and trends (aggregated)</li>
                        <li>Income sources (anonymized)</li>
                      </ul>
                    </div>
                    <div>
                      <h3 className="font-medium">What We DON'T Collect</h3>
                      <ul className="list-disc list-inside text-muted-foreground space-y-1 mt-2">
                        <li>Full transaction descriptions with PII</li>
                        <li>Account numbers or PINs</li>
                        <li>Recipient names or phone numbers</li>
                        <li>Residential or business addresses</li>
                      </ul>
                    </div>
                  </CardContent>
                </Card>
              </section>

              <section>
                <h2 className="text-2xl font-semibold flex items-center gap-2 font-playfair">
                  <Database className="h-6 w-6" />
                  How We Use Your Information
                </h2>
                <Card>
                  <CardContent className="space-y-4 pt-6">
                    <div>
                      <h3 className="font-medium">Primary Uses</h3>
                      <ul className="list-disc list-inside text-muted-foreground space-y-1 mt-2">
                        <li>Analyze your financial transactions to provide insights</li>
                        <li>Generate personalized financial reports</li>
                        <li>Improve our AI models and analysis accuracy</li>
                        <li>Send you your analysis results and reports</li>
                      </ul>
                    </div>
                  </CardContent>
                </Card>
              </section>

              <section>
                <h2 className="text-2xl font-semibold flex items-center gap-2 font-playfair">
                  <Eye className="h-6 w-6" />
                  Your Rights
                </h2>
                <Card>
                  <CardContent className="space-y-4 pt-6">
                    <ul className="list-disc list-inside text-muted-foreground space-y-2">
                      <li><strong>Access:</strong> You can request a copy of your data at any time</li>
                      <li><strong>Rectification:</strong> You can correct inaccurate data</li>
                      <li><strong>Erasure:</strong> You can request complete data deletion</li>
                      <li><strong>Portability:</strong> You can export your data in a machine-readable format</li>
                    </ul>
                  </CardContent>
                </Card>
              </section>

              <section>
                <h2 className="text-2xl font-semibold flex items-center gap-2 font-playfair">
                  <Mail className="h-6 w-6" />
                  Contact Us
                </h2>
                <Card>
                  <CardContent className="space-y-4 pt-6">
                    <p className="text-muted-foreground">
                      If you have any questions about this privacy policy or your data, please contact us:
                    </p>
                    <ul className="space-y-1 text-muted-foreground">
                      <li><strong>Email:</strong> privacy@pesaanalyser.com</li>
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
