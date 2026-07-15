// ─── Campaign Template Seed Data ───────────────────────────────────────────
// Run with: npx tsx prisma/seed.ts
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

const templates = [
  // Plumber
  { name: "Seasonal Pipe Inspection", category: "Plumber", type: "EMAIL" as const, subject: "Protect Your Pipes This Season", body: "Hi {{name}}, don't wait for a burst pipe! Schedule your seasonal inspection with {{business}} today. Limited slots available.", defaultMessage: "Offer a free or discounted seasonal pipe inspection to prevent winter/summer emergencies." },
  { name: "Water Heater Check", category: "Plumber", type: "EMAIL" as const, subject: "Is Your Water Heater Ready?", body: "Hi {{name}}, your water heater works hard year-round. Let {{business}} give it a quick check. Call us today!", defaultMessage: "Remind customers about water heater maintenance before the busy season hits." },
  { name: "Drain Cleaning Reminder", category: "Plumber", type: "SMS" as const, subject: null, body: "Hi {{name}}, {{business}} here! Time for a drain cleaning. Book now and save 10%. Reply to schedule.", defaultMessage: "Send a timely reminder about drain cleaning services." },
  // Dentist
  { name: "New Patient Special", category: "Dentist", type: "EMAIL" as const, subject: "Welcome! Your First Visit at {{business}}", body: "Hi {{name}}, welcome to {{business}}! Enjoy a free consultation and exam on your first visit. Schedule today!", defaultMessage: "Attract new patients with a special introductory offer." },
  { name: "Dental Checkup Reminder", category: "Dentist", type: "SMS" as const, subject: null, body: "Hi {{name}}, it's been 6 months! Time for your checkup at {{business}}. Reply to book or call us.", defaultMessage: "Remind existing patients about their semi-annual checkup." },
  { name: "Teeth Whitening Offer", category: "Dentist", type: "EMAIL" as const, subject: "Brighten Your Smile — Special Offer Inside", body: "Hi {{name}}, want a brighter smile? {{business}} is offering 20% off teeth whitening this month. Book now!", defaultMessage: "Promote cosmetic dentistry services with a limited-time offer." },
  // Landscaper
  { name: "Spring Cleanup", category: "Landscaper", type: "EMAIL" as const, subject: "Get Your Yard Ready for Spring", body: "Hi {{name}}, spring is here! Let {{business}} handle your yard cleanup. Book your slot before they fill up.", defaultMessage: "Offer spring cleanup services to prepare yards for the growing season." },
  { name: "Lawn Care Plan", category: "Landscaper", type: "EMAIL" as const, subject: "Consistent Lawn Care — All Season Long", body: "Hi {{name}}, keep your lawn looking its best with {{business}}'s seasonal care plan. Mowing, trimming, and more.", defaultMessage: "Promote a recurring lawn maintenance subscription." },
  { name: "Fall Leaf Removal", category: "Landscaper", type: "SMS" as const, subject: null, body: "Hi {{name}}, leaves piling up? {{business}} offers fast fall cleanup. Book now and save 15%!", defaultMessage: "Send a seasonal reminder about leaf removal services." },
  // Electrician
  { name: "Electrical Safety Check", category: "Electrician", type: "EMAIL" as const, subject: "Is Your Home Electrically Safe?", body: "Hi {{name}}, old wiring can be dangerous. Let {{business}} do a safety inspection. Peace of mind guaranteed.", defaultMessage: "Offer an electrical safety inspection to prevent hazards." },
  { name: "Smart Home Upgrade", category: "Electrician", type: "EMAIL" as const, subject: "Upgrade to a Smart Home", body: "Hi {{name}}, ready for a smarter home? {{business}} installs smart switches, thermostats, and more. Ask about our package deals!", defaultMessage: "Promote smart home installation services." },
  { name: "Review Request", category: "Electrician", type: "REVIEW_REQUEST" as const, subject: "Love Our Service? Leave a Review!", body: "Hi {{name}}, we hope you loved {{business}}'s service! A quick Google review helps us serve you better.", defaultMessage: "Request a review after a completed service." },
  // Restaurant
  { name: "Weekend Special", category: "Restaurant", type: "SOCIAL" as const, subject: null, body: "This weekend only at {{business}}! Try our new seasonal menu. Reserve your table now!", defaultMessage: "Promote weekend specials and new menu items." },
  { name: "Catering Offer", category: "Restaurant", type: "EMAIL" as const, subject: "Let Us Cater Your Next Event", body: "Hi {{name}}, planning an event? {{business}} offers catering for all occasions. Get a free quote today!", defaultMessage: "Promote catering services for events and parties." },
  { name: "Birthday Special", category: "Restaurant", type: "SMS" as const, subject: null, body: "Happy Birthday {{name}}! Celebrate with {{business}} and enjoy a free dessert on us. Show this text!", defaultMessage: "Send birthday offers to loyalty program members." },
  // General
  { name: "Follow-Up", category: "General", type: "EMAIL" as const, subject: "How Was Your Experience?", body: "Hi {{name}}, thank you for choosing {{business}}. We'd love your feedback. Reply to this email or leave a review!", defaultMessage: "Send a follow-up after service to gather feedback and reviews." },
  { name: "Seasonal Offer", category: "General", type: "EMAIL" as const, subject: "Special Seasonal Offer Inside", body: "Hi {{name}}, {{business}} has a special seasonal offer just for you. Limited time — act now!", defaultMessage: "Create a generic seasonal promotion for any business type." },
];

async function main() {
  console.log("Seeding campaign templates...");
  for (const t of templates) {
    await prisma.campaignTemplate.upsert({
      where: { id: `seed-${t.category}-${t.name.replace(/\s+/g, "-").toLowerCase()}` },
      update: {},
      create: {
        id: `seed-${t.category}-${t.name.replace(/\s+/g, "-").toLowerCase()}`,
        ...t,
      },
    });
  }
  console.log(`Seeded ${templates.length} templates across ${[...new Set(templates.map(t => t.category))].length} categories`);
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());