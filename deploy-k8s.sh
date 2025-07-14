#!/bin/bash

set -e

NAMESPACE="imagen-processing"
DOCKER_REGISTRY="localhost:5000"

echo "Desplegando sistema en Kubernetes..."

# verificar si un comando existe
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Verificar herramientas necesarias
if ! command_exists kubectl; then
    echo "kubectl no esta instalado"
    exit 1
fi

if ! command_exists minikube; then
    echo "minikube no esta instalado" 
    exit 1
fi

# Verificar que Minikube esta corriendo
if ! minikube status | grep -q "Running"; then
    minikube start --driver=docker --cpus=2 --memory=4096 --disk-size=20gb --kubernetes-version=v1.33.1
fi

# Configurar Docker para usar el registro de Minikube
echo "Configurando Docker registry..."
eval $(minikube docker-env)

echo "Construyendo imagenes..."
docker build -t nodo-procesamiento:latest -f nodos/Dockerfile .
docker build -t cliente-flask:latest -f cliente/Dockerfile .

echo "Creando namespace..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

echo "Configuración base..."
kubectl apply -f k8s/00-namespace.yaml

echo "GlusterFS..."
kubectl apply -f k8s/01-glusterfs.yaml

echo "Esperando a que GlusterFS este listo..."
kubectl wait --for=condition=ready pod -l app=glusterfs -n $NAMESPACE --timeout=300s

echo " Nodos de procesamiento..."
kubectl apply -f k8s/02-nodos-procesamiento.yaml

echo "Esperando a que los nodos estén listos..."
kubectl wait --for=condition=ready pod -l app=nodo-procesamiento -n $NAMESPACE --timeout=300s

echo "Cliente Flask..."
kubectl apply -f k8s/03-cliente-flask.yaml

echo "Esperando a que el cliente este listo..."
kubectl wait --for=condition=ready pod -l app=cliente-flask -n $NAMESPACE --timeout=300s

echo "configurando acceso..."
kubectl patch service cliente-service -n $NAMESPACE -p '{"spec":{"type":"LoadBalancer"}}'

echo "despliegue completado!"
kubectl get pods -n $NAMESPACE

echo ""
echo "URLs de acceso:"
echo "  Aplicación: http://$(minikube ip):$(kubectl get service cliente-service -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}')"
echo "  Dashboard K8s: minikube dashboard"

echo ""
echo "Comandos útiles:"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl logs -f deployment/cliente-flask -n $NAMESPACE"
echo "  kubectl logs -f deployment/nodo-procesamiento -n $NAMESPACE"
echo "  kubectl describe pod <pod-name> -n $NAMESPACE"