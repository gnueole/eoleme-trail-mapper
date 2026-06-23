FROM nginx:alpine

# Copy custom nginx configuration
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

# Copy public static files to Nginx server subpath directory
COPY public /usr/share/nginx/html/trail-mapper

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
