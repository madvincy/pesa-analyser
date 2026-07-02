'use client'

import { motion } from 'framer-motion'
import { 
  Zap, Shield, BarChart3, FileText, 
  Clock, Users, Brain, Sparkles,
  TrendingUp, PieChart, Wallet, CreditCard
} from 'lucide-react'
import { Card, CardContent } from './ui/card'

const features = [
  {
    icon: Zap,
    title: 'Instant Analysis',
    description: 'Get AI-powered insights in seconds. Upload and analyze your statements instantly.',
    color: 'text-yellow-500',
    bg: 'bg-yellow-500/10',
  },
  {
    icon: Shield,
    title: 'Secure & Private',
    description: 'Bank-grade encryption ensures your financial data is always safe and private.',
    color: 'text-blue-500',
    bg: 'bg-blue-500/10',
  },
  {
    icon: BarChart3,
    title: '20+ Insights',
    description: 'Comprehensive financial metrics including spending patterns, income trends, and more.',
    color: 'text-purple-500',
    bg: 'bg-purple-500/10',
  },
  {
    icon: FileText,
    title: 'Detailed Reports',
    description: 'Generate beautiful PDF reports with charts, insights, and recommendations.',
    color: 'text-green-500',
    bg: 'bg-green-500/10',
  },
  {
    icon: Brain,
    title: 'AI-Powered',
    description: 'Advanced AI algorithms analyze your transactions for deeper financial understanding.',
    color: 'text-pink-500',
    bg: 'bg-pink-500/10',
  },
  {
    icon: Wallet,
    title: 'M-PESA Integration',
    description: 'Seamlessly analyze M-PESA statements with support for all transaction types.',
    color: 'text-orange-500',
    bg: 'bg-orange-500/10',
  },
  {
    icon: PieChart,
    title: 'Category Analysis',
    description: 'Automatically categorize spending into Food, Transport, Utilities, and more.',
    color: 'text-cyan-500',
    bg: 'bg-cyan-500/10',
  },
  {
    icon: TrendingUp,
    title: 'Track Growth',
    description: 'Monitor your financial growth with month-over-month comparisons and trends.',
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
  },
]

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
}

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
}

export function FeaturesSection() {
  return (
    <section className="py-20">
      <div className="container">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <h2 className="text-3xl md:text-4xl font-bold font-playfair mb-4">
            Powerful Features for{' '}
            <span className="gradient-text">Financial Freedom</span>
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Everything you need to understand and improve your financial health
          </p>
        </motion.div>

        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
        >
          {features.map((feature, index) => (
            <motion.div key={feature.title} variants={item}>
              <Card className="h-full card-hover border-0 shadow-lg hover:shadow-xl transition-all duration-300">
                <CardContent className="p-6 text-center">
                  <div className={`w-12 h-12 rounded-full ${feature.bg} flex items-center justify-center mx-auto mb-4`}>
                    <feature.icon className={`h-6 w-6 ${feature.color}`} />
                  </div>
                  <h3 className="font-semibold mb-2">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground">{feature.description}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}
