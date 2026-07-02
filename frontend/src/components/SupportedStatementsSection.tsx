'use client'

import { motion } from 'framer-motion'
import { 
  Building2, Smartphone, FileSpreadsheet, 
  FileText, File, CheckCircle2, Zap 
} from 'lucide-react'
import { Card, CardContent } from './ui/card'

const banks = [
  { name: 'KCB', icon: Building2, color: 'text-blue-600' },
  { name: 'Equity', icon: Building2, color: 'text-red-600' },
  { name: 'Cooperative', icon: Building2, color: 'text-green-600' },
  { name: 'Stanbic', icon: Building2, color: 'text-blue-500' },
  { name: 'ABSA', icon: Building2, color: 'text-red-500' },
  { name: 'NCBA', icon: Building2, color: 'text-orange-500' },
]

const formats = [
  { name: 'PDF', icon: FileText, color: 'text-red-500' },
  { name: 'CSV', icon: File, color: 'text-green-500' },
  { name: 'Excel', icon: FileSpreadsheet, color: 'text-blue-500' },
]

const features = [
  'M-PESA Statements (All versions)',
  'Bank Statements (All major banks)',
  'PayBill & Till Analysis',
  'Fuliza & M-Shwari Tracking',
  'P2P Transfer Analysis',
  'Subscription Detection',
]

export function SupportedStatementsSection() {
  return (
    <section className="py-20">
      <div className="container">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-12"
        >
          <h2 className="text-3xl md:text-4xl font-bold font-playfair mb-4">
            Supported <span className="gradient-text">Statements</span>
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            We support all major banks and file formats
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Banks */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
          >
            <Card className="h-full border-0 shadow-lg">
              <CardContent className="p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Smartphone className="h-5 w-5 text-primary" />
                  <h3 className="font-semibold">Banks Supported</h3>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {banks.map((bank) => (
                    <div
                      key={bank.name}
                      className="flex items-center gap-2 p-2 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors"
                    >
                      <bank.icon className={`h-4 w-4 ${bank.color}`} />
                      <span className="text-sm">{bank.name}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* File Formats */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
          >
            <Card className="h-full border-0 shadow-lg">
              <CardContent className="p-6">
                <div className="flex items-center gap-2 mb-4">
                  <FileText className="h-5 w-5 text-primary" />
                  <h3 className="font-semibold">File Formats</h3>
                </div>
                <div className="space-y-3">
                  {formats.map((format) => (
                    <div
                      key={format.name}
                      className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50"
                    >
                      <format.icon className={`h-5 w-5 ${format.color}`} />
                      <span className="font-medium">{format.name}</span>
                      <span className="text-xs text-muted-foreground ml-auto">
                        ✓ Supported
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Features */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3 }}
          >
            <Card className="h-full border-0 shadow-lg">
              <CardContent className="p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Zap className="h-5 w-5 text-primary" />
                  <h3 className="font-semibold">Analysis Features</h3>
                </div>
                <div className="space-y-2">
                  {features.map((feature) => (
                    <div key={feature} className="flex items-center gap-2 text-sm">
                      <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                      <span>{feature}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
