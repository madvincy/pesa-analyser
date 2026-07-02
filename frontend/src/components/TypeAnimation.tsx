'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'

const phrases = [
  '📊 Analyze your spending',
  '💰 Track your income',
  '📈 Get AI-powered insights',
  '💳 Understand your M-PESA',
  '🏦 Manage your finances',
]

export function TypeAnimation() {
  const [currentPhrase, setCurrentPhrase] = useState(0)
  const [displayText, setDisplayText] = useState('')
  const [isDeleting, setIsDeleting] = useState(false)

  useEffect(() => {
    const phrase = phrases[currentPhrase]
    const speed = isDeleting ? 50 : 100

    const timeout = setTimeout(() => {
      if (!isDeleting) {
        setDisplayText(phrase.slice(0, displayText.length + 1))
        if (displayText.length === phrase.length) {
          setTimeout(() => setIsDeleting(true), 2000)
        }
      } else {
        setDisplayText(phrase.slice(0, displayText.length - 1))
        if (displayText.length === 0) {
          setIsDeleting(false)
          setCurrentPhrase((prev) => (prev + 1) % phrases.length)
        }
      }
    }, speed)

    return () => clearTimeout(timeout)
  }, [displayText, currentPhrase, isDeleting])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="text-lg text-primary font-medium"
    >
      {displayText}
      <span className="animate-pulse">|</span>
    </motion.div>
  )
}
