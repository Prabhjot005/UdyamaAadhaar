FROM node:24.11.0-alpine

WORKDIR /app

COPY package*.json .
RUN npm install

COPY . .

EXPOSE 3003 

CMD ["npm", "start"]

