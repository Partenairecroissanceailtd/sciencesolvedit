import { z, defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';

const reviews = defineCollection({
  loader: glob({
    pattern: 'reviews/**/*.md',
    base: 'src/content/',
  }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    category: z.string(),
    price: z.number(),
    rating: z.number().min(1).max(5),
    pros: z.array(z.string()).optional(),
    cons: z.array(z.string()).optional(),
    affiliateUrl: z.string().optional(),
    brand: z.string().optional(),
    publishedDate: z.date().optional(),
    featured: z.boolean().optional().default(false),
    image: z.string().optional(),
    specs: z.record(z.string(), z.string()).optional(),
    faq: z.array(z.object({
      q: z.string(),
      a: z.string(),
    })).optional(),
  }),
});

const guides = defineCollection({
  loader: glob({
    pattern: 'guides/**/*.md',
    base: 'src/content/',
  }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    category: z.string(),
    products: z.number().optional(),
    priceRange: z.string().optional(),
    publishedDate: z.date().optional(),
    featured: z.boolean().optional().default(false),
    image: z.string().optional(),
    bestPick: z.string().optional(),
    affiliateUrl: z.string().optional(),
    faq: z.array(z.object({
      q: z.string(),
      a: z.string(),
    })).optional(),
  }),
});

const comparisons = defineCollection({
  loader: glob({
    pattern: 'comparisons/**/*.md',
    base: 'src/content/',
  }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    category: z.string(),
    products: z.array(z.union([
      z.string(),
      z.object({
        name: z.string(),
        price: z.number().optional(),
        score: z.number().optional(),
        url: z.string().optional(),
        emoji: z.string().optional(),
      })
    ])).optional(),
    winner: z.string().optional(),
    publishedDate: z.date().optional(),
    featured: z.boolean().optional().default(false),
    image: z.string().optional(),
  }),
});

export const collections = { reviews, guides, comparisons };
