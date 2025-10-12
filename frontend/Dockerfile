FROM node:18-alpine AS base

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

FROM base AS development
ENV NODE_ENV=development
CMD ["npm", "start"]

FROM base AS build
ENV NODE_ENV=production
RUN npm run build

FROM nginx:alpine AS production
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
