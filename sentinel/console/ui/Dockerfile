# syntax=docker/dockerfile:1
FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS build
WORKDIR /ui
COPY sentinel/console/ui/package.json sentinel/console/ui/package-lock.json ./
RUN npm ci
COPY sentinel/console/ui ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.31.7-alpine3.24-slim@sha256:b94a56c52fd315bbd8f1f4368d64c25983351c978313e02feff2c0b35e856f2d
COPY sentinel/console/ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /ui/dist /usr/share/nginx/html
EXPOSE 8080
