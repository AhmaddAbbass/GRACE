# --- build stage ---
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# --- serve stage ---
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# minimal SPA config (no proxy). If your UI calls the API directly, skip custom nginx.conf.
# If you DO need proxying, add an nginx.conf and COPY it here.
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
