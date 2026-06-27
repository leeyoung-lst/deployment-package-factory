FROM node:22-alpine AS build

WORKDIR /app

COPY frontend/package.json /app/package.json
COPY frontend/tsconfig.json /app/tsconfig.json
COPY frontend/index.html /app/index.html
COPY frontend/vite.config.ts /app/vite.config.ts
COPY frontend/src /app/src

RUN corepack enable && pnpm install --prod=false
RUN pnpm build

FROM nginx:1.27-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
