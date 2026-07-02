'use client'

import { motion } from 'framer-motion'
import { Users, Target, Heart, Award } from 'lucide-react'
import { Card, CardContent } from './ui/card'

const values = [
  {
    icon: Users,
    title: 'Customer First',
    description: 'We prioritize our users\' financial well-being above all else.',
  },
  {
    icon: Target,
    title: 'Innovation',
    description: 'Continuously improving our AI to provide better insights.',
  },
  {
    icon: Heart,
    title: 'Trust & Transparency',
    description: 'We believe in complete transparency with your data.',
  },
  {
    icon: Award,
    title: 'Excellence',
    description: 'Committed to delivering the highest quality financial analysis.',
  },
]

export function AboutUsSection() {
  return (
    <section className="py-20">
      <div className="container">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl md:text-4xl font-bold font-playfair mb-6">
              About <span className="gradient-text">Pesa Analyser</span>
            </h2>
            <p className="text-muted-foreground mb-4">
              Pesa Analyser was born from a simple idea: Everyone deserves to understand their finances.
              We saw that many Kenyans struggled to make sense of their M-PESA and bank statements,
              missing out on crucial insights about their spending and saving habits.
            </p>
            <p className="text-muted-foreground mb-6">
              Our AI-powered platform analyzes your financial data to provide actionable insights,
              helping you make better financial decisions. Whether you&apos;re an individual tracking
              personal expenses or a small business managing cash flow, Pesa Analyser is here to help.
            </p>
            <div className="flex items-center gap-4">
              <div className="flex -space-x-2">
                {['JM', 'SA', 'DO', 'GW'].map((initials) => (
                  <div
                    key={initials}
                    className="w-10 h-10 rounded-full bg-primary/10 border-2 border-background flex items-center justify-center text-xs font-medium"
                  >
                    {initials}
                  </div>
                ))}
              </div>
              <div>
                <div className="text-sm font-medium">Trusted by 10,000+ users</div>
                <div className="text-xs text-muted-foreground">Across Kenya and beyond</div>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="grid grid-cols-2 gap-4"
          >
            {values.map((value, index) => (
              <Card key={value.title} className="card-hover border-0 shadow-lg">
                <CardContent className="p-6 text-center">
                  <value.icon className="h-8 w-8 text-primary mx-auto mb-3" />
                  <h4 className="font-semibold text-sm">{value.title}</h4>
                  <p className="text-xs text-muted-foreground mt-1">{value.description}</p>
                </CardContent>
              </Card>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  )
}
