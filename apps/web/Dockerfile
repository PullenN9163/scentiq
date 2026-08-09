FROM node:24-bookworm-slim AS dependencies

WORKDIR /workspace

RUN npm install --global pnpm@11.16.0

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile --filter @scentiq/web...

FROM dependencies AS builder

ARG NEXT_PUBLIC_APP_ENV=development
ENV NEXT_PUBLIC_APP_ENV=${NEXT_PUBLIC_APP_ENV}

COPY apps/web/app ./apps/web/app
COPY apps/web/components ./apps/web/components
COPY apps/web/lib ./apps/web/lib
COPY apps/web/instrumentation.ts ./apps/web/instrumentation.ts
COPY apps/web/next.config.ts apps/web/next-env.d.ts apps/web/tsconfig.json apps/web/vitest.setup.ts ./apps/web/

RUN mkdir -p apps/web/public \
    && pnpm --filter @scentiq/web build

FROM node:24-bookworm-slim AS runtime

ENV HOSTNAME=0.0.0.0 \
    NODE_ENV=production \
    PORT=3000

WORKDIR /app

COPY --from=builder --chown=node:node /workspace/apps/web/.next/standalone ./
COPY --from=builder --chown=node:node /workspace/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=node:node /workspace/apps/web/public ./apps/web/public

WORKDIR /app/apps/web

USER node

EXPOSE 3000

CMD ["node", "server.js"]
