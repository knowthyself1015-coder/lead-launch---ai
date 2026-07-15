import express from 'express';
import cors from 'cors';
import writerRoutes from './routes/writer';
import productRoutes from './routes/products';

const app = express();
const PORT = process.env.PORT || 4000;

app.use(cors());
app.use(express.json());

// Health check
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// ── AI Writer ──
app.use('/api/writer', writerRoutes);

// ── Product Import ──
app.use('/api/products', productRoutes);

app.listen(PORT, () => {
  console.log(`API server running on http://localhost:${PORT}`);
  console.log(`  POST /api/writer/generate`);
  console.log(`  POST /api/products/import`);
  console.log(`  GET  /api/products`);
});

export default app;
