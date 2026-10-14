FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN yarn install --non-interactive --network-timeout 600000
COPY . .
# empty = same origin; nginx proxies /api to the backend
ARG REACT_APP_BACKEND_URL=""
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
RUN rm -f .env && yarn build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
