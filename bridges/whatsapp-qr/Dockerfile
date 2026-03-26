FROM node:20-slim

WORKDIR /app

COPY package.json ./
RUN npm install --production

COPY index.js ./

ENV GATEWAY_URL=http://gateway:8000
ENV SESSION_DIR=/data/session
ENV BRIDGE_PORT=3001

EXPOSE 3001

CMD ["node", "index.js"]
