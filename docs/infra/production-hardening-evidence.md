# Production Deployment Hardening — Evidence Boundary

**Scope:** PR #244, branch `feat/issue-182-deployment-e2e`
**Card:** `t_a10e1e6a` (production-profile image digest pinning + compose-guard re-verification)
**Reviewed HEAD at the time of writing:** `614ed31f2844bc910061ec9e665d27186d865d3e`

---

## 1. What this evidence level is

**Evidence level: L1 (static).**

The claims below are established by:

- a static guard (`scripts/check_production_compose.py`) executed against the
  committed Compose file, and
- image digests resolved from the public container registries and cross-checked
  by hashing the manifest bodies that the registries actually served.

Nothing in this document was produced by deploying to a plant, a production
host, or a hardware bench.

---

## 2. What this evidence level is NOT

This card produces **no** claim in the following areas. Each is explicitly
out of scope and must not be inferred from anything below.

| Not claimed | Why |
|---|---|
| **Lifecycle rehearsal** | No production deployment, upgrade, rollback or teardown was rehearsed. Container start-up order, restart behaviour and data migration under real load were not exercised. |
| **Physical control-isolation proof** | No physical uKit motor, relay, limit switch or safety circuit was involved. The command path was simulated only. |
| **HIL (L4)** | No hardware-in-the-loop bench, no real ESP32 bridge, no real MQTT device identity binding. |
| **Production-rollout acceptance** | This is **not** a production authorisation, a production sign-off, or a go-live approval. The maintainer review decides acceptance; this document is input to it. |
| **Certificate or ACL issuance** | The TLS trust material and the ACL file are **operator-supplied at deployment time**. They are generated outside CI and are gitignored. Their *generation* was not performed or verified here. |
| **Broker policy conformance** | ADR-0010 is **Proposed**, not Accepted. The Compose file implements the policy it describes; it does not by itself constitute evidence that the policy is enforced against a live broker. Negative (deny) authorisation cases require broker-side test evidence that is out of this card's scope. |

---

## 3. Image digest pinning (production profiles)

Every image referenced by a service in the `PRODUCTION` or
`PRODUCTION_READONLY` profile is pinned to an immutable OCI manifest digest.
The human-readable tag is retained as a comment next to each digest for
provenance.

| Image | Digest | Registry source |
|---|---|---|
| `eclipse-mosquitto:2` | `sha256:860aeb5d63ce509508f6dcfb2bc8a1c1dd2bc60555b562b45ce90e52d8dabb0f` | Docker Hub — `registry-1.docker.io/v2/library/eclipse-mosquitto/manifests/2` |
| `mongo:4.4` | `sha256:4be76f674fc4b27859816811b8baa3c51830eb1dbf4ca81a51e26b79edd662ef` | Docker Hub — `registry-1.docker.io/v2/library/mongo/manifests/4.4` |
| `quay.io/fiware/orion-ld:1.5.0` | `sha256:dcb8c4100769b2a873b6d16c8ed501515fe3fb9ebde8d0fb4c3129ef07671bd2` | Quay — `quay.io/v2/fiware/orion-ld/manifests/1.5.0` |
| `nginx:alpine` | `sha256:a3554c0d0b48177b1413c26e01f695334428020d9df01243fbae3e11cfd17417` | Docker Hub — `registry-1.docker.io/v2/library/nginx/manifests/alpine` |
| `python:3.12-slim` | `sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704` | Docker Hub — `registry-1.docker.io/v2/library/python/manifests/3.12-slim` |
| `node:20-alpine` | `sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293` | Docker Hub — `registry-1.docker.io/v2/library/node/manifests/20-alpine` |

### How each digest was resolved and cross-checked

1. **Registry manifest API.** For Docker Hub images a pull token was obtained
   from `https://auth.docker.io/token?service=registry.docker.io&scope=repository:<repo>:pull`;
   for the Quay image the registry was queried directly. The manifest was
   requested with `Accept` covering
   `application/vnd.oci.image.index.v1+json`,
   `application/vnd.docker.distribution.manifest.list.v2+json`,
   `application/vnd.oci.image.manifest.v1+json` and
   `application/vnd.docker.distribution.manifest.v2+json`.
2. **Body-hash cross-check.** The SHA-256 of the *returned manifest body* was
   computed and compared with the `Docker-Content-Digest` response header.
   For all six images the two values were identical. A digest that could not
   be resolved this way was left unpinned and reported, never invented.
3. **Independent second source.** `docker manifest inspect -v <image>` was run
   for each image; the returned per-platform descriptors were consistent with
   the same manifest tree.
4. **Pull confirmation.** `docker pull <image>@<digest>` followed by
   `docker image inspect --format '{{json .RepoDigests}}'` was performed for
   `eclipse-mosquitto:2` and `quay.io/fiware/orion-ld:1.5.0`; the reported
   `RepoDigests` matched the pinned digests exactly.

The digests are multi-architecture **index** digests (the Docker Hub images
resolve to 6–16 platform manifests each), which is what makes a single pinned
reference valid across architectures.

---

## 4. Compose guard re-verification

The existing guard was re-run and extended. The guard fails closed: it exits
non-zero and prints one `FAIL:` line per violation.

```console
$ python scripts/check_production_compose.py docker-compose.full.yml
PASS: docker-compose.full.yml satisfies production compose security invariants
$ echo $?
0
```

The guard rejects, with a dedicated `FAIL:` message and a regression test for
each:

| Permissive default | Rejected? |
|---|---|
| Wildcard Orion-LD CORS origins (`*`) | Yes |
| Empty or defaulted `SAFETY_OPERATOR_TOKEN` on an actuation-capable service | Yes — `iot-gateway` and `factory-control` |
| A `changeme` / literal / defaulted MQTT password | Yes — `MQTT_ADMIN_PASSWORD`, `MQTT_GW_PASSWORD`, `MQTT_BRIDGE_PASSWORD` |
| A published plaintext broker port (1883) | Yes |
| A non-TLS production MQTT listener (`MQTT_TLS_ONLY` not true) | Yes |
| A production image referenced by a floating tag rather than a digest | Yes |
| A production service that is not digest-pinned at all | Yes |
| A broker entrypoint that does not write an `acl_file` / `password_file` | Yes |
| A broker entrypoint that sets `allow_anonymous true` | Yes |
| A broker entrypoint that does not support a TLS-only listener | Yes |
| A broker TLS/ACL mount that is not repository-relative and therefore not verifiable | Yes |

The last four rows are additions made by this card. Previously the guard only
checked that the entrypoint and TLS material were *mounted*; it did not check
that the mounted script actually implements an authorisation boundary, so a
compliant-looking Compose file could have mounted a permissive entrypoint.

---

## 5. Orion-LD / MongoDB version compatibility

The pinned pair is `quay.io/fiware/orion-ld:1.5.0` +
`mongo:4.4@sha256:4be76f674fc4b27859816811b8baa3c51830eb1dbf4ca81a51e26b79edd662ef`.

- **Verified directly in the pinned Orion-LD image:** the image ships
  `/usr/lib/x86_64-linux-gnu/libmongoclient.a` with the legacy
  `mongo::DBClientWithCommands` symbols, and ships **no** `libmongocxx` /
  `libbsoncxx`. Orion-LD 1.5.0 therefore speaks the legacy `OP_QUERY` wire
  protocol.
- **Documented server boundary:** MongoDB *deprecated* the legacy opcodes in
  5.0 and *removed* them in 5.1
  (<https://www.mongodb.com/docs/manual/legacy-opcodes> — "Deprecated as of
  MongoDB 5.0. Unsupported as of MongoDB 5.1."). A 5.1+ server makes the
  broker log `Unsupported OP_QUERY command: listDatabases` followed by
  `mongo::MsgAssertionException`, and it never becomes ready.
- **Conclusion:** MongoDB 4.4 sits safely below that removal boundary and is
  the tested pairing for the pinned Orion-LD digest. Upgrading either
  component requires re-pinning **both** digests and re-running the L2
  simulation; changing one side alone is not a supported configuration.
- **Data volume:** the MongoDB volume must have been created by a 4.x server.
  A volume previously initialised by 7.0 carries
  `featureCompatibilityVersion 7.0` and makes 4.4 refuse to start. Recreate
  the volume when downgrading.

---

## 6. MQTT broker path: TLS on 8883 with ACL enforcement

### TLS

- The `mqtt` service publishes **only** `8883:8883`, bound to
  `${MQTT_TLS_BIND:-127.0.0.1}`. No plaintext port (1883) is published in
  any profile.
- `MQTT_TLS_ENABLED=true` and `MQTT_TLS_ONLY=true` are set in the service
  environment. The broker entrypoint emits a TLS-only listener and drops the
  plaintext listener entirely when `MQTT_TLS_ONLY=true`.
- Every production client service (`iot-gateway`, `factory-control`,
  `factory-control-readonly`, `edge-ai-robot`) uses `MQTT_PORT=8883` with
  `MQTT_TLS_ENABLED=true`; the guard rejects any of them that does not.

### ACL enforcement

- The broker is configured by `infrastructure/mqtt-broker/entrypoint.d/init.sh`,
  which is mounted read-only into the container and is the Compose
  `entrypoint:`. It writes `mosquitto.conf` with `acl_file`, `password_file`
  and `allow_anonymous false`, and writes the ACL and password files at
  container start from the operator-supplied credentials.
- The guard now inspects the mounted entrypoint's content and fails closed if
  it stops writing an `acl_file` / `password_file`, sets
  `allow_anonymous true`, or loses the TLS-only support.

### Operator-supplied artefacts (expected paths, deliberately absent from git)

| Artefact | Expected path | Produced by | In repository? |
|---|---|---|---|
| CA trust anchor | `infrastructure/mqtt-broker/config/tls/ca.crt` | `config/tls/generate-certs.sh` | **No** — gitignored (`.gitignore` line 48) |
| Broker server certificate | `infrastructure/mqtt-broker/config/tls/server.crt` | `config/tls/generate-certs.sh` | **No** — gitignored (`.gitignore` line 48) |
| Broker server private key | `infrastructure/mqtt-broker/config/tls/server.key` | `config/tls/generate-certs.sh` | **No** — gitignored (`.gitignore` line 47) |
| Broker ACL file | `/mosquitto/config/acl` (in the `mqtt-conf` volume) | `entrypoint.d/init.sh` at container start | **No** — generated at runtime |
| Broker password file | `/mosquitto/config/passwd` (in the `mqtt-conf` volume) | `entrypoint.d/init.sh` at container start | **No** — generated at runtime |

The TLS artefacts are absent from the repository **by design** so that private
key material can never be committed. The broker entrypoint fails closed when
TLS is enabled but the certificate files are missing: it exits `1` with
`TLS enabled but certificate files missing: ca.crt ...` rather than starting a
broker without a trust chain.

### Divergence from ADR-0010 (reported, not silently changed)

`docs/adr/adr-0010-mqtt-broker-security.md` is **Status: Proposed**. Its
enforcement table deliberately excludes the heartbeat topic:

> Heartbeat is not included because the current bridge MQTT contract does not
> define a heartbeat topic.

The implemented ACL in `init.sh` grants the gateway credential
`topic read smart-factory/+/heartbeat`, and the gateway does subscribe to
`smart-factory/+/heartbeat` (`iot-gateway/src/iot_gateway/config.py`). This is
a **wider** grant than the ADR table describes.

This card does not change it: ADR-0010 explicitly says the heartbeat topic
"requires a separate accepted decision before inclusion", and that decision is
the maintainers' to make, not a side effect of a pinning card. It is recorded
here so that the reviewer can either accept the heartbeat subscription as
within the ADR-0010 proposal (it is read-only ingestion of a bridge-origin
topic, and the ADR itself notes PR #100 proposed adding it) or raise a
follow-up to align the ADR table with the implementation. This is reported
deliberately rather than papered over.

---

## 7. Commands actually run

All commands were run from the repository root on the branch
`feat/issue-182-deployment-e2e`.

```console
$ python scripts/check_production_compose.py docker-compose.full.yml
PASS: docker-compose.full.yml satisfies production compose security invariants
(exit code 0)

$ python -m pytest scripts/tests/test_check_production_compose.py -q
......................                                                   [100%]
22 passed in 1.03s

$ python scripts/check_adrs.py
ℹ️ Architecture modified without ADR, but bypassed via commit message marker
✅ ADR Lint / Governance Gate PASSED (15 ADRs validated successfully).
(exit code 0)

$ python -m pytest scripts/tests/ -q
............................                                             [100%]
28 passed in 1.13s
```

A deliberate negative control was also run against a mutated copy of the
Compose file (wildcard CORS, floating `mongo:4.4` tag, empty operator token,
`changeme` MQTT password, `MQTT_TLS_ONLY=false`, published `1883:1883`).
The guard exited `1` and reported every one of those defects:

```console
FAIL: orion-ld must require a non-wildcard ORION_LD_CORS_ORIGINS
FAIL: mqtt must require a non-default MQTT_GW_PASSWORD
FAIL: mqtt must not publish a plaintext broker port
FAIL: mqtt must enable TLS-only access on port 8883
FAIL: mongodb must pin its image by digest, not by a floating tag: mongo:4.4
FAIL: iot-gateway must require SAFETY_OPERATOR_TOKEN
FAIL: factory-control must require SAFETY_OPERATOR_TOKEN
```

No Docker Compose teardown (`down -v --remove-orphans`) was performed. The
only containers started were two single-shot `docker run --rm` containers used
to inspect the pinned image contents and to confirm the digest pull.

---

## 8. Summary statement for the PR

> The production-profile container images in `docker-compose.full.yml` are
> pinned to OCI manifest digests resolved from the real registries and
> cross-checked by hashing the manifest bodies the registries served. The
> compose security guard fails closed on permissive production defaults,
> including wildcard CORS, empty or defaulted actuation tokens, default MQTT
> passwords, plaintext broker ports, unpinned images, and a broker entrypoint
> that would not enforce an ACL. The MQTT broker path is TLS-only on 8883
> with ACL and password files generated at container start by the mounted
> entrypoint; the certificate material and the ACL file are operator-supplied
> and their expected paths are recorded above.
>
> This evidence is **L1 (static)**. The Compose/Mongo/Orion exercise is a
> **L2 simulation** only. It is **not** a lifecycle rehearsal, **not**
> physical control-isolation proof, **not** HIL (L4), and **not**
> production-rollout acceptance. Nothing here constitutes production
> authorisation.
