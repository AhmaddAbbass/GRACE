# --- build stage ---
FROM node:20-alpine AS build
WORKDIR /app
COPY kgx-ui/package*.json ./
RUN npm ci
COPY kgx-ui/ .
RUN npm run build

# --- serve stage ---
FROM nginx:1.27-alpine
# SPA fallback + proxy to backend (service name: backend)
COPY kgx-ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
