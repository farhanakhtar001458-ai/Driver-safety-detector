# SafeWay AI frontend image (multi-stage).
#
# Build stage compiles the Next.js app; the runtime stage serves it with
# `next start`. API_PROXY_URL is baked in at build time because Next.js
# rewrites are resolved at build time for this setup - rebuild the image when
# the backend host changes, or front it with nginx instead (recommended).

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG API_PROXY_URL=http://backend:8000
ENV API_PROXY_URL=$API_PROXY_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

RUN addgroup -S nextjs && adduser -S nextjs -G nextjs

COPY --from=build /app/public ./public
COPY --from=build --chown=nextjs:nextjs /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/next.config.mjs ./next.config.mjs

USER nextjs
EXPOSE 3000
CMD ["npm", "run", "start"]
