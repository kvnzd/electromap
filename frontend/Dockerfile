# Imagen del frontend de ElectroMap: compila React con Vite y lo sirve con nginx.
#     docker build -t electromap-frontend --build-arg VITE_API_URL=http://localhost:8000 frontend
# VITE_API_URL queda fija en el código compilado (dirección del backend vista desde el navegador).

# Etapa 1: compilar
FROM node:22-alpine AS compilacion
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Etapa 2: servir solo los archivos compilados (imagen liviana, sin Node ni código fuente)
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=compilacion /app/dist /usr/share/nginx/html
EXPOSE 80
