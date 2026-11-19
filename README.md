# Sahana Eden 
Despliegue de Sahana Eden, familia de aplicaciones que proporciona herramientas de colaboración basadas en web que abordan los problemas comunes de coordinación ocasionados durante un desastre, incluyendo la búsqueda de personas desaparecidas, la gestión de la ayuda, la administración de los voluntarios, y el seguimiento eficaz de contacto entre los campamentos y los grupos gubernamentales, la sociedad civil (ONG) y las propias víctimas.

Se despliegan las ramas: `default`, `safire` y `skeleton` para ser consumidas por la [platadorma de gestion de desastres](https://github.com/disaster-management-platform).
| Componente | Versión fijada |
|---|---|
| Eden | 6.3, commit `5cc0fe1d2cf7cc4d58c6939a6e8d085b7d3c00a9` |
| Python | 3.11.14, imagen oficial `python:3.11.14-slim-bookworm` fijada por digest en Dockerfile |
| Sistema del contenedor | Debian 12, independiente del Python de Ubuntu |
| web2py | 3.3.3, commit `9005306c50ab2125c265bad8f4a9dacc56d460a1` |
| PyDAL | 20260313.1, submódulo oficial `b515c362e83006e79f681ff6491e4a4ab8566acb` |
| Rocket3 | Submódulo `4154030489ebab15b96d1f90a6f288cf4f64dd23` |
| YATL | Submódulo `c6983a51909f76c48f4a40c93eea7f485321cd3f` |
| Bibliotecas Python | Versiones y hashes en `requirements.lock`, incluidas dependencias transitivas |
| Base de datos | SQLite de la imagen Python, una `storage.db` por volumen |

La [release oficial 6.3](https://github.com/sahana/eden/releases/tag/6.3) establece Python 3.11+, web2py 3.3.3 y soporte para Debian 12/13. La [guía de instalación](https://eden-asp.readthedocs.io/en/latest/dev/setup.html) identifica el commit de web2py usado. Se contrastó con la documentación incluida en el código fijado. La release 6.3 no publica un parche adicional web2py/PyDAL; no se aplicaron parches ni cambios al código de Eden. Las bibliotecas se seleccionaron dentro de sus requisitos y se validaron en esta ejecución; no se afirma que sean una matriz oficial completa de compatibilidad.

El [Dockerfile documentado para desarrollo](https://eden-asp.readthedocs.io/en/latest/dev/docker.html) prepara herramientas, pero requiere instalar/configurar/iniciar Eden después. El Dockerfile de este directorio sí incluye la aplicación y su punto de entrada ejecuta el `noop.py` oficial con modelos antes de iniciar Rocket. No construye documentación ni necesita Sphinx. La imagen construida ocupa aproximadamente 468 MB.

`fetch-source.py` obtiene archivos de los repositorios oficiales, verifica SHA-256 y conserva sus licencias y atribuciones. No crea repositorios Git. `source/web2py/applications/eden` contiene una única copia de Eden. Los tres servicios comparten una imagen, no una base de datos.

## Archivos y aislamiento

| Servicio | Plantilla exacta | Aplicación web2py | Volumen persistente |
|---|---|---|---|
| default | default | eden_default | sahana-evaluation_default-data |
| skeleton | skeleton | eden_skeleton | sahana-evaluation_skeleton-data |
| safire | SAFIRE | eden_safire | sahana-evaluation_safire-data |

Cada volumen contiene `databases`, `sessions`, `uploads`, `errors`, `cache` y una clave HMAC propia. Los nombres de aplicación distintos producen cookies `session_id_eden_default`, `session_id_eden_skeleton` y `session_id_eden_safire`: los puertos, por sí solos, no separan cookies del navegador. Los enlaces a `/opt/eden` evitan duplicar código dentro de la imagen. Las configuraciones se montan de solo lectura. El administrador de aplicaciones de web2py está deshabilitado, la cuenta administradora de Eden permanece disponible.

## Ejecución

Ejecutar desde la raiz del repositorio.

1. Comprobar prerrequisitos y puertos:

```bash
docker version
docker compose version
python3 --version
uname -m
df -h .
ss -ltn '( sport = :8001 or sport = :8002 or sport = :8003 )'
```

`docker version` debe mostrar cliente y servidor accesibles; `uname -m`, `x86_64`. Se comprobó Docker Engine 29.8.0, cliente 29.9.0, Compose 5.6.0 y Python del host 3.12.3. Compose v2 con soporte de estas opciones también es adecuado, pero no se ensayó otra versión. Si Docker falta o exige permisos que el usuario no tiene, resolver su instalación/acceso antes; estos archivos no modifican el sistema.

2. Obtener las fuentes en una copia nueva de estos archivos:

```bash
python3 fetch-source.py
```
3. Construir la única imagen:

```bash
docker compose build default
```
Los otros servicios reutilizan esa imagen. No hace falta construir tres veces.

4. Iniciar las tres instancias:

```bash
docker compose up -d --no-build --wait --wait-timeout 300
```

La primera ejecución crea tablas e importa los datos oficiales seleccionados por cada plantilla. No interrumpir esa inicialización. Las siguientes ejecuciones conservan los datos; el mecanismo oficial detecta que la base ya está inicializada.

5. Iniciar una instancia individual:

```bash
docker compose up -d --no-build --wait skeleton
```

Sustituir `skeleton` por `default` o `safire`. Este comando no detiene servicios ya iniciados.

6. Consultar logs:

```bash
docker compose logs --tail=100
docker compose logs -f safire
```

Salir del seguimiento con Ctrl+C conserva los contenedores.

7. Comprobar estado y HTTP:

```bash
docker compose ps
curl -I http://127.0.0.1:8001/eden_default/
curl -I http://127.0.0.1:8002/eden_skeleton/
curl -I http://127.0.0.1:8003/eden_safire/
```
Puede haber una redirección normal hacia la portada o el login. Consultar mediante `curl -L -o /dev/null -w '%{http_code}\n' URL`.

8. Abrir en el navegador y usar las cuentas verificadas:

| Plantilla | URL | Administrador | Usuario normal |
|---|---|---|---|
| default | http://127.0.0.1:8001/eden_default/ | admin@example.com / testing | normaluser@example.com / testing |
| skeleton | http://127.0.0.1:8002/eden_skeleton/ | admin@example.com / testing | normaluser@example.com / testing |
| SAFIRE | http://127.0.0.1:8003/eden_safire/ | admin@example.com / testing | normaluser@example.com / testing |

SAFIRE también incluye `team1@example.com` a `team9@example.com`, contraseña `eden`, rol Call Logger. Se probó `team1@example.com`; no se inició sesión individualmente con los otros ocho. Son credenciales oficiales de demostración destinadas a esta evaluación local.

9. Detener sin perder datos:

```bash
docker compose stop
```

También se puede retirar contenedores y red conservando los volúmenes:

```bash
docker compose down
```

10. Reiniciar conservando datos:

```bash
docker compose restart
docker compose up -d --no-build --wait --wait-timeout 300
```

Para recrear contenedores conservando volúmenes, por ejemplo tras reconstruir la imagen:

```bash
docker compose up -d --no-build --force-recreate --wait --wait-timeout 300
```

## Comparación funcional

[default](https://github.com/sahana/eden/blob/5cc0fe1d2cf7cc4d58c6939a6e8d085b7d3c00a9/modules/templates/default/config.py), [skeleton](https://github.com/sahana/eden/blob/5cc0fe1d2cf7cc4d58c6939a6e8d085b7d3c00a9/modules/templates/skeleton/config.py), [SAFIRE](https://github.com/sahana/eden/blob/5cc0fe1d2cf7cc4d58c6939a6e8d085b7d3c00a9/modules/templates/SAFIRE/config.py).

| Aspecto | default | skeleton | SAFIRE |
|---|---|---|---|
| Propósito declarado | Organización pequeña que gestiona sus recursos | Base mínima para crear una plantilla propia | Sahana First Response |
| Módulos habilitados, además de los cuatro comunes | sync, gis, pr, org, hrm, vol, cms, doc, msg, supply, inv, asset, vehicle, req, project, stats | gis, pr, org, cms | sync, gis, pr, org, hrm, vol, cms, doc, msg, supply, inv, asset, vehicle, fin, cr, project, req, hms, event |
| Módulos presentes en el núcleo pero deshabilitados¹ | act, budget, cap, cr, deploy, disease, dvi, dvr, event, fin, fire, hms, irs, med, member, mpr, patient, proc, security, sit, transport, water | act, asset, budget, cap, cr, deploy, disease, doc, dvi, dvr, event, fin, fire, hms, hrm, inv, irs, med, member, mpr, msg, patient, proc, project, req, security, sit, stats, supply, sync, transport, vehicle, vol, water | act, budget, cap, deploy, disease, dvi, dvr, fire, irs, med, member, mpr, patient, proc, security, sit, stats, transport, water |
| Funcionalidad efectivamente comprobada | Login, listados habilitados, organización creada/leída y JSON, persistencia y aislamiento | Igual para sus módulos mínimos | Igual, excepto albergues; además login Call Logger y acceso a reportes |
| Datos iniciales y demo | default/base + default + default/users. default/Demo está comentado y no se activa | default/base + skeleton + default/users; no activa demo adicional | default/base + SAFIRE + default/users + SAFIRE/Demo; importación parcial |
| Roles y permisos | Política 5: ACL de controlador, función y tabla; roles HR, Logistics, Map, Organisation y Project Administrator | Política heredada 1: lectura general y edición autenticada; hereda roles de default/auth_roles.csv | Política 5; Call Logger, Call Supervisor y Map Admin, además de roles del sistema |
| Comprobación de permisos | Admin accede; usuario normal inicia sesión y recibe rechazo al intentar administrar usuarios | Mismo resultado; la política general es más permisiva | Mismo resultado; Call Logger accede al listado de reportes. No se auditó cada ACL |
| Incidentes | event deshabilitado; HTTP 404 comprobado | event deshabilitado; HTTP 404 comprobado | event habilitado; listado de incidentes y reportes HTTP 200; no se ensayó despacho completo |
| Personas y familias | pr habilitado; listado de personas 200. Núcleo incluye grupos/membresías; no se validó flujo familiar | Igual | Igual; no equivale al módulo dvr, deshabilitado en las tres |
| Organizaciones | org habilitado; alta y consulta comprobadas | Igual | Igual; demo incorpora dos organizaciones |
| Recursos e inventario | supply, inv, asset y vehicle habilitados; listados 200, sin ensayar movimientos | Deshabilitados; warehouse 404 comprobado | Habilitados; listados 200; catálogo demo y recursos materiales de escenarios fallan |
| Albergues | cr deshabilitado, 404 | cr deshabilitado | cr habilitado, pero listado 500. Además shelter_registration=False: no activa registro de residentes |
| Solicitudes y asistencia | req habilitado y listado 200; no se probó ciclo solicitud/compromiso/entrega | req deshabilitado | req habilitado y listado 200; no se probó ciclo completo. fin también habilitado; listado de gastos 200 |
| Coordinación de actividades | project habilitado; solo listado de proyectos probado. act deshabilitado | project y act deshabilitados | project/event habilitados; escenarios oficiales importados parcialmente; coordinación operativa no validada |
| Proyectos | project habilitado, listado 200 | Deshabilitado | project habilitado, listado 200 |
| Evaluación de daños | stats habilitado y portada 200; eso no demuestra evaluación de daños | Sin flujo de daños verificado | No se verificó un flujo de daños. stats deshabilitado (404), sit deshabilitado |
| GIS y mapas | gis habilitado, página 200 y estáticos 200 | Igual | Igual. No se verificó renderizado JavaScript, teselas, geocodificación ni análisis espacial |
| APIs e integración | GET de organizaciones en JSON autenticado comprobado; sync habilitado, sin réplica externa | JSON de organizaciones comprobado; sync deshabilitado | JSON autenticado comprobado; sync habilitado, sin réplica externa |
| Limitaciones | Cobertura amplia de logística; incidentes/albergues no habilitados | Muy pocos módulos; política simple que debe revisarse antes de producción | Fallo reproducible en albergues y demo incompleta; requiere mantenimiento oficial antes de usar esos flujos |
| Personalización posible | Nueva plantilla derivada con selección explícita de módulos, ACL, imports y workflows | Punto de partida mínimo para diseñar una configuración propia | Reutilizar patrones de primera respuesta tras resolver incompatibilidades; no asumir que habilitar implica funcionar |

Los cuatro módulos comunes son `default`, `admin`, `appadmin`, `errors`. `appadmin` y los modelos reutilizables incluyen `pr_person`, `pr_group` y membresías; `org_organisation`; `supply_item`, `inv_inv_item` y `asset_asset`; `req_req`; `project_project`; `event_incident`; `cr_shelter`. Las plantillas comparten ese núcleo y cambian configuración, permisos, vistas y personalizaciones.

## Bloqueos y servicios adicionales

1. **SAFIRE/albergues:** `modules/templates/SAFIRE/config.py`, función `customise_cr_shelter_resource`, referencia `current.s3db.cr_shelter.shelter_service_id`; el modelo actual no tiene ese atributo. La traza termina en `AttributeError: 'Table' object has no attribute 'shelter_service_id'`. La misma configuración estaba en la rama oficial `dev` al revisar. No se sustituyó por una variante ni se aplicó una corrección local.
2. **SAFIRE/demo:** `catalog_item.csv` falla por unidad `piece` no admitida; `scenario_asset.csv` falla por referencias y catálogo requeridos. La base resultante contiene 5 escenarios, 14 tareas de escenario y 13 asignaciones de personal; **0 artículos de catálogo y 0 recursos materiales de escenario**. Hay 11 usuarios. `incident_report.csv` solo contiene cabecera: no aporta incidentes demo. No debe interpretarse una pantalla vacía como pérdida de datos de prueba.
3. **GIS:** mensajes oficiales de dependencia opcional ausente para GDAL (Shapefile) y Selenium (impresión de mapas). No se instalaron porque esos flujos no se probaron. Teselas, capas remotas, geocodificación y proveedores como Google/Bing/OpenWeatherMap pueden necesitar red, claves, condiciones de uso o servicios adicionales. No se contrataron ni validaron.
4. **Mensajería:** faltan pyserial para módem serie y sgmllib3k para importación de feeds. Correo/SMS y otros canales requieren servidor o proveedor configurado; no se enviaron mensajes. Los módulos msg de default/SAFIRE se probaron solo como interfaz accesible.
5. **Procesamiento programado e integraciones:** los modelos crean tareas del scheduler, pero este despliegue no inicia workers. Sincronización remota, tareas periódicas, notificaciones y conectores no están validados. No se añadieron servicios que no fueran necesarios para las pruebas interactivas.
6. **Alcance:** Rocket y SQLite sirven para evaluación local. No se realizaron pruebas de carga, auditoría integral de seguridad, flujos completos de logística, familias, asistencia, proyectos o daños, ni configuración de producción. Las cuentas demo y los permisos heredados deben revisarse antes de cualquier despliegue real.

## Plantilla de plataforma: personas afectadas (07B.2)

El servicio `default` utiliza ahora `platform`, derivada de `default`. Conserva los módulos existentes y habilita DVR, CR y EVENT; PR, SUPPLY, INV y REQ siguen siendo nativos. `templates/platform` se incluye en la imagen y se monta de solo lectura en desarrollo. `docker compose up -d --no-build default` reutiliza la imagen existente y conserva el volumen; una compilación posterior incorpora la misma plantilla. Las otras dos plantillas no cambian.

La política 7 de Eden aplica realms jerárquicos. Los registros personales y familiares creados por operadores pertenecen a su organización; expedientes y refugios validan la organización y establecen su propietario mediante callbacks nativos. No se concede acceso global a personas utilizando el permiso del directorio de organizaciones. Las cuentas históricas y sus registros no se reasignan automáticamente.

Se conservan los flujos nativos `/pr/person`, `/pr/group`, `/dvr/case` y `/cr/shelter`, sus componentes y representaciones REST `.json`. Eden valida y persiste; Java no consulta tablas ni replica sus reglas. No se añaden endpoints alternativos sin un consumidor implementado. El acceso web requiere sesión propia de Eden; un JWT de la plataforma no se convierte en una sesión administrativa.

Validación reproducible sobre la instancia local:

```sh
export EDEN_TEST_URL=http://127.0.0.1:8001/eden_default
export EDEN_ADMIN_CONFIG="$HOME/.config/disaster-management-platform/eden-admin.env"
export EDEN_TEST_IDENTITIES="$HOME/.config/disaster-management-platform/eden-platform-test.json"
python3 scripts/platform_test.py
```

El script requiere requests y beautifulsoup4. Lee las credenciales como datos, usa exclusivamente formularios y APIs nativas y guarda las contraseñas técnicas aleatorias fuera de Git con permisos 600. Aprovisiona dos organizaciones sintéticas identificables, roles y usuarios sin privilegios administrativos. Comprueba creación, consulta y actualización propias, rechazo de consultas cruzadas, creación en una organización ajena y administración de catálogos. Los datos sintéticos se conservan para repetir los mismos casos, sin personas reales ni acceso directo a la base de datos. Los endpoints interactivos nativos pueden denegar mediante redirección 303 al índice; las representaciones JSON deniegan con 403/404.

## Recursos nativos (07C.1)

SUPPLY mantiene el catálogo; INV administra almacenes, existencias, ajustes y movimientos; REQ administra solicitudes, compromisos y cumplimiento. ASSET, VEH y HRM permanecen habilitados como en default. El catálogo no se duplica en Java. Los permisos de catálogo quedan reservados a ADMIN/LOGS_ADMIN; los operadores técnicos de recursos consultan el catálogo y operan sus propios sitios, sin privilegios administrativos ni permisos de personas otorgados por este flujo.

La plantilla asigna los registros logísticos a la organización del operador y valida sitios mediante auth.permitted_facilities, conservando las validaciones de Eden. No se habilita edición directa de cantidades: los datos de prueba utilizan el ajuste nativo de inventario y su cierre. Los compromisos se registran mediante los componentes de REQ; no se calculan ni se descuentan existencias desde Jakarta.

Prueba dirigida posterior a 07B.2, reutilizando sus organizaciones y los helpers de formularios/APIs:

```sh
export EDEN_TEST_IDENTITIES="$HOME/.config/disaster-management-platform/eden-platform-resources-test.json"
python3 scripts/resources_test.py
```

Conserva EDEN_TEST_URL y EDEN_ADMIN_CONFIG del ejemplo anterior. Las cuentas técnicas de recursos son distintas de las de personas. Comprueba almacenes propios y ajenos, catálogo de solo lectura para runtime, ajustes nativos con 10 unidades sintéticas, solicitudes y compromisos de 2 unidades, aislamiento de existencias/solicitudes/compromisos y rechazo de sitios ajenos. El aprovisionamiento reutiliza IDs nativos obtenidos por HTTP; nunca interpreta el ID de un desastre .NET como ID Eden.

Alcance verificado: operaciones nativas locales y aislamiento organizacional. No se afirma entrega física de suministros, cobertura de todos los módulos de Eden, SSO ni integración financiera. El compromiso no equivale a entrega. La financiación de Reconstrucción permanece separada de inventarios. Los datos de prueba están identificados con Platform07B/Platform07C y no contienen personas reales. No se modificaron otros despliegues ni se implementaron endpoints duplicados para pantallas futuras.

## SSO OIDC con cuentas previamente autorizadas

La plantilla `platform` admite Keycloak mediante `templates/platform/oidc.py` y el hook nativo `customise_auth_user_controller`. No crea usuarios ni los busca por correo. Un administrador aprovisiona primero la cuenta, organización, roles y realms en Eden. Un archivo JSON privado contiene entradas `issuer`, `subject`, `userId`, `organizationId` (plataforma) y `edenOrganizationId`. Solo un vínculo exacto permite iniciar sesión; la organización firmada debe coincidir y la cuenta nativa debe estar aprobada y desbloqueada. Las ACL siguen siendo las de Eden; los roles del token no se convierten en permisos.

En el aprovisionamiento existente de Keycloak, `KC_EDEN_REDIRECT_URI` habilita el cliente confidencial `eden`, Code + PKCE S256, sin password grant ni implicit flow. Obtenga su secreto mediante administración segura. El archivo externo `EDEN_OIDC_ENV_FILE` proporciona `EDEN_OIDC_ISSUER`, `EDEN_OIDC_CLIENT_ID`, `EDEN_OIDC_CLIENT_SECRET`, `EDEN_OIDC_REDIRECT_URI`, `EDEN_OIDC_BINDINGS_FILE=/run/eden-identity-bindings.json` y `EDEN_OIDC_CA_FILE=/run/eden-identity-ca.crt`. Para la red Docker local puede configurar `EDEN_OIDC_BACKCHANNEL=https://keycloak:8443/realms/platform`: la conexión sigue verificando el certificado y el hostname del issuer público, sin desactivar TLS. El callback exige HTTPS; solo loopback de desarrollo permite HTTP con `EDEN_OIDC_LOCAL_DEVELOPMENT=true`.

```sh
docker compose build default
docker compose -f compose.yaml -f compose.oidc.yaml up -d --no-build default
```

Además del archivo de entorno, exporte `EDEN_OIDC_BINDINGS_FILE` y `EDEN_OIDC_CA_FILE` como rutas locales de los archivos privados a montar. El overlay utiliza la red existente `platform-identity_default`; conserva el volumen de Eden. Los secretos y vínculos no se incluyen en la imagen ni Git. Sin configuración OIDC se mantiene el comportamiento anterior. Las identidades técnicas HTTP Basic conservan sus permisos nativos y no deben compartirse con usuarios.

Se verifica issuer, firma RS256, audience, expiración, nonce, state y PKCE. El código se canjea una sola vez; no se guardan tokens en la sesión. Metadatos y claves públicas se almacenan cinco minutos; ante un kid desconocido se deniega acceso hasta renovar la caché. La sesión autenticada y el logout local siguen siendo de Eden; no se afirma logout global ni revocación instantánea de sesiones existentes. Limite la exposición y no registre query strings del callback en proxies de acceso.

`scripts/oidc_test.py` requiere `EDEN_TEST_URL` local, `EDEN_SSO_TEST_USERS` (credenciales sintéticas externas), `EDEN_TEST_IDENTITIES` y `EDEN_SSO_TEST_CA`. Se validaron MFA real, vínculo exacto, aislamiento A/B, rechazo de coincidencia de email sin vínculo, state inválido y acceso directo no autenticado. Esto no certifica el aislamiento logístico pendiente.
