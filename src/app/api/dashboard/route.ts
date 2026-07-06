import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET() {
  try {
    const [totalBusinesses, totalLeads, totalClaims, totalWebsites] =
      await Promise.all([
        prisma.business.count(),
        prisma.lead.count(),
        prisma.claim.count(),
        prisma.website.count(),
      ]);

    const recentLeads = await prisma.lead.findMany({
      include: { business: { select: { name: true } } },
      orderBy: { createdAt: "desc" },
      take: 10,
    });

    const claimRate =
      totalBusinesses > 0
        ? ((totalClaims / totalBusinesses) * 100).toFixed(1)
        : "0.0";

    return NextResponse.json({
      stats: {
        totalBusinesses,
        totalLeads,
        totalClaims,
        totalWebsites,
        claimRate: `${claimRate}%`,
      },
      recentLeads,
    });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to fetch dashboard data" },
      { status: 500 }
    );
  }
}
