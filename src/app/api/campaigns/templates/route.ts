import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const category = searchParams.get("category");
    const where = category ? { category } : {};
    const templates = await prisma.campaignTemplate.findMany({
      where,
      orderBy: { createdAt: "desc" },
    });
    return NextResponse.json({ templates });
  } catch (error) {
    return NextResponse.json({ error: "Failed to fetch templates" }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { name, category, type, subject, body: bodyText, defaultMessage } = body;
    if (!name || !category || !type) {
      return NextResponse.json({ error: "name, category, and type are required" }, { status: 400 });
    }
    const template = await prisma.campaignTemplate.create({
      data: { name, category, type, subject, body: bodyText, defaultMessage },
    });
    return NextResponse.json({ template }, { status: 201 });
  } catch (error) {
    return NextResponse.json({ error: "Failed to create template" }, { status: 500 });
  }
}