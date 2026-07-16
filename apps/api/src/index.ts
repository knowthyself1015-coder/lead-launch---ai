import express from 'express';
import cors from 'cors';
import writerRoutes from './routes/writer';
import productRoutes from './routes/products';
import subscriptionRoutes from './routes/subscriptions';
import { generationLimitMiddleware } from './middleware/rateLimit';
import { handleStripeWebhook } from './routes/webhooks';

const app = express();
const PORT = process.env.PORT || 4000;

// ── Stripe webhook MUST receive raw body BEFORE json middleware ──
// Route it under /api/subscriptions/webhook per spec
app.post('/api/subscriptions/webhook', express.raw({ type: 'application/json' }), handleStripeWebhook);

// ── Standard middleware (after webhook raw handler) ──
app.use(cors());
app.use(express.json());

// Health check
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// ── AI Writer ──
app.use('/api/writer', generationLimitMiddleware, writerRoutes);

// ── Product Import ──
app.use('/api/products', productRoutes);

// ── Subscriptions ──
app.use('/api/subscriptions', subscriptionRoutes);

app.listen(PORT, () => {
  console.log(`API server running on http://localhost:${PORT}`);
  console.log(`  POST /api/writer/generate`);
  console.log(`  POST /api/products/import`);
  console.log(`  GET  /api/products`);
  console.log(`  POST /api/subscriptions/create-checkout`);
  console.log(`  POST /api/subscriptions/portal`);
  console.log(`  GET  /api/subscriptions/status`);
  console.log(`  POST /api/subscriptions/webhook`);
});

export default app;
