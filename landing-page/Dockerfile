FROM node:20-alpine AS build
WORKDIR /app
COPY . .
RUN node build.mjs

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
RUN printf 'server {\n  listen 80;\n  root /usr/share/nginx/html;\n  server_tokens off;\n  location / { try_files $uri $uri/ =404; }\n}\n' > /etc/nginx/conf.d/default.conf
