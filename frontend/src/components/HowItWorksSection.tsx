'use client'

import { motion } from 'framer-motion'
import { Upload, FileSearch, BarChart, Download } from 'lucide-react'
import { Card, CardContent } from './ui/card'

const steps = [
  {
    icon: Upload,
    title: 'Upload Statement',
    description: 'Drag and drop your M-PESA or bank statement PDF, CSV, or Excel file.',
    color: 'text-blue-500',
  },
  {
    icon: FileSearch,
    title: 'AI Analysis',
    description: 'Our AI analyzes your transactions to uncover spending patterns and insights.',
    color: 'text-purple-500',
  },
  {
    icon: BarChart,
    title: 'View Insights',
    description: 'Get 20+ financial insights with beautiful charts and visualizations.',
    color: 'text-green-500',
  },
  {
    icon: Download,
    title: 'Download Report',
    description: 'Export detailed PDF reports for tax compliance or loan applications.',
    color: 'text-orange-500',
  },
]

export function HowItWorksSection() {
  return (
    <section className="py-20 bg-secondary/30">
      <div className="container">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-12"
        >
          <h2 className="text-3xl md:text-4xl font-bold font-playfair mb-4">
            How It <span className="gradient-text">Works</span>
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Get started in 4 simple steps
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 relative">
          {/* Connecting Line */}
          <div className="hidden lg:block absolute top-1/2 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 via-green-500 to-orange-500 -translate-y-1/2" />

          {steps.map((step, index) => (
            <motion.div
              key={step.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.2 }}
              className="relative"
            >
              <Card className="h-full border-0 shadow-lg card-hover">
                <CardContent className="p-6 text-center">
                  <div className="relative">
                    <div className={`w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4`}>
                      <step.icon className="h-8 w-8 text-primary" />
                    </div>
                    <div className="absolute -top-2 -right-2 w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold">
                      {index + 1}
                    </div>
                  </div>
                  <h3 className="font-semibold mb-2">{step.title}</h3>
                  <p className="text-sm text-muted-foreground">{step.description}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
