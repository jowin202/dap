# Kubernetes Deployment

## 1. Secret anlegen

```bash
kubectl create namespace dap

kubectl create secret generic dap-secrets \
  --namespace dap \
  --from-literal=POSTGRES_PASSWORD='<dein-db-passwort>' \
  --from-literal=DATABASE_URL='postgresql+asyncpg://dap:<dein-db-passwort>@db/dap' \
  --from-literal=ADMIN_TOKEN='<dein-admin-token>' \
  --from-literal=JWT_SECRET='<dein-jwt-secret>'
```

## 2. Domain in ingress.yml eintragen

`files.example.com` in [ingress.yml](ingress.yml) durch deine echte Domain ersetzen.

## 3. Alles deployen

```bash
kubectl apply -f k8s/
```

Es gibt nur ein Image (`ghcr.io/jowin202/dap/app`) mit Frontend + Backend.
Datenbank-Migrationen laufen beim Start des Containers automatisch.

## Aktualisieren (nach neuem Image-Build)

```bash
kubectl rollout restart deployment/app -n dap
```

## Status prüfen

```bash
kubectl get all -n dap
kubectl logs -n dap deployment/app
```
