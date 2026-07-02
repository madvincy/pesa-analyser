"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  ChevronDown,
  ChevronUp,
  HelpCircle,
  MessageCircle,
  Search,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { Input } from "./ui/input";
interface FAQ {
  id: string;
  category: string;
  question: string;
  answer: string;
}

const faqs: FAQ[] = [
  {
    id: "1",
    category: "Getting Started",
    question: "What is Pesa Analyser?",
    answer:
      "Pesa Analyser is an AI-powered financial analysis tool that helps you understand your spending patterns, income trends, and overall financial health by analyzing your M-PESA and bank statements.",
  },
  {
    id: "2",
    category: "Getting Started",
    question: "How do I upload my statement?",
    answer:
      'Simply click on the upload zone on our homepage, select your PDF, CSV, or Excel file, and click "Upload & Analyze". If your PDF is password protected, you\'ll be prompted to enter the password.',
  },
  {
    id: "3",
    category: "Security & Privacy",
    question: "Is my financial data secure?",
    answer:
      "Absolutely! We use bank-grade encryption (AES-256) for all data in transit and at rest. We never store your raw transaction data - only anonymized insights. Your data is processed in memory and deleted after analysis unless you choose to save it.",
  },
  {
    id: "4",
    category: "Security & Privacy",
    question: "Do you store my personal information?",
    answer:
      "We only store anonymized data for analytics purposes. We never store your full name, phone number, account numbers, or transaction descriptions. All PII (Personally Identifiable Information) is redacted and tokenized.",
  },
  {
    id: "5",
    category: "Pricing",
    question: "How much does it cost?",
    answer:
      "We offer a freemium model. Basic analysis with summary charts is FREE. Detailed analysis with 20+ financial insights costs KES 50-150 per analysis. Premium credit-ready reports with PDF export cost KES 500.",
  },
  {
    id: "6",
    category: "Pricing",
    question: "How do I pay?",
    answer:
      "We accept payments via M-PESA STK Push. After analysis, you'll receive a payment prompt on your phone. You can also pay via card or bank transfer for business accounts.",
  },
  {
    id: "7",
    category: "Technical",
    question: "What file formats are supported?",
    answer:
      "We support PDF, CSV, XLS, and XLSX files from all major banks in Kenya (KCB, Equity, Cooperative, Stanbic, ABSA) and M-PESA statements. Maximum file size is 50MB.",
  },
  {
    id: "8",
    category: "Technical",
    question: "How long does analysis take?",
    answer:
      "Analysis typically takes 30-60 seconds for most statements. For very large files (5+ years of transactions), it may take up to 2-3 minutes. You'll receive a notification when your analysis is ready.",
  },
  {
    id: "9",
    category: "Features",
    question: "What insights do I get?",
    answer:
      "You get 20+ financial insights including: Total Income vs Expenses, Average Daily Balance, Net Cash Flow, Transaction Fees, PayBill & Till breakdown, Fuliza & M-Shwari usage, P2P transfers, Category spending, Subscription detection, and much more.",
  },
  {
    id: "10",
    category: "Features",
    question: "Can I download my report?",
    answer:
      "Yes! Premium users can download comprehensive PDF reports with charts, insights, and recommendations. Basic users can download CSV exports of their transaction data.",
  },
  {
    id: "11",
    category: "Business",
    question: "Do you offer business plans?",
    answer:
      "Yes! We have SME and Enterprise plans that include multi-user access, API integration, custom reports, and dedicated support. Contact us for a custom quote based on your transaction volume.",
  },
  {
    id: "12",
    category: "Business",
    question: "Can I use Pesa Analyser for tax compliance?",
    answer:
      "Absolutely! Our premium reports are designed to be KRA-compliant and can be used for tax filing, loan applications, and audit purposes. We provide verified income consistency and debt-to-income summaries.",
  },
];

const categories = [
  "All",
  "Getting Started",
  "Security & Privacy",
  "Pricing",
  "Technical",
  "Features",
  "Business",
];

export function FAQSection() {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [openItems, setOpenItems] = useState<Set<string>>(new Set());

  const filteredFAQs = faqs.filter((faq) => {
    const matchesSearch =
      faq.question.toLowerCase().includes(searchTerm.toLowerCase()) ||
      faq.answer.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory =
      selectedCategory === "All" || faq.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const toggleItem = (id: string) => {
    const newOpenItems = new Set(openItems);
    if (newOpenItems.has(id)) {
      newOpenItems.delete(id);
    } else {
      newOpenItems.add(id);
    }
    setOpenItems(newOpenItems);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="text-center space-y-4">
        <div className="flex justify-center">
          <div className="p-3 rounded-full bg-primary/10">
            <HelpCircle className="h-10 w-10 text-primary" />
          </div>
        </div>
        <h1 className="text-4xl font-bold tracking-tight font-playfair">
          Frequently Asked Questions
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Find answers to common questions about Pesa Analyser
        </p>
      </div>

      {/* Search & Filter */}
      <div className="flex flex-col sm:flex-row gap-4 max-w-3xl mx-auto">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search FAQs..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        <div className="flex flex-wrap gap-2 justify-center">
          {categories.map((category) => (
            <Button
              key={category}
              variant={selectedCategory === category ? "default" : "outline"}
              size="sm"
              onClick={() => setSelectedCategory(category)}
              className="whitespace-nowrap"
            >
              {category}
            </Button>
          ))}
        </div>
      </div>

      {/* FAQ List */}
      <div className="max-w-3xl mx-auto space-y-4">
        <AnimatePresence>
          {filteredFAQs.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <Card>
                <CardContent className="py-12 text-center">
                  <Search className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                  <p className="text-muted-foreground">
                    No FAQs found matching your criteria
                  </p>
                  <Button
                    variant="outline"
                    className="mt-4"
                    onClick={() => {
                      setSearchTerm("");
                      setSelectedCategory("All");
                    }}
                  >
                    Clear Filters
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          ) : (
            filteredFAQs.map((faq, index) => (
              <motion.div
                key={faq.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <Card className="overflow-hidden hover:shadow-md transition-shadow">
                  <button
                    onClick={() => toggleItem(faq.id)}
                    className="w-full text-left p-4 hover:bg-muted/50 transition-colors flex justify-between items-start group"
                  >
                    <div className="flex-1">
                      <span className="text-xs text-primary font-medium uppercase">
                        {faq.category}
                      </span>
                      <h3 className="font-semibold mt-1 group-hover:text-primary transition-colors">
                        {faq.question}
                      </h3>
                    </div>
                    <div className="ml-4 mt-1 flex-shrink-0">
                      {openItems.has(faq.id) ? (
                        <ChevronUp className="h-5 w-5 text-primary" />
                      ) : (
                        <ChevronDown className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
                      )}
                    </div>
                  </button>
                  <AnimatePresence>
                    {openItems.has(faq.id) && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.3 }}
                      >
                        <div className="px-4 pb-4">
                          <div className="border-t pt-4 text-muted-foreground">
                            {faq.answer}
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </Card>
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>

      {/* Still Have Questions - Contact CTA */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="max-w-3xl mx-auto"
      >
        <Card className="bg-gradient-to-r from-primary/5 via-secondary/10 to-primary/5 border-primary/20">
          <CardContent className="py-8 text-center">
            <div className="flex justify-center mb-4">
              <div className="p-3 rounded-full bg-primary/10">
                <MessageCircle className="h-8 w-8 text-primary" />
              </div>
            </div>
            <h3 className="font-semibold text-xl font-playfair mb-2">
              Still have questions?
            </h3>
            <p className="text-muted-foreground max-w-md mx-auto mb-4">
              Can&apos;t find what you&apos;re looking for? Our support team is
              here to help.
            </p>
            <Link href="/#contact">
              <Button className="gap-2 group">
                Contact Support
                <ChevronDown className="h-4 w-4 group-hover:translate-x-1 transition-transform rotate-[-90deg]" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
