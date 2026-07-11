"use client";

import { AboutUsSection } from "@/components/AboutUsSection";
import { ContactSection } from "@/components/ContactSection";
import { FeaturesSection } from "@/components/FeaturesSection";
import { Footer } from "@/components/Footer";
import { HeroSection } from "@/components/HeroSection";
import { HowItWorksSection } from "@/components/HowItWorksSection";
import { Navigation } from "@/components/Navigation";
import { SupportedStatementsSection } from "@/components/SupportedStatementsSection";
import { TestimonialsSection } from "@/components/TestimonialsSection";
import { motion } from "framer-motion";
import dynamic from "next/dynamic";
import { useState } from "react";

// ✅ Dynamically import Dashboard to avoid SSR issues with charts
const Dashboard = dynamic(
  () => import("@/components/Dashboard").then((mod) => mod.Dashboard),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    ),
  },
);

// ✅ Dynamically import UploadZone to avoid issues with Dexie
const UploadZone = dynamic(
  () => import("@/components/UploadZone").then((mod) => mod.UploadZone),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
          <p className="mt-2 text-sm text-muted-foreground">
            Loading uploader...
          </p>
        </div>
      </div>
    ),
  },
);

export default function Home() {
  const [analysisId, setAnalysisId] = useState<string | null>(null);

  const handleUploadComplete = (id: string) => {
    setAnalysisId(id);
    // Scroll to the dashboard
    setTimeout(() => {
      const dashboard = document.getElementById("dashboard-section");
      if (dashboard) {
        dashboard.scrollIntoView({ behavior: "smooth" });
      }
    }, 100);
  };

  const handleBackToUpload = () => {
    setAnalysisId(null);
  };

  return (
    <main className="min-h-screen bg-background pt-16">
      <Navigation />

      {!analysisId ? (
        <div className="space-y-0">
          {/* Hero Section */}
          <HeroSection />

          {/* Features Section */}
          <div id="features">
            <FeaturesSection />
          </div>

          {/* How It Works Section */}
          <div id="how-it-works">
            <HowItWorksSection />
          </div>

          {/* About Us Section */}
          <div id="about">
            <AboutUsSection />
          </div>

          {/* Testimonials Section */}
          <div id="reviews">
            <TestimonialsSection />
          </div>

          {/* Supported Statements Section */}
          <SupportedStatementsSection />

          {/* Upload Section */}
          <section className="py-20 gradient-bg" id="upload">
            <div className="container">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="text-center mb-8"
              >
                <h2 className="text-3xl md:text-4xl font-bold font-playfair mb-4">
                  Ready to <span className="gradient-text">Analyze</span> Your
                  Finances?
                </h2>
                <p className="text-muted-foreground max-w-2xl mx-auto">
                  Upload your statement now and get instant insights
                </p>
              </motion.div>

              <UploadZone
                mode="analysis"
                onUploadComplete={handleUploadComplete}
                title="Upload Your Statement"
                description="Drag & drop or click to select your M-PESA PDF, CSV, or Excel file"
                showHistory={false}
              />
            </div>
          </section>

          {/* Contact Section */}
          <div id="contact">
            <ContactSection />
          </div>
        </div>
      ) : (
        <div className="container py-8" id="dashboard-section">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold font-playfair">
              Analysis Results
            </h2>
            <button
              onClick={handleBackToUpload}
              className="text-sm text-primary hover:underline flex items-center gap-1"
            >
              ← Upload Another Statement
            </button>
          </div>
          <Dashboard analysisId={analysisId} />
        </div>
      )}

      <Footer />
    </main>
  );
}
