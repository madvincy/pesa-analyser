#!/bin/bash

# Azure Deployment Script for Pesa Analyser

echo "🚀 Starting Azure Deployment..."

# Variables
RESOURCE_GROUP="pesa-rg"
LOCATION="eastus"
ACR_NAME="pesaregistry"
AKS_NAME="pesa-cluster"
APP_NAME="pesa-analyser"

# Login to Azure
echo "Logging into Azure..."
az login --use-device-code

# Create Resource Group
echo "Creating Resource Group..."
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Azure Container Registry
echo "Creating Azure Container Registry..."
az acr create \
    --resource-group $RESOURCE_GROUP \
    --name $ACR_NAME \
    --sku Standard \
    --admin-enabled true

# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query "username" -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)

echo "ACR Username: $ACR_USERNAME"
echo "ACR Password: $ACR_PASSWORD"

# Build and push Frontend
echo "Building and pushing Frontend..."
az acr build \
    --registry $ACR_NAME \
    --image pesa-frontend:latest \
    --file frontend/Dockerfile \
    ./frontend

# Build and push Backend
echo "Building and pushing Backend..."
az acr build \
    --registry $ACR_NAME \
    --image pesa-backend:latest \
    --file backend/Dockerfile \
    ./backend

# Create Azure Kubernetes Service
echo "Creating AKS Cluster..."
az aks create \
    --resource-group $RESOURCE_GROUP \
    --name $AKS_NAME \
    --node-count 3 \
    --node-vm-size Standard_D2s_v3 \
    --enable-addons monitoring \
    --generate-ssh-keys \
    --attach-acr $ACR_NAME

# Get credentials
echo "Getting AKS credentials..."
az aks get-credentials --resource-group $RESOURCE_GROUP --name $AKS_NAME

# Create PostgreSQL
echo "Creating PostgreSQL..."
az postgres flexible-server create \
    --resource-group $RESOURCE_GROUP \
    --name pesa-postgres \
    --location $LOCATION \
    --sku-name Standard_B1ms \
    --storage-size 32 \
    --version 15 \
    --admin-user postgres \
    --admin-password $(openssl rand -base64 32)

# Create Redis Cache
echo "Creating Redis Cache..."
az redis create \
    --resource-group $RESOURCE_GROUP \
    --name pesa-redis \
    --location $LOCATION \
    --sku Basic \
    --vm-size C0

# Deploy to Kubernetes
echo "Deploying to Kubernetes..."
kubectl create namespace pesa-analyser

# Apply secrets
echo "Applying secrets..."
kubectl create secret generic pesa-secrets \
    --namespace pesa-analyser \
    --from-literal=SECRET_KEY=$(openssl rand -base64 32) \
    --from-literal=JWT_SECRET=$(openssl rand -base64 32)

# Apply configurations
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/hpa.yaml

# Get service IP
echo "Getting service IP..."
SERVICE_IP=$(kubectl get svc frontend-service -n pesa-analyser -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "Application URL: http://$SERVICE_IP"

echo "✅ Azure Deployment Complete!"
