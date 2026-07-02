'use client'

import { motion } from 'framer-motion'
import { Star, Quote, Verified } from 'lucide-react'
import { Card, CardContent } from './ui/card'
import { Avatar, AvatarFallback } from './ui/avatar'
import { Badge } from './ui/badge'

const testimonials = [
  {
    name: 'James Mwangi',
    role: 'SME Owner',
    content: 'Pesa Analyser transformed how I manage my business finances. The insights about PayBill transactions and customer spending patterns have been invaluable.',
    rating: 5,
    verified: true,
    initials: 'JM',
  },
  {
    name: 'Sarah Akinyi',
    role: 'Freelancer',
    content: 'I never knew I was spending so much on subscriptions! The AI categorization opened my eyes, and I\'ve already saved over KES 5,000 per month.',
    rating: 5,
    verified: true,
    initials: 'SA',
  },
  {
    name: 'David Ochieng',
    role: 'Software Engineer',
    content: 'The Fuliza and M-Shwari tracking is a lifesaver. I can finally see exactly how much I\'m paying in interest and make informed decisions.',
    rating: 4,
    verified: true,
    initials: 'DO',
  },
  {
    name: 'Grace Wanjiru',
    role: 'Accountant',
    content: 'This tool has made tax preparation so much easier. The KRA-compliant reports save me hours of manual work. Highly recommended!',
    rating: 5,
    verified: true,
    initials: 'GW',
  },
]

export function TestimonialsSection() {
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
            What Our <span className="gradient-text">Users Say</span>
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Join thousands of satisfied users who have transformed their financial lives
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {testimonials.map((testimonial, index) => (
            <motion.div
              key={testimonial.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1 }}
            >
              <Card className="h-full border-0 shadow-lg card-hover">
                <CardContent className="p-6">
                  <Quote className="h-6 w-6 text-primary/30 mb-3" />
                  <p className="text-sm text-muted-foreground mb-4 line-clamp-4">
                    &quot;{testimonial.content}&quot;
                  </p>
                  <div className="flex items-center gap-2 mb-2">
                    {[...Array(5)].map((_, i) => (
                      <Star
                        key={i}
                        className={`h-4 w-4 ${i < testimonial.rating ? 'fill-yellow-400 text-yellow-400' : 'text-gray-300'}`}
                      />
                    ))}
                  </div>
                  <div className="flex items-center gap-3">
                    <Avatar className="h-10 w-10">
                      <AvatarFallback className="bg-primary/10 text-primary font-semibold">
                        {testimonial.initials}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <div className="flex items-center gap-1">
                        <span className="font-semibold text-sm">{testimonial.name}</span>
                        {testimonial.verified && (
                          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200 text-[10px]">
                            <Verified className="h-3 w-3 mr-0.5" />
                            Verified
                          </Badge>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">{testimonial.role}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
