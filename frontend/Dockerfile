FROM node:22-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy source
COPY . .

# Next.js dev server
EXPOSE 3000
CMD ["npm", "run", "dev"]
