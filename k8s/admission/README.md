# Control de admisión (Kyverno)

Cilium decide con quién habla cada identidad. La admisión decide antes algo más
básico: **qué pod puede existir** y qué puede pedir. Las dos políticas se apoyan en
la misma idea: un pod legítimo del core lo crea siempre un controlador (Deployment),
así que un Pod suelto que copie etiquetas o pida una red dedicada es rechazado por
el API server antes de arrancar.

| Fichero | Política | Qué impide | Cómo se aplica |
|---|---|---|---|
| `kyverno-redes-dedicadas.yaml` | `kcd-multus-network-guard` | que un pod que no sea el AMF, el gNB o el UPF se conecte a las redes `access` o `n6`, o use otra IP | automática con `deploy_multus: true` (`site.yml`, tag `admission`). Pruebas: [`docs/pruebas-fase2.md`](../../docs/pruebas-fase2.md) |
| `kyverno-identidad-nf.yaml` | `kcd-nf-identity-guard` | que un Pod suelto copie las etiquetas de una NF del core o del gNB y Cilium lo trate como tal | manual |

## Por qué hace falta

Las políticas de Cilium reconocen a una NF por sus etiquetas
(`app.kubernetes.io/instance=open5gs-cp`, `app.kubernetes.io/name=<nf>`). Una
etiqueta la escribe quien crea el pod. Sin admisión, un impostor en `5g-cp` se pone
las etiquetas del AMF y pasa la política de red.

| Capa | Pregunta | Dónde actúa | Cuándo |
|---|---|---|---|
| Admisión | ¿Puede existir este pod con esta identidad o esta red? | API server | al crear el pod |
| Red (Cilium) | ¿Con quién puede hablar esta identidad? | datapath eBPF | en cada conexión |
| L7 (Cilium) | ¿Qué operación puede pedir? | proxy Envoy | en cada petición HTTP |
| Runtime (Tetragon) | ¿Qué puede ejecutar dentro del pod? | kernel | en cada `exec` |

## Aplicar la política de identidad de NF

Kyverno se instala con `deploy_multus: true`. Con una sola red, instálalo antes:

```bash
helm repo add kyverno https://kyverno.github.io/kyverno/ && helm repo update
helm install kyverno kyverno/kyverno --version 3.1.4 -n kyverno --create-namespace
```

```bash
kubectl apply -f k8s/admission/kyverno-identidad-nf.yaml

# Prueba: un Pod suelto que copia las etiquetas del AMF.
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Pod
metadata:
  name: impostor-con-etiquetas
  namespace: 5g-cp
  labels:
    app.kubernetes.io/instance: open5gs-cp
    app.kubernetes.io/name: amf
spec:
  containers:
    - name: attacker
      image: nicolaka/netshoot:v0.13
      command: ["sleep", "infinity"]
YAML
# Esperado: admission webhook ... denied the request: ... la identidad de una NF no se copia.
```

Si al aplicarla algo legítimo deja de arrancar, cambia `validationFailureAction` a
`Audit` y mira `kubectl get policyreport -A`.

## Qué cubre y qué no

- **Cubre:** un pod creado directamente que intenta pasar por una NF, por el gNB o
  conectarse a una red dedicada.
- **No cubre:** quien puede crear Deployments en esos namespaces. Sus pods los crea
  un controlador y pasan. Eso lo resuelve RBAC, y la cadena de suministro (una
  imagen alterada en un Deployment legítimo) la resuelve la firma de imágenes.
