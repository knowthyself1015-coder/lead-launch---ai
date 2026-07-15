// ─── Verification Code Types ───────────────────────────────────────────────
// In-memory store for verification codes (expires in 15 minutes).
// A production system would use a DB table or Redis.

interface VerificationEntry {
  code: string;
  email: string;
  businessSlug: string;
  expiresAt: number; // timestamp ms
  attempts: number;
}

const store = new Map<string, VerificationEntry>();

// Clean up expired entries every 5 minutes
if (typeof setInterval !== "undefined") {
  setInterval(() => {
    const now = Date.now();
    for (const [key, entry] of store.entries()) {
      if (entry.expiresAt < now) store.delete(key);
    }
  }, 5 * 60 * 1000);
}

/**
 * Generate a random 6-digit verification code.
 */
export function generateCode(): string {
  return String(Math.floor(100000 + Math.random() * 900000));
}

/**
 * Store a verification code for a business claim.
 * Key is `${businessSlug}:${email}`.
 */
export function storeVerificationCode(
  businessSlug: string,
  email: string,
  code: string
): void {
  const key = `${businessSlug}:${email}`;
  store.set(key, {
    code,
    email,
    businessSlug,
    expiresAt: Date.now() + 15 * 60 * 1000, // 15 minutes
    attempts: 0,
  });
}

/**
 * Verify a code for a business claim.
 * Returns { valid: boolean; reason?: string }.
 */
export function verifyCode(
  businessSlug: string,
  email: string,
  code: string
): { valid: boolean; reason?: string } {
  const key = `${businessSlug}:${email}`;
  const entry = store.get(key);

  if (!entry) {
    return { valid: false, reason: "No verification code found. Request a new one." };
  }

  if (Date.now() > entry.expiresAt) {
    store.delete(key);
    return { valid: false, reason: "Verification code expired. Request a new one." };
  }

  entry.attempts++;

  if (entry.attempts > 5) {
    store.delete(key);
    return { valid: false, reason: "Too many failed attempts. Request a new code." };
  }

  if (entry.code !== code) {
    return { valid: false, reason: "Invalid verification code." };
  }

  // Success — clean up
  store.delete(key);
  return { valid: true };
}

/**
 * Send a verification code via email (or mock it).
 * In production, this would use Resend. For now, logs to console.
 */
export async function sendVerificationCode(
  email: string,
  code: string,
  businessName: string
): Promise<void> {
  const fromResend = process.env.RESEND_API_KEY;

  console.log(`[Claim] Verification code for ${email} (${businessName}): ${code}`);

  if (fromResend) {
    try {
      const { Resend } = await import("resend");
      const resend = new Resend(fromResend);
      await resend.emails.send({
        from: "LeadLaunch AI <noreply@leadlaunch.ai>",
        to: email,
        subject: `Verify your business: ${businessName}`,
        html: `
          <h2>Claim Your Business on LeadLaunch AI</h2>
          <p>You're verifying ownership of <strong>${businessName}</strong>.</p>
          <p style="font-size: 24px; font-weight: bold; letter-spacing: 4px; text-align: center; padding: 16px; background: #f5f5f5; border-radius: 8px;">
            ${code}
          </p>
          <p>This code expires in 15 minutes.</p>
          <p>If you didn't request this, you can ignore this email.</p>
        `,
      });
      console.log(`[Claim] Email sent to ${email} via Resend`);
    } catch (error) {
      console.error(`[Claim] Failed to send email via Resend:`, error);
    }
  }
}