# Stage 1: Build the UI5 application
FROM node:18 AS builder
WORKDIR /app
COPY package.json . 
COPY package-lock.json .
RUN npm install
COPY webapp ./webapp
COPY ui5.yaml .
COPY ui5-local.yaml .
COPY ui5-mock.yaml .
COPY ui5-deploy.yaml .
RUN npm run build:cf
RUN ls -R dist

# Stage 2: Serve the application with Nginx
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
