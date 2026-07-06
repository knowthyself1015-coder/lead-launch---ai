import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET() {
  try {
    const leads = await prisma.lead.findMany({
      include: { business: { select: { name: true, slug: true } } },
      orderBy: { createdAt: "desc" },
      take: 100,
    });
    return NextResponse.json({ leads });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to fetch leads" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const lead = await prisma.lead.create({
      data: {
        businessId: body.businessId,
        customerName: body.customerName,
        email: body.email,
        phone: body.phone,
        message: body.message,
        serviceType: body.serviceType,
      },
    });
    return NextResponse.json({ lead }, { status: 201 });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to create lead" },
      { status: 500 }
    );
  }
}
