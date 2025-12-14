# Stage 1: Build the UI5 application
FROM node:18 AS builder
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN npm run build
RUN ls -R /app/dist

# Stage 2: Serve the application with Nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
