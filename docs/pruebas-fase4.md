# Pruebas — Fase 4: mTLS en la SBI (`sbi_tls`)

Giro 2 de la charla: TS 33.501 pide proteger la SBI con TLS, y al activarlo la
política L7 de Cilium se queda ciega. El proxy ya no puede leer método ni ruta, y
solo quedan L3/L4 e identidad.

> **Estado de verificación.**
> - Comprobado en local:
>   - la plantilla de configuración de las NF se renderiza y da YAML válido en las
>     cuatro combinaciones de `deploy_multus` × `sbi_tls`;
>   - el script de PKI genera la CA y los certificados, `openssl verify` los valida,
>     las SAN y los EKU son correctos y una segunda pasada no regenera nada;
>   - los cuatro overlays de políticas construyen, y los `-tls` no tienen reglas
>     `http`;
>   - `make policy-matrix` da lo esperado; yamllint, `ansible-lint` y
>     `--syntax-check` pasan.
> - **Nada se ha ejecutado en un clúster.** No se sabe aún qué hace Cilium con una
>   regla L7 sobre un flujo TLS: §4 deja el comando para medirlo.

## 1. Qué hace `sbi_tls: true`

| Pieza | Qué | Dónde |
|---|---|---|
| PKI | CA propia del lab y un certificado RSA 2048 por NF y para `sbi-probe`. SAN = nombres del Service `open5gs-cp-<nf>-sbi` (corto, `.5g-cp`, `.svc`, `.svc.cluster.local`), EKU servidor y cliente. Se queda en el master (`/etc/kcd-lab/pki/sbi`, solo root); **nada va al repo** | `templates/sbi-pki.sh.j2` |
| Secrets | `sbi-tls-<nf>` en 5g-cp con `ca.crt`, `tls.crt` y `tls.key`, montados en `/etc/open5gs/tls` | `site.yml` |
| Config de las NF | `customOpen5gsConfig` completo por NF (reemplaza el fichero del chart) con `default.tls.server` (`scheme: https`, `private_key`, `cert`, `verify_client: true`, `verify_client_cacert`) y `default.tls.client` (`scheme: https`, `cacert`, `client_private_key`, `client_cert`); `advertise` con el FQDN del Service; URIs del SCP y del NRF en `https://` | `templates/open5gs-cp-nf-config-values.yaml.j2` |
| Sondas | `customLivenessProbe`/`customReadinessProbe` por TCP al 7777 (una sonda HTTP fallaría contra HTTPS con certificado de cliente) | la misma plantilla |
| Políticas | overlay `<modo>-tls`: el de la Fase 3 sin las reglas `http` del NRF (componente `sbi-tls`) | `cilium-policies/lab/` |
| Smoke | sale de `sbi-probe` y usa HTTPS con certificado si lo hay | `bootstrap/checks/smoke-control-plane.sh` |

Las claves de configuración TLS son las de `configs/open5gs/*.yaml.in` de Open5GS
v2.7.5. La plantilla también genera el AMF de las redes dedicadas, así que
`deploy_multus` y `sbi_tls` se combinan: con los dos, el AMF lleva NGAP en
10.10.0.10 y TLS en la SBI.

**TS 33.501 §13.1:** todas las NF deben soportar TLS con autenticación mutua en la
SBI. Dentro de una PLMN, el operador puede no usarlo si la red ya está protegida de
otra forma (NDS/IP o seguridad física). Aquí se activa para ver qué pasa con la
política L7 cuando el operador sí lo usa.

## 2. Antes de activar: comprobar el chart

Supuestos **no verificados** contra el chart de Gradiant 2.3.4:

| Supuesto | Si falla |
|---|---|
| `<nf>.customOpen5gsConfig` reemplaza el fichero entero de cada NF | La NF arranca sin TLS o con config mezclada |
| `<nf>.extraVolumes` y `<nf>.extraVolumeMounts` existen | El certificado no se monta y la NF no arranca |
| `customLivenessProbe` y `customReadinessProbe` sustituyen las sondas del chart | Si las sondas del chart son HTTP, los pods no pasan a Ready |
| El Service de MongoDB es `open5gs-cp-mongodb` | UDR y PCF no conectan con la base (`open5gs_db_uri`) |
| La config de cada NF de la plantilla no pierde nada de lo que pone el chart | Comparar con `diff` (abajo) |
| El proceso de Open5GS puede leer la clave con `defaultMode: 0400` (corre como root) | Si corre con otro usuario, subir el modo o usar `fsGroup` |

En el master, con la carpeta de trabajo del playbook (`/tmp/cib46/`):

```bash
CHART=oci://registry-1.docker.io/gradiantcharts/open5gs
# sin TLS (referencia) y con TLS
helm template open5gs-cp $CHART --version 2.3.4 -n 5g-cp -f /tmp/cib46/open5gs-values.yaml > /tmp/sin-tls.yaml
helm template open5gs-cp $CHART --version 2.3.4 -n 5g-cp -f /tmp/cib46/open5gs-values.yaml \
  -f /tmp/cib46/open5gs-cp-nf-config-values.yaml > /tmp/con-tls.yaml
diff <(grep -A60 'nrf.yaml' /tmp/sin-tls.yaml) <(grep -A60 'nrf.yaml' /tmp/con-tls.yaml)
grep -nE 'sbi-tls|/etc/open5gs/tls|tcpSocket|httpGet' /tmp/con-tls.yaml | head -40
grep -n 'name: open5gs-cp-mongodb' /tmp/sin-tls.yaml
```

Haz el `diff` para cada NF: solo deben cambiar `default.tls`, `advertise` y los
`https://`.

## 3. Activar y comprobar (no ejecutado aún)

1. Plan B funcionando y snapshot.
2. `sbi_tls: true` en `group_vars/all.yml` y `ansible-playbook site.yml -K`.

```bash
sudo ls -l /etc/kcd-lab/pki/sbi                       # ca.* y <nf>.crt/.key, modo 600
kubectl -n 5g-cp get secret | grep sbi-tls            # 11 Secrets (10 NF + sbi-probe)
kubectl -n 5g-cp get pods                             # todas las NF Running y Ready
kubectl -n 5g-cp logs deploy/open5gs-cp-nrf | grep -iE 'tls|https|registered'
kubectl get cnp -n 5g-cp -l kcd.io/sbi-tls=true       # overlay -tls aplicado
make smoke                                            # attach=SI sbi(mTLS)=200
```

En claro ya no responde nada:

```bash
kubectl -n 5g-cp exec deploy/sbi-probe -- curl -s --http2-prior-knowledge -m 3 \
  -o /dev/null -w '%{http_code}\n' http://open5gs-cp-nrf-sbi.5g-cp.svc.cluster.local:7777/nnrf-disc/v1/nf-instances
# 000 o error de protocolo
```

Y un cliente sin certificado es rechazado por el propio NRF (`verify_client: true`):

```bash
kubectl -n 5g-cp exec deploy/sbi-probe -- curl -s --http2 -m 3 --cacert /etc/open5gs/tls/ca.crt \
  -o /dev/null -w '%{http_code}\n' https://open5gs-cp-nrf-sbi.5g-cp.svc.cluster.local:7777/nnrf-disc/v1/nf-instances
# fallo del handshake TLS
```

## 4. La demo: la misma petición, con y sin TLS

```bash
make demo-l7-ciega
```

Lanza `GET /nnrf-nfm/v1/nf-instances` (listar todos los perfiles de NF) desde
`sbi-probe`, que solo tiene permiso para `GET /nnrf-disc/v1/nf-instances`. Es una
lectura y no cambia nada en el core.

| Caso | Política aplicada | Esperado por diseño | Medido en el lab |
|---|---|---|---|
| A. SBI en claro | `<modo>` (con reglas `http`) | 403 del proxy de Cilium; Hubble muestra `GET /nnrf-nfm/v1/nf-instances` con veredicto DROPPED/403 | _pendiente_ |
| B. SBI con mTLS | `<modo>-tls` (sin reglas `http`) | La petición llega al NRF: `sbi-probe` tiene un certificado firmado por la CA del lab, como lo tendría una NF comprometida. Hubble solo ve un flujo TCP | _pendiente_ |
| C. SBI con mTLS **y** la regla L7 puesta | `<modo>` (con reglas `http`) | **No se sabe: medirlo.** Lo esperable es que el proxy no pueda interpretar el TLS como HTTP y corte la conexión (también la de las NF legítimas hacia el NRF), pero no hay que afirmarlo sin verlo | _pendiente_ |

Cómo provocar el caso C, y volver:

```bash
make policies MODE=una-red          # o multus: overlay CON reglas http, con TLS activo
make demo-l7-ciega
hubble observe -n 5g-cp --to-label app.kubernetes.io/name=nrf --last 30
hubble observe -n 5g-cp --to-label app.kubernetes.io/name=nrf --verdict DROPPED --last 30
kubectl -n 5g-cp logs deploy/open5gs-cp-nrf --tail=30
make smoke                          # ¿siguen registrándose las NF y el UE?
make policies                       # volver al overlay -tls
```

Apunta lo que salga en las tres filas, en la tabla y en el guion de la charla.

## 5. Notas

- **Con TLS, spec2policy pierde los datos** (Fase 5): sin L7 no hay flujos HTTP en
  Hubble. El blast radius map se captura con la SBI en claro.
- **Rotación de certificados:** borra `/etc/kcd-lab/pki/sbi/<nf>.crt` y relanza;
  el playbook vuelve a emitirlo, actualiza el Secret y reinicia las NF.
- **Volver a la SBI en claro:** `sbi_tls: false` y relanzar. Los Secrets se quedan,
  pero ya no se montan.
