/**
 * Amazon Product Advertising API integration.
 *
 * Uses the PA API v5 to fetch product data by ASIN or search by keyword.
 * Requires AMAZON_PA_API_KEY, AMAZON_PA_API_SECRET, and AMAZON_PA_ASSOCIATE_TAG
 * environment variables.
 *
 * Reference: https://webservices.amazon.com/paapi5/documentation/
 */

// ── Types ──────────────────────────────────────────────────

export interface AmazonProductData {
  asin: string;
  title: string;
  description: string;
  features: string[];
  imageUrl: string;
  imageUrls: string[];
  price: string;
  currency: string;
  category: string;
  brand: string;
  availability: string;
  url: string;
  affiliateUrl: string;
  rating?: number;
  reviewCount?: number;
}

interface AmazonError {
  code: string;
  message: string;
}

// ── Configuration ──────────────────────────────────────────

function getAmazonCredentials() {
  const accessKey = process.env.AMAZON_PA_API_KEY;
  const secretKey = process.env.AMAZON_PA_API_SECRET;
  const associateTag = process.env.AMAZON_PA_ASSOCIATE_TAG;
  const region = process.env.AMAZON_PA_REGION || "us-east-1";
  const host = process.env.AMAZON_PA_HOST || "webservices.amazon.com";

  if (!accessKey || !secretKey) {
    throw new AmazonProductError(
      "Amazon Product API credentials not configured. Set AMAZON_PA_API_KEY, AMAZON_PA_API_SECRET, and AMAZON_PA_ASSOCIATE_TAG.",
      "CREDENTIALS_MISSING",
      500,
    );
  }

  return { accessKey, secretKey, associateTag, region, host };
}

// ── Error handling ─────────────────────────────────────────

export class AmazonProductError extends Error {
  constructor(
    message: string,
    public code: string,
    public statusCode: number = 500,
  ) {
    super(message);
    this.name = "AmazonProductError";
  }
}

// ── Extract ASIN from URL ──────────────────────────────────

export function extractAsin(input: string): string | null {
  // Already a clean ASIN (10 alphanumeric chars)
  const cleanAsin = input.trim().toUpperCase();
  if (/^[A-Z0-9]{10}$/.test(cleanAsin)) {
    return cleanAsin;
  }

  // Extract from Amazon URL patterns
  const patterns = [
    /\/dp\/([A-Z0-9]{10})/,
    /\/product\/([A-Z0-9]{10})/,
    /\/gp\/product\/([A-Z0-9]{10})/,
    /\/exec\/obidos\/ASIN\/([A-Z0-9]{10})/,
    /asin=([A-Z0-9]{10})/i,
    /\/o\/([A-Z0-9]{10})/,
  ];

  for (const pattern of patterns) {
    const match = input.match(pattern);
    if (match) return match[1];
  }

  return null;
}

// ── Affiliate URL builder ──────────────────────────────────

export function buildAffiliateUrl(
  asin: string,
  associateTag?: string,
): string {
  const tag = associateTag || process.env.AMAZON_PA_ASSOCIATE_TAG || "affiliatecontent-20";
  return `https://www.amazon.com/dp/${asin}?tag=${tag}`;
}

// ── AWS Signature V4 (for PA API) ──────────────────────────

async function sha256(message: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(message);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function hmacSha256(key: ArrayBuffer | Uint8Array, message: string): Promise<ArrayBuffer> {
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    key instanceof Uint8Array ? key : new Uint8Array(key),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const encoder = new TextEncoder();
  return crypto.subtle.sign("HMAC", cryptoKey, encoder.encode(message));
}

async function getSignatureKey(
  secretKey: string,
  date: string,
  region: string,
  service: string,
): Promise<ArrayBuffer> {
  const encoder = new TextEncoder();
  const kDate = await hmacSha256(encoder.encode(`AWS4${secretKey}`), date);
  const kRegion = await hmacSha256(new Uint8Array(kDate), region);
  const kService = await hmacSha256(new Uint8Array(kRegion), service);
  return hmacSha256(new Uint8Array(kService), "aws4_request");
}

// ── API Call ───────────────────────────────────────────────

async function callAmazonPAAPI(
  operation: "GetItems" | "SearchItems",
  params: Record<string, any>,
): Promise<any> {
  const { accessKey, secretKey, associateTag, region, host } = getAmazonCredentials();

  const service = "ProductAdvertisingAPI";
  const method = "POST";
  const canonicalUri = "/paapi5/" + (operation === "GetItems" ? "getitems" : "searchitems");
  const endpoint = `https://${host}${canonicalUri}`;

  const now = new Date();
  const amzDate = now.toISOString().replace(/[:-]|\.\d{3}/g, "");
  const dateStamp = amzDate.slice(0, 8);

  const payload: any = {
    ...params,
    PartnerTag: associateTag,
    PartnerType: "Associates",
    Marketplace: "www.amazon.com",
  };

  const payloadStr = JSON.stringify(payload);
  const payloadHash = await sha256(payloadStr);

  const canonicalHeaders = [
    `content-encoding:amz-1.0`,
    `host:${host}`,
    `x-amz-date:${amzDate}`,
    `x-amz-target:com.amazon.paapi5.v1.ProductAdvertisingAPIv1.${operation}`,
  ].join("\n") + "\n";

  const signedHeaders = "content-encoding;host;x-amz-date;x-amz-target";

  const canonicalRequest = [
    method,
    canonicalUri,
    "", // query string (none for POST)
    canonicalHeaders,
    signedHeaders,
    payloadHash,
  ].join("\n");

  const algorithm = "AWS4-HMAC-SHA256";
  const credentialScope = `${dateStamp}/${region}/${service}/aws4_request`;
  const stringToSign = [
    algorithm,
    amzDate,
    credentialScope,
    await sha256(canonicalRequest),
  ].join("\n");

  const signingKey = await getSignatureKey(secretKey, dateStamp, region, service);
  const signature = Array.from(new Uint8Array(await hmacSha256(new Uint8Array(signingKey), stringToSign)))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  const authorization = `${algorithm} Credential=${accessKey}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Encoding": "amz-1.0",
      "Content-Type": "application/json; charset=UTF-8",
      "Host": host,
      "X-Amz-Date": amzDate,
      "X-Amz-Target": `com.amazon.paapi5.v1.ProductAdvertisingAPIv1.${operation}`,
      "Authorization": authorization,
    },
    body: payloadStr,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    let parsed: AmazonError[] = [];
    try {
      const json = JSON.parse(errorBody);
      parsed = json.Errors || [];
    } catch {}
    throw new AmazonProductError(
      `Amazon API error (${response.status}): ${parsed.map((e) => e.message).join("; ") || errorBody}`,
      "API_ERROR",
      response.status,
    );
  }

  return response.json();
}

// ── Parse API response ─────────────────────────────────────

function parseItemResponse(raw: any): AmazonProductData | null {
  const items = raw?.ItemsResult?.Items;
  if (!items || items.length === 0) return null;

  const item = items[0];
  const detailUrl = item.DetailPageURL || `https://www.amazon.com/dp/${item.ASIN}`;

  return {
    asin: item.ASIN || "",
    title: item.ItemInfo?.Title?.DisplayValue || "Unknown Product",
    description: item.ItemInfo?.Features?.DisplayValues?.join(". ") ||
      item.ItemInfo?.Title?.DisplayValue || "",
    features: item.ItemInfo?.Features?.DisplayValues || [],
    imageUrl: item.Images?.Primary?.Large?.URL || item.Images?.Primary?.Medium?.URL || "",
    imageUrls: item.Images?.Primary?.Large?.URL
      ? [item.Images.Primary.Large.URL]
      : [],
    price: item.ItemInfo?.ListPrice?.DisplayAmount || item.Offers?.Listings?.[0]?.Price?.DisplayAmount || "",
    currency: item.ItemInfo?.ListPrice?.Currency || "USD",
    category: item.ItemInfo?.Classifications?.ProductGroup?.DisplayValue || "",
    brand: item.ItemInfo?.ByLineInfo?.Brand?.DisplayValue || "",
    availability: item.ItemInfo?.Availability?.Message || "Check on Amazon",
    url: detailUrl,
    affiliateUrl: detailUrl,
    rating: item.ItemInfo?.CustomerReviews?.StarRating?.Value,
    reviewCount: item.ItemInfo?.CustomerReviews?.Count,
  };
}

// ── Public API ─────────────────────────────────────────────

export async function getProductByAsin(
  asin: string,
  associateTag?: string,
): Promise<AmazonProductData> {
  const raw = await callAmazonPAAPI("GetItems", {
    ItemIds: [asin],
    Resources: [
      "ItemInfo.Title",
      "ItemInfo.Features",
      "ItemInfo.ListPrice",
      "ItemInfo.Classifications",
      "ItemInfo.ByLineInfo",
      "ItemInfo.CustomerReviews",
      "ItemInfo.Availability",
      "Images.Primary.Large",
      "Images.Primary.Medium",
      "Offers.Listings.Price",
    ],
  });

  const product = parseItemResponse(raw);
  if (!product) {
    throw new AmazonProductError(
      `Product not found for ASIN: ${asin}`,
      "NOT_FOUND",
      404,
    );
  }

  // Generate affiliate URL
  product.affiliateUrl = buildAffiliateUrl(product.asin, associateTag);

  return product;
}

export async function searchProducts(
  keyword: string,
  associateTag?: string,
  maxResults: number = 5,
): Promise<AmazonProductData[]> {
  const raw = await callAmazonPAAPI("SearchItems", {
    Keywords: keyword,
    ItemCount: maxResults,
    Resources: [
      "ItemInfo.Title",
      "ItemInfo.Features",
      "ItemInfo.ListPrice",
      "Images.Primary.Medium",
      "ItemInfo.ByLineInfo",
    ],
  });

  const items = raw?.SearchResult?.Items || [];
  return items
    .map((item: any) => {
      return {
        asin: item.ASIN || "",
        title: item.ItemInfo?.Title?.DisplayValue || "Unknown",
        description: item.ItemInfo?.Features?.DisplayValues?.join(". ") || "",
        features: item.ItemInfo?.Features?.DisplayValues || [],
        imageUrl: item.Images?.Primary?.Medium?.URL || "",
        imageUrls: [],
        price: item.ItemInfo?.ListPrice?.DisplayAmount || "",
        currency: "USD",
        category: "",
        brand: item.ItemInfo?.ByLineInfo?.Brand?.DisplayValue || "",
        availability: "Check on Amazon",
        url: item.DetailPageURL || `https://www.amazon.com/dp/${item.ASIN}`,
        affiliateUrl: buildAffiliateUrl(item.ASIN, associateTag),
      };
    });
}

/**
 * Smart import — tries ASIN first, then searches by name.
 * Falls back to mock data when Amazon API credentials are not configured.
 */
export async function importProduct(
  input: string,
  associateTag?: string,
): Promise<AmazonProductData> {
  const asin = extractAsin(input);

  // Try real API if credentials are available
  try {
    getAmazonCredentials();

    if (asin) {
      return getProductByAsin(asin, associateTag);
    }

    const results = await searchProducts(input, associateTag, 1);
    if (results.length === 0) {
      throw new AmazonProductError(
        `No products found for: "${input}"`,
        "NOT_FOUND",
        404,
      );
    }
    return results[0];
  } catch (error) {
    // If credentials are missing or API fails, use mock data
    if (error instanceof AmazonProductError && error.code === "CREDENTIALS_MISSING") {
      return getMockProduct(input, associateTag);
    }
    throw error;
  }
}

// ── Mock Data (for development without API credentials) ────

const MOCK_PRODUCTS: Record<string, AmazonProductData> = {
  B08N5WRWNW: {
    asin: "B08N5WRWNW",
    title: "Sony WH-1000XM5 Wireless Noise Canceling Headphones",
    description: "Industry-leading noise canceling with Auto NC Optimizer. Crystal clear hands-free calling with 4 beamforming microphones. 30-hour battery life with quick charging (3 min charge for 3 hours playback). Lightweight and comfortable design.",
    features: [
      "Industry-leading noise canceling with Auto NC Optimizer",
      "Crystal clear hands-free calling with 4 beamforming microphones",
      "30-hour battery life with quick charging",
      "Multipoint connection — switch between 2 devices seamlessly",
      "Lightweight design at just 250g for all-day comfort",
    ],
    imageUrl: "https://m.media-amazon.com/images/I/61bZhJ2XhZL._AC_SL1500_.jpg",
    imageUrls: ["https://m.media-amazon.com/images/I/61bZhJ2XhZL._AC_SL1500_.jpg"],
    price: "$348.00",
    currency: "USD",
    category: "Headphones",
    brand: "Sony",
    availability: "In Stock",
    url: "https://www.amazon.com/dp/B08N5WRWNW",
    affiliateUrl: "https://www.amazon.com/dp/B08N5WRWNW?tag=affiliatecontent-20",
    rating: 4.6,
    reviewCount: 12453,
  },
  B0BSHF7WHW: {
    asin: "B0BSHF7WHW",
    title: "Apple AirPods Pro (2nd Generation) with USB-C",
    description: "Rebuilt from the sound up. The Apple-designed H2 chip pushes advanced audio performance with richer bass and clearer sound. Up to 2x more Active Noise Cancellation. Adaptive Audio dynamically blends Transparency and ANC.",
    features: [
      "Apple H2 chip for richer bass and clearer sound",
      "Up to 2x more Active Noise Cancellation",
      "Adaptive Audio dynamically blends Transparency and ANC",
      "USB-C charging case with Find My and speaker",
      "Personalized Spatial Audio with dynamic head tracking",
    ],
    imageUrl: "https://m.media-amazon.com/images/I/61SUj2aKoEL._AC_SL1500_.jpg",
    imageUrls: ["https://m.media-amazon.com/images/I/61SUj2aKoEL._AC_SL1500_.jpg"],
    price: "$199.99",
    currency: "USD",
    category: "Earbuds",
    brand: "Apple",
    availability: "In Stock",
    url: "https://www.amazon.com/dp/B0BSHF7WHW",
    affiliateUrl: "https://www.amazon.com/dp/B0BSHF7WHW?tag=affiliatecontent-20",
    rating: 4.7,
    reviewCount: 28761,
  },
  B09G9D7K6N: {
    asin: "B09G9D7K6N",
    title: "Instant Pot Duo Plus 6-Quart 9-in-1 Electric Pressure Cooker",
    description: "9-in-1 programmable pressure cooker: pressure cook, slow cook, rice cooker, yogurt maker, steamer, sauté pan, food warmer, sterilizer, and sous vide. Built-in progress indicator and 25 customizable smart programs.",
    features: [
      "9-in-1 functionality replaces 9 kitchen appliances",
      "6-quart capacity — perfect for families",
      "Advanced microprocessor monitors pressure, temperature, and time",
      "Built-in progress indicator shows cooking status",
      "Dishwasher-safe inner pot and accessories",
    ],
    imageUrl: "https://m.media-amazon.com/images/I/71lOQ0-HxrL._AC_SL1500_.jpg",
    imageUrls: ["https://m.media-amazon.com/images/I/71lOQ0-HxrL._AC_SL1500_.jpg"],
    price: "$89.99",
    currency: "USD",
    category: "Kitchen Appliances",
    brand: "Instant Pot",
    availability: "In Stock",
    url: "https://www.amazon.com/dp/B09G9D7K6N",
    affiliateUrl: "https://www.amazon.com/dp/B09G9D7K6N?tag=affiliatecontent-20",
    rating: 4.8,
    reviewCount: 89234,
  },
};

function getMockProduct(input: string, associateTag?: string): AmazonProductData {
  const asin = extractAsin(input);

  // Try direct ASIN match
  if (asin && MOCK_PRODUCTS[asin]) {
    const product = { ...MOCK_PRODUCTS[asin] };
    if (associateTag) {
      product.affiliateUrl = buildAffiliateUrl(product.asin, associateTag);
    }
    return product;
  }

  // Try keyword match
  const keyword = input.toLowerCase();
  for (const mock of Object.values(MOCK_PRODUCTS)) {
    if (
      mock.title.toLowerCase().includes(keyword) ||
      mock.brand.toLowerCase().includes(keyword) ||
      mock.category.toLowerCase().includes(keyword)
    ) {
      const product = { ...mock };
      if (associateTag) {
        product.affiliateUrl = buildAffiliateUrl(product.asin, associateTag);
      }
      return product;
    }
  }

  // Generate a generic mock product
  const mockAsin = asin || `B0${Math.random().toString(36).substring(2, 11).toUpperCase()}`;
  const tag = associateTag || "affiliatecontent-20";
  return {
    asin: mockAsin,
    title: input.trim() || "Sample Product",
    description: `This is a mock product for "${input}". Connect Amazon PA API credentials to import real products.`,
    features: ["Feature 1: Sample feature for testing", "Feature 2: Another great feature", "Feature 3: High quality materials"],
    imageUrl: "https://placehold.co/600x600/e2e8f0/475569?text=Product+Image",
    imageUrls: ["https://placehold.co/600x600/e2e8f0/475569?text=Product+Image"],
    price: "$49.99",
    currency: "USD",
    category: "General",
    brand: "Sample Brand",
    availability: "In Stock",
    url: `https://www.amazon.com/dp/${mockAsin}`,
    affiliateUrl: `https://www.amazon.com/dp/${mockAsin}?tag=${tag}`,
    rating: 4.5,
    reviewCount: 1000,
  };
}

export { MOCK_PRODUCTS };
