#!/bin/bash
# Start all services

echo "Starting server services..."
docker compose up -d

echo "Services started successfully!"
docker compose ps
