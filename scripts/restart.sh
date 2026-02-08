#!/bin/bash
# Restart all services

echo "Restarting server services..."
docker-compose restart

echo "Services restarted successfully!"
docker-compose ps
