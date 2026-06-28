FROM node:22-alpine AS build

WORKDIR /app

COPY frontend/package.json /app/package.json
COPY frontend/pnpm-lock.yaml /app/pnpm-lock.yaml
COPY frontend/pnpm-workspace.yaml /app/pnpm-workspace.yaml
COPY frontend/tsconfig.json /app/tsconfig.json
COPY frontend/index.html /app/index.html
COPY frontend/vite.config.ts /app/vite.config.ts
COPY frontend/src /app/src

RUN corepack enable && corepack prepare pnpm@10.24.0 --activate
RUN pnpm install --frozen-lockfile --prod=false
RUN pnpm build

FROM nginx:1.27-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/docker-entrypoint.sh /docker-entrypoint.sh
COPY --from=build /app/dist /usr/share/nginx/html
RUN chmod +x /docker-entrypoint.sh \
    && chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/run /run /docker-entrypoint.sh

USER 101

EXPOSE 8080
ENTRYPOINT ["/docker-entrypoint.sh"]
