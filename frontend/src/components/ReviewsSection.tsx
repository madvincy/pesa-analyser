"use client";

import { Star, StarHalf, ThumbsUp, Verified } from "lucide-react";
import { useState } from "react";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { Progress } from "./ui/progress";
interface Review {
  id: string;
  name: string;
  rating: number;
  date: string;
  title: string;
  content: string;
  verified?: boolean;
  helpful?: number;
  category?: string;
  plan?: string;
}

const reviews: Review[] = [
  {
    id: "1",
    name: "James Mwangi",
    rating: 5,
    date: "2024-12-15",
    title: "Game-changer for my business finances",
    content:
      "I've been using Pesa Analyser for my SME for 3 months now. The insights are incredible!",
    verified: true,
    helpful: 45,
    category: "Business",
    plan: "Business",
  },
  {
    id: "2",
    name: "Sarah Akinyi",
    rating: 5,
    date: "2024-12-10",
    title: "Finally understand my spending habits",
    content:
      "I never realized how much I was spending on subscriptions until I used Pesa Analyser.",
    verified: true,
    helpful: 38,
    category: "Personal Finance",
    plan: "Basic",
  },
];

export function ReviewsSection() {
  const [filter] = useState("All");

  const renderStars = (rating: number) => {
    const fullStars = Math.floor(rating);
    const hasHalfStar = rating % 1 !== 0;

    return (
      <div className="flex items-center gap-0.5">
        {[...Array(fullStars)].map((_, i) => (
          <Star
            key={`full-${i}`}
            className="h-4 w-4 fill-yellow-400 text-yellow-400"
          />
        ))}
        {hasHalfStar && (
          <StarHalf className="h-4 w-4 fill-yellow-400 text-yellow-400" />
        )}
        {[...Array(5 - fullStars - (hasHalfStar ? 1 : 0))].map((_, i) => (
          <Star key={`empty-${i}`} className="h-4 w-4 text-gray-300" />
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-8">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold tracking-tight">Customer Reviews</h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          See what our users are saying about Pesa Analyser
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-4xl font-bold">4.8</div>
            <div className="flex justify-center mt-2">{renderStars(4.8)}</div>
            <p className="text-sm text-muted-foreground mt-2">
              Based on 127 reviews
            </p>
          </CardContent>
        </Card>
        <Card className="md:col-span-2">
          <CardContent className="pt-6">
            {[5, 4, 3, 2, 1].map((stars) => (
              <div key={stars} className="flex items-center gap-3">
                <span className="text-sm w-12">{stars} Stars</span>
                <Progress
                  value={stars === 5 ? 80 : stars === 4 ? 15 : 5}
                  className="h-2 flex-1"
                />
                <span className="text-sm text-muted-foreground w-12 text-right">
                  {stars === 5 ? 102 : stars === 4 ? 19 : 6}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="flex items-center justify-center gap-4">
              <div>
                <div className="text-2xl font-bold">98%</div>
                <div className="text-xs text-muted-foreground">
                  Would Recommend
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        {reviews.map((review) => (
          <Card key={review.id}>
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <Avatar className="h-10 w-10">
                  <AvatarFallback>
                    {review.name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{review.name}</span>
                    {review.verified && (
                      <Badge
                        variant="outline"
                        className="bg-green-50 text-green-700 border-green-200"
                      >
                        <Verified className="h-3 w-3 mr-1" />
                        Verified
                      </Badge>
                    )}
                    <Badge variant="secondary" className="text-xs">
                      {review.plan}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    {renderStars(review.rating)}
                    <span className="text-sm text-muted-foreground">
                      {new Date(review.date).toLocaleDateString("en-KE", {
                        year: "numeric",
                        month: "long",
                        day: "numeric",
                      })}
                    </span>
                  </div>
                  <h4 className="font-medium mt-2">{review.title}</h4>
                  <p className="text-muted-foreground mt-1">{review.content}</p>
                  <div className="flex items-center gap-4 mt-3">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-muted-foreground"
                    >
                      <ThumbsUp className="h-4 w-4 mr-1" />
                      {review.helpful}
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="bg-primary/5 border-primary/20">
        <CardContent className="py-8 text-center">
          <h3 className="font-semibold text-lg">Share Your Experience</h3>
          <p className="text-muted-foreground mt-2">
            Help others make informed decisions by sharing your experience with
            Pesa Analyser
          </p>
          <Button className="mt-4">Write a Review</Button>
        </CardContent>
      </Card>
    </div>
  );
}
