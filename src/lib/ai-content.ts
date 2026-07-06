/**
 * AI Content Generation Pipeline
 *
 * Generates website content for local businesses using OpenAI.
 * Falls back to template-based content when OPENAI_API_KEY is not set.
 */

interface BusinessData {
  name: string;
  category?: string | null;
  city?: string | null;
  state?: string | null;
  description?: string | null;
  phone?: string | null;
  email?: string | null;
  hours?: Record<string, string> | null;
}

interface GeneratedContent {
  heroHeadline: string;
  heroSubheadline: string;
  about: string;
  services: { title: string; description: string }[];
  faq: { question: string; answer: string }[];
  seoTitle: string;
  seoDescription: string;
}

/**
 * Generates business website content using OpenAI.
 * Falls back to template-based content if API key is missing.
 */
export async function generateBusinessContent(
  business: BusinessData
): Promise<GeneratedContent> {
  if (process.env.OPENAI_API_KEY) {
    try {
      return await generateWithAI(business);
    } catch (error) {
      console.error("AI content generation failed, using fallback:", error);
      return generateFallbackContent(business);
    }
  }
  return generateFallbackContent(business);
}

async function generateWithAI(business: BusinessData): Promise<GeneratedContent> {
  const prompt = `Generate website content for a local business. Return valid JSON only.

Business: ${business.name}
Category: ${business.category || "General"}
Location: ${business.city || "Local"}, ${business.state || ""}
Description: ${business.description || "Professional services"}

Generate a JSON object with these fields:
- heroHeadline: catchy headline (max 10 words)
- heroSubheadline: brief value proposition (max 20 words)
- about: 2-3 sentence description of the business
- services: array of 3-4 objects with {title, description} for their main services
- faq: array of 3 frequently asked questions with {question, answer}
- seoTitle: SEO-optimized title tag (max 60 chars)
- seoDescription: SEO meta description (max 160 chars)

Return ONLY valid JSON, no markdown or code blocks.`;

  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
    },
    body: JSON.stringify({
      model: "gpt-4o-mini",
      messages: [
        {
          role: "system",
          content:
            "You are a professional copywriter for local business websites. Generate compelling, SEO-optimized content. Return ONLY valid JSON.",
        },
        { role: "user", content: prompt },
      ],
      temperature: 0.7,
      max_tokens: 1500,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`OpenAI API error (${response.status}): ${errorText}`);
  }

  const data = await response.json();
  const contentText = data.choices[0]?.message?.content;

  if (!contentText) {
    throw new Error("No content returned from OpenAI");
  }

  // Parse the JSON response, handling potential markdown code blocks
  const jsonStr = contentText
    .replace(/```json\n?/g, "")
    .replace(/```\n?/g, "")
    .trim();

  const parsed = JSON.parse(jsonStr) as GeneratedContent;
  return parsed;
}

function generateFallbackContent(business: BusinessData): GeneratedContent {
  const city = business.city || "your area";
  const category = business.category || "professional services";

  return {
    heroHeadline: business.name,
    heroSubheadline: `Trusted ${category} serving ${city} and surrounding areas`,
    about:
      business.description ||
      `${business.name} is a trusted provider of ${category} in ${city}. We are committed to delivering exceptional service and quality results to every customer. Contact us today to learn more about how we can help with your needs.`,
    services: [
      {
        title: `Professional ${category}`,
        description: `Expert ${category} tailored to your specific needs. Our team has the experience and tools to get the job done right.`,
      },
      {
        title: "Free Consultation",
        description: `Get in touch for a free consultation. We'll discuss your needs and provide a detailed estimate with no obligation.`,
      },
      {
        title: "Customer Satisfaction",
        description: `We pride ourselves on delivering exceptional customer service. Your satisfaction is our top priority on every project.`,
      },
    ],
    faq: [
      {
        question: `What areas do you serve?`,
        answer: `We proudly serve ${city} and the surrounding communities. Contact us to see if we cover your area.`,
      },
      {
        question: "Do you offer free estimates?",
        answer: "Yes! We provide free, no-obligation estimates. Give us a call or fill out the contact form to schedule yours.",
      },
      {
        question: "How can I contact you?",
        answer: `You can reach us by phone at ${business.phone || "the number listed on our site"} or by using the contact form below. We look forward to hearing from you!`,
      },
    ],
    seoTitle: `${business.name} | ${category} in ${city}`,
    seoDescription: `${business.name} provides professional ${category} in ${city}. Contact us for a free estimate. Call ${business.phone || "today"}!`,
  };
}