You are a technical documentation writer. Generate comprehensive, public-facing documentation for the "FinOps Operator" — a Kubernetes operator that manages Dex OIDC configurations through Custom Resources (CRDs). The documentation should be structured as a documentation site (like a GitBook, Docusaurus, or MkDocs site) with the following sections and content. Use clear, professional language. Include YAML examples throughout.

---

## Project Context

FinOps Operator is a Kubernetes operator (API group: `auth.stakater.com/v1alpha1`) that provides a declarative, GitOps-friendly way to manage Dex OIDC server configuration. Instead of manually editing Dex's config.yaml, users define Kubernetes Custom Resources. The operator collects all CRDs and referenced Secrets, generates a complete Dex config.yaml, stores it in a Kubernetes Secret, and automatically triggers a rolling restart of the Dex deployment.

All sensitive data (OAuth client secrets, database passwords, connector credentials, user password hashes) is stored in Kubernetes Secrets — never in CRDs directly.

---

## Documentation Structure

### 1. Introduction / Overview
- What is FinOps Operator and what problem it solves
- High-level architecture diagram (ASCII or Mermaid):
  - DexConfig, Connector, Client, LocalUser CRDs feed into a Config Manager
  - Config Manager generates config.yaml → stores in a Kubernetes Secret → triggers Dex deployment rolling restart
  - Secret Controller watches referenced secrets and triggers re-reconciliation on changes
- Key features:
  - Security-first: all sensitive data in Kubernetes Secrets
  - Event-driven: automatic config updates on CRD or Secret changes
  - Auto-restart: rolling restart of Dex deployment on config changes
  - Secret watching: monitors referenced secrets, regenerates config on change
  - Comprehensive validation with detailed status conditions
  - Abstraction layer enabling future support for non-Dex OIDC providers
  - Multiple storage backends: Kubernetes, PostgreSQL, MySQL, SQLite3, memory
  - Namespace-scoped or cluster-wide CRD watching
  - Enable/disable individual resources without deletion

### 2. Getting Started / Quick Start Guide
- Prerequisites: Go 1.24+, Docker 17.03+, kubectl v1.11.3+, Kubernetes cluster v1.11.3+
- Installation options:
  - Via Helm chart (`charts/dex-config-operator/`)
  - Via kustomize (`make deploy IMG=<registry>/dex-config-operator:tag`)
  - Via raw manifests (`kubectl apply -f dist/install.yaml`)
- Quick start walkthrough:
  1. Install CRDs (`make install`)
  2. Deploy operator
  3. Create a DexConfig resource with Kubernetes storage
  4. Create a Connector (e.g., Google OAuth) with its Secret
  5. Create a Client
  6. Verify generated config: `kubectl get secret dex -n dex -o jsonpath='{.data.config\.yaml}' | base64 -d`
  7. Check resource statuses: `kubectl get dexconfigs`, `kubectl get connectors`, etc.

### 3. Concepts
- **Configuration Flow**: User creates CRD → Controller validates → Config Manager collects all CRDs + Secrets → Dex Manager generates config.yaml → Secret updated → Dex deployment restarted
- **Secret References**: All CRDs reference Kubernetes Secrets via `SecretReference` (name, namespace, key) or `SecretKeyReference`. The operator labels watched secrets with `dex-config-operator.stakater.com/watch: "true"` for efficient selective watching.
- **Status Conditions**: Every CRD reports 4 condition types:
  - `Ready` — overall readiness
  - `SecretResolved` — all referenced secrets found
  - `ConfigurationValid` — configuration passes validation
  - `Synced` — config synced to Dex secret
- **Phases**: Each resource moves through `Pending` → `Ready` or `Failed`
- **Enable/Disable**: Connectors, Clients, and LocalUsers have an `enabled` field (default: true). Setting to false excludes the resource from generated config without deleting it.
- **Singleton DexConfig**: Only one DexConfig resource is allowed per cluster. The controller enforces this.

### 4. Guides

#### 4.1 Setting Up Dex with Kubernetes Storage
- Simplest setup: DexConfig with `storage.type: kubernetes` and `config: { inCluster: true }`
- Full example YAML:
```yaml
apiVersion: auth.stakater.com/v1alpha1
kind: DexConfig
metadata:
  name: dex-config
spec:
  issuer: https://dex.example.com
  storage:
    type: kubernetes
    config:
      inCluster: true
  web:
    http: 0.0.0.0:5556
  oauth2:
    skipApprovalScreen: true
  expiry:
    signingKeys: "6h"
    idTokens: "24h"
  logger:
    level: info
    format: text
```

#### 4.2 Setting Up Dex with PostgreSQL Storage
- Create a Secret with keys: `POSTGRESQL_DATABASE`, `POSTGRESQL_USER`, `POSTGRESQL_PASSWORD`, `POSTGRESQL_PORT`, `POSTGRESQL_SERVICE`, `POSTGRESQL_SSL`
- DexConfig with `storage.type: postgres` and `storage.configSecretRef` pointing to the secret
- Full example YAML:
```yaml
apiVersion: auth.stakater.com/v1alpha1
kind: DexConfig
metadata:
  name: dex-config
spec:
  issuer: https://dex.example.com
  storage:
    type: postgres
    configSecretRef:
      name: postgres-credentials
---
apiVersion: v1
kind: Secret
metadata:
  name: postgres-credentials
type: Opaque
stringData:
  POSTGRESQL_DATABASE: dex
  POSTGRESQL_USER: dexuser
  POSTGRESQL_PASSWORD: password123
  POSTGRESQL_PORT: "5432"
  POSTGRESQL_SERVICE: postgres.default.svc.cluster.local
  POSTGRESQL_SSL: disable
```

#### 4.3 Setting Up Dex with MySQL Storage
- Same pattern as PostgreSQL but with `MYSQL_*` keys
- DexConfig with `storage.type: mysql`
- Full example YAML:
```yaml
apiVersion: auth.stakater.com/v1alpha1
kind: DexConfig
metadata:
  name: dex-config
spec:
  issuer: https://dex.example.com
  storage:
    type: mysql
    configSecretRef:
      name: mysql-credentials
---
apiVersion: v1
kind: Secret
metadata:
  name: mysql-credentials
type: Opaque
stringData:
  MYSQL_DATABASE: dex
  MYSQL_USER: dexuser
  MYSQL_PASSWORD: password123
  MYSQL_PORT: "3306"
  MYSQL_SERVICE: mysql.default.svc.cluster.local
```

#### 4.4 Configuring an OIDC Connector (e.g., Keycloak)
- Create a Secret containing base64-encoded JSON config with fields: `issuer`, `clientID`, `clientSecret`, `redirectURI`, `scopes`
- Create a Connector CR with `type: oidc`, referencing the secret
- Explain the configSecretRef key field (defaults to "config")
- Full example YAML:
```yaml
apiVersion: auth.stakater.com/v1alpha1
kind: Connector
metadata:
  name: keycloak
spec:
  type: oidc
  id: keycloak
  name: Corporate SSO
  configSecretRef:
    name: keycloak-connector-config
  enabled: true
---
apiVersion: v1
kind: Secret
metadata:
  name: keycloak-connector-config
type: Opaque
data:
  # Base64-encoded JSON:
  # {"issuer": "https://keycloak.example.com/realms/myrealm", "clientID": "dex-client", "clientSecret": "your-secret", "redirectURI": "https://dex.example.com/callback", "scopes": ["openid", "profile", "email", "groups"]}
  config: eyJpc3N1ZXIiOiAiaHR0cHM6Ly9rZXljbG9hay5leGFtcGxlLmNvbS9yZWFsbXMvbXlyZWFsbSIsICJjbGllbnRJRCI6ICJkZXgtY2xpZW50IiwgImNsaWVudFNlY3JldCI6ICJ5b3VyLXNlY3JldCIsICJyZWRpcmVjdFVSSSI6ICJodHRwczovL2RleC5leGFtcGxlLmNvbS9jYWxsYmFjayIsICJzY29wZXMiOiBbIm9wZW5pZCIsICJwcm9maWxlIiwgImVtYWlsIiwgImdyb3VwcyJdfQ==
```

#### 4.5 Configuring a Google OAuth Connector
- Required fields in secret: `clientID`, `clientSecret`, `redirectURI`
- Full example YAML:
```yaml
apiVersion: auth.stakater.com/v1alpha1
kind: Connector
metadata:
  name: google
spec:
  type: google
  id: google
  name: Google
  configSecretRef:
    name: google-config
  enabled: true
---
apiVersion: v1
kind: Secret
metadata:
  name: google-config
type: Opaque
data:
  # Base64-encoded JSON: {"clientID": "your-google-client-id", "clientSecret": "your-secret", "redirectURI": "https://dex.example.com/callback"}
  config: eyJjbGllbnRJRCI6ICJ5b3VyLWdvb2dsZS1jbGllbnQtaWQiLCAiY2xpZW50U2VjcmV0IjogInlvdXItc2VjcmV0IiwgInJlZGlyZWN0VVJJIjogImh0dHBzOi8vZGV4LmV4YW1wbGUuY29tL2NhbGxiYWNrIn0=
```

#### 4.6 Configuring a SAML Connector
- Complex config including certificates, attribute mappings, group filtering
- Full example YAML showing a SAML connector with:
  - `ssoURL`, `ca` (certificate), `redirectURI`, `entityIssuer`
  - `usernameAttr`, `emailAttr`, `groupsAttr`
  - `nameIDPolicyFormat`
  - All stored as base64-encoded JSON in the secret

#### 4.7 Configuring an LDAP Connector
- Example with host, bind DN, user/group search configuration
- Full example YAML showing an LDAP connector with:
  - `host`, `insecureNoSSL`, `insecureSkipVerify`
  - `bindDN`, `bindPW`
  - `userSearch`: `baseDN`, `filter`, `username`, `idAttr`, `emailAttr`, `nameAttr`
  - `groupSearch`: `baseDN`, `filter`, `userMatchers`

#### 4.8 Configuring OAuth2 Clients
- Public clients (SPAs, mobile apps): `public: true`, no secretRef needed
- Confidential clients (server apps): `public: false`, secretRef required
- Trusted peers for token sharing between clients
- Full example YAMLs:

**Public Client:**
```yaml
apiVersion: auth.stakater.com/v1alpha1
kind: Client
metadata:
  name: spa-app
spec:
  id: spa-app
  name: "Single Page Application"
  redirectURIs:
    - "http://localhost:3000/callback"
  public: true
  enabled: true
```

**Confidential Client:**
```yaml
apiVersion: auth.stakater.com/v1alpha1
kind: Client
metadata:
  name: backend-app
spec:
  id: backend-app
  name: "Backend Application"
  redirectURIs:
    - "https://app.example.com/callback"
  public: false
  secretRef:
    name: backend-app-secret
    key: secret
  trustedPeers: ["spa-app"]
  logoURL: "https://app.example.com/logo.png"
  enabled: true
---
apiVersion: v1
kind: Secret
metadata:
  name: backend-app-secret
type: Opaque
stringData:
  secret: "your-client-secret"
```

#### 4.9 Managing Local Users
- Two credential secret formats:
  - Structured: single key containing JSON/YAML with username, email, password (bcrypt hash), groups
  - Flat keys: individual secret keys for username, email, password, groups (comma-separated or JSON array)
- How to generate bcrypt password hashes:
  - `htpasswd -bnBC 10 "" your-password | tr -d ':\n'`
  - `python3 -c 'import bcrypt; print(bcrypt.hashpw(b"your-password", bcrypt.gensalt()).decode())'`
- Enabling passwordDB: happens automatically when any enabled LocalUser exists
- Full example YAML for both formats:

**Structured JSON (with key specified):**
```yaml
apiVersion: auth.stakater.com/v1alpha1
kind: LocalUser
metadata:
  name: admin
spec:
  userID: "1"
  credentialSecretRef:
    name: admin-credentials
    key: credentials
  enabled: true
---
apiVersion: v1
kind: Secret
metadata:
  name: admin-credentials
type: Opaque
stringData:
  credentials: |
    {
      "username": "admin",
      "email": "admin@example.com",
      "password": "$2y$10$gVWVjtNeh7yqvatJyQ6q1O50N0Yy9WqyMIQC3qDxbYmljNAumfeH2",
      "groups": ["admins", "users"]
    }
```

**Flat keys (without key specified):**
```yaml
apiVersion: auth.stakater.com/v1alpha1
kind: LocalUser
metadata:
  name: admin
spec:
  userID: "1"
  credentialSecretRef:
    name: admin-credentials-flat
  enabled: true
---
apiVersion: v1
kind: Secret
metadata:
  name: admin-credentials-flat
type: Opaque
stringData:
  username: admin
  email: admin@example.com
  password: "$2y$10$gVWVjtNeh7yqvatJyQ6q1O50N0Yy9WqyMIQC3qDxbYmljNAumfeH2"
  groups: "admins,users"
```

#### 4.10 Multi-Environment Connector Configuration
- Using a single Secret with multiple keys for dev/prod configs
- Multiple Connector CRs referencing different keys in the same secret
- Full example YAML:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: keycloak-configs
type: Opaque
data:
  dev-config: <base64-encoded-dev-JSON>
  prod-config: <base64-encoded-prod-JSON>
---
apiVersion: auth.stakater.com/v1alpha1
kind: Connector
metadata:
  name: keycloak-dev
spec:
  type: oidc
  id: keycloak-dev
  name: "Keycloak Dev"
  configSecretRef:
    name: keycloak-configs
    key: dev-config
---
apiVersion: auth.stakater.com/v1alpha1
kind: Connector
metadata:
  name: keycloak-prod
spec:
  type: oidc
  id: keycloak-prod
  name: "Keycloak Prod"
  configSecretRef:
    name: keycloak-configs
    key: prod-config
```

#### 4.11 Frontend Customization
- FrontendSpec fields: issuer (display name), logoURL, theme (light/dark/auto), dir (static assets path), extra (raw JSON)
- Full example YAML:
```yaml
apiVersion: auth.stakater.com/v1alpha1
kind: DexConfig
metadata:
  name: dex-config
spec:
  issuer: https://dex.example.com
  storage:
    type: kubernetes
    config:
      inCluster: true
  frontend:
    issuer: "My Company SSO"
    logoURL: "https://example.com/logo.png"
    theme: dark
```

#### 4.12 Token Expiry Configuration
- Configure signing key rotation (`signingKeys`), ID token lifetime (`idTokens`), auth request lifetime (`authRequests`), device request lifetime (`deviceRequests`)
- Refresh token settings: `validIfNotUsedFor`, `absoluteLifetime`, `reuseInterval`, `disableRotation`
- Full example YAML:
```yaml
apiVersion: auth.stakater.com/v1alpha1
kind: DexConfig
metadata:
  name: dex-config
spec:
  issuer: https://dex.example.com
  storage:
    type: kubernetes
    config:
      inCluster: true
  expiry:
    signingKeys: "6h"
    idTokens: "24h"
    authRequests: "24h"
    deviceRequests: "5m"
    refreshTokens:
      validIfNotUsedFor: "720h"
      absoluteLifetime: "8760h"
      reuseInterval: "30s"
      disableRotation: false
```

#### 4.13 Namespace-Scoped vs Cluster-Wide Operation
- Default: watches all namespaces for Connectors, Clients, LocalUsers
- `--watch-namespace=<ns>` for single-namespace operation
- DexConfig is always watched globally
- Use cases for each mode

#### 4.14 Disabling Automatic Dex Restart
- Set `--dex-namespace` and `--dex-deployment-name` to empty strings
- Alternative: use Stakater Reloader for production environments
- Show Reloader annotation example:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dex
  annotations:
    secret.reloader.stakater.com/reload: "dex-config"
```

#### 4.15 Complete Production Setup Example
- Full end-to-end example with PostgreSQL storage, Keycloak OIDC connector, a confidential client, and an admin local user:
```yaml
# 1. Global Dex Configuration
apiVersion: auth.stakater.com/v1alpha1
kind: DexConfig
metadata:
  name: production-dex
spec:
  issuer: https://dex.mycompany.com
  storage:
    type: postgres
    configSecretRef:
      name: dex-postgres-config
  web:
    http: 0.0.0.0:5556
  oauth2:
    skipApprovalScreen: false
  expiry:
    signingKeys: "6h"
    idTokens: "24h"
  logger:
    level: info
    format: json
---
# 2. Database credentials
apiVersion: v1
kind: Secret
metadata:
  name: dex-postgres-config
type: Opaque
stringData:
  POSTGRESQL_DATABASE: dex
  POSTGRESQL_USER: dexuser
  POSTGRESQL_PASSWORD: super-secret-password
  POSTGRESQL_PORT: "5432"
  POSTGRESQL_SERVICE: postgres.database.svc.cluster.local
  POSTGRESQL_SSL: require
---
# 3. Keycloak OIDC Connector
apiVersion: auth.stakater.com/v1alpha1
kind: Connector
metadata:
  name: keycloak
spec:
  type: oidc
  id: keycloak
  name: Corporate SSO
  configSecretRef:
    name: keycloak-connector-config
  enabled: true
---
apiVersion: v1
kind: Secret
metadata:
  name: keycloak-connector-config
type: Opaque
data:
  config: eyJpc3N1ZXIiOiAiaHR0cHM6Ly9rZXljbG9hay5teWNvbXBhbnkuY29tL3JlYWxtcy9teXJlYWxtIiwgImNsaWVudElEIjogImRleC1jbGllbnQiLCAiY2xpZW50U2VjcmV0IjogInlvdXItc2VjcmV0IiwgInJlZGlyZWN0VVJJIjogImh0dHBzOi8vZGV4Lm15Y29tcGFueS5jb20vY2FsbGJhY2siLCAic2NvcGVzIjogWyJvcGVuaWQiLCAicHJvZmlsZSIsICJlbWFpbCIsICJncm91cHMiXX0=
---
# 4. Application Client
apiVersion: auth.stakater.com/v1alpha1
kind: Client
metadata:
  name: myapp
spec:
  id: myapp
  name: My Application
  redirectURIs:
    - https://myapp.mycompany.com/callback
  public: false
  secretRef:
    name: myapp-secret
  logoURL: https://myapp.mycompany.com/logo.png
  enabled: true
---
apiVersion: v1
kind: Secret
metadata:
  name: myapp-secret
type: Opaque
stringData:
  secret: my-app-client-secret
---
# 5. Admin User
apiVersion: auth.stakater.com/v1alpha1
kind: LocalUser
metadata:
  name: admin
spec:
  userID: "1"
  credentialSecretRef:
    name: admin-credentials
    key: credentials
  enabled: true
---
apiVersion: v1
kind: Secret
metadata:
  name: admin-credentials
type: Opaque
stringData:
  credentials: |
    {
      "username": "admin",
      "email": "admin@mycompany.com",
      "password": "$2y$10$gVWVjtNeh7yqvatJyQ6q1O50N0Yy9WqyMIQC3qDxbYmljNAumfeH2",
      "groups": ["admins", "users"]
    }
```

### 5. CRD Reference

For each CRD, provide a complete field reference in table format with: Field Path, Type, Required/Optional, Default Value, Validation Rules, Description.

#### 5.1 DexConfig
- API: `auth.stakater.com/v1alpha1`
- Kind: `DexConfig`
- Scope: Namespaced (but only one allowed per cluster)
- Print columns: Issuer, Phase, Age
- **Spec fields:**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `issuer` | string | Yes | - | Pattern: `^https?://.*` | The canonical URL of the OpenID Connect service. All clients must use this URL to refer to dex. |
| `storage` | StorageSpec | Yes | - | - | Configures the storage backend for Dex. |
| `storage.type` | string | Yes | `kubernetes` | Enum: `kubernetes`, `postgres`, `mysql`, `sqlite3`, `memory` | Storage backend type. |
| `storage.config` | raw JSON | No | - | PreserveUnknownFields | Inline storage configuration. For kubernetes: `{"inCluster": true}`. |
| `storage.configSecretRef` | SecretReference | No | - | - | References a secret containing database credentials. Takes precedence over inline config if both specified. |
| `web` | WebSpec | No | - | - | HTTP/HTTPS server configuration. |
| `web.http` | string | No | - | - | HTTP listen address (e.g., `0.0.0.0:5556`). |
| `web.https` | string | No | - | - | HTTPS listen address (e.g., `0.0.0.0:5554`). |
| `web.tlsCert` | string | No | - | - | Path to TLS certificate file. |
| `web.tlsKey` | string | No | - | - | Path to TLS private key file. |
| `web.allowedOrigins` | []string | No | - | - | List of allowed CORS origins. |
| `grpc` | GRPCSpec | No | - | - | gRPC API server configuration. |
| `grpc.addr` | string | No | - | - | gRPC server listen address. |
| `grpc.tlsCert` | string | No | - | - | Path to TLS certificate file for gRPC. |
| `grpc.tlsKey` | string | No | - | - | Path to TLS private key file for gRPC. |
| `grpc.tlsClientCA` | string | No | - | - | Path to TLS client CA file for mTLS. |
| `grpc.reflection` | bool | No | false | - | Enables gRPC server reflection. |
| `telemetry` | TelemetrySpec | No | - | - | Telemetry/metrics server configuration. |
| `telemetry.http` | string | No | - | - | HTTP listen address for telemetry (e.g., `0.0.0.0:5558`). |
| `oauth2` | OAuth2Spec | No | - | - | OAuth2-specific behavior configuration. |
| `oauth2.skipApprovalScreen` | bool | No | false | - | Skips the OAuth2 approval/consent screen. |
| `oauth2.alwaysShowLoginScreen` | bool | No | false | - | Forces the login screen to always be shown. |
| `oauth2.passwordConnector` | string | No | - | - | Specifies which connector to use for password grants. |
| `oauth2.responseTypes` | []string | No | - | - | Allowed OAuth2 response types (e.g., `["code", "token", "id_token"]`). |
| `expiry` | ExpirySpec | No | - | - | Token expiry configuration. |
| `expiry.signingKeys` | string | No | `"6h"` | - | How long signing keys are valid. |
| `expiry.idTokens` | string | No | `"24h"` | - | How long ID tokens are valid. |
| `expiry.authRequests` | string | No | - | - | How long authorization requests are valid. |
| `expiry.deviceRequests` | string | No | - | - | How long device authorization requests are valid. |
| `expiry.refreshTokens` | RefreshTokenExpirySpec | No | - | - | Refresh token expiry configuration. |
| `expiry.refreshTokens.validIfNotUsedFor` | string | No | - | - | How long a refresh token is valid if not used. |
| `expiry.refreshTokens.absoluteLifetime` | string | No | - | - | Absolute lifetime of a refresh token. |
| `expiry.refreshTokens.reuseInterval` | string | No | - | - | Interval for which a refresh token can be reused. |
| `expiry.refreshTokens.disableRotation` | bool | No | false | - | Disables refresh token rotation. |
| `logger` | LoggerSpec | No | - | - | Logging configuration. |
| `logger.level` | string | No | `info` | Enum: `debug`, `info`, `error` | Log level. |
| `logger.format` | string | No | `text` | Enum: `text`, `json` | Log output format. |
| `frontend` | FrontendSpec | No | - | - | Web UI customization. |
| `frontend.issuer` | string | No | - | - | Display name of the issuer in the UI. |
| `frontend.logoURL` | string | No | - | - | URL to a logo to display. |
| `frontend.theme` | string | No | - | - | CSS theme (`light`, `dark`, `auto`). |
| `frontend.dir` | string | No | - | - | Directory path to serve static frontend assets from. |
| `frontend.extra` | raw JSON | No | - | PreserveUnknownFields | Any additional frontend configuration as raw JSON. |
| `enablePasswordDB` | bool | No | false | - | Enables static password authentication. Automatically set to true when any enabled LocalUser exists. |

- **Status fields:**

| Field | Type | Description |
|-------|------|-------------|
| `conditions` | []metav1.Condition | Latest observations of the DexConfig's current state (Ready, Synced). |
| `observedGeneration` | int64 | Generation of the most recently observed DexConfig. |
| `phase` | string | Current phase: `Pending`, `Ready`, or `Failed`. |
| `message` | string | Human-readable details about the current state. |
| `lastUpdated` | *metav1.Time | Timestamp of last status update. |
| `appliedConfiguration` | bool | Whether this config has been applied to the Dex secret. |

- **Database Secret Key Reference (for storage.configSecretRef):**

| Backend | Secret Keys |
|---------|-------------|
| PostgreSQL | `POSTGRESQL_DATABASE`, `POSTGRESQL_USER`, `POSTGRESQL_PASSWORD`, `POSTGRESQL_PORT`, `POSTGRESQL_SERVICE`, `POSTGRESQL_SSL` |
| MySQL | `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_PORT`, `MYSQL_SERVICE`, `MYSQL_SSL` |

#### 5.2 Connector
- API: `auth.stakater.com/v1alpha1`
- Kind: `Connector`
- Scope: Namespaced
- **Spec fields:**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `type` | string | Yes | - | Enum: `oidc`, `google`, `saml`, `ldap`, `github`, `gitlab`, `bitbucket`, `microsoft` | The type of authentication connector. |
| `id` | string | Yes | - | Pattern: `^[a-z0-9]([-a-z0-9]*[a-z0-9])?$` | Unique identifier for this connector. Must be DNS-subdomain-style. |
| `name` | string | Yes | - | - | Human-readable display name shown in the Dex login UI. |
| `configSecretRef` | SecretReference | Yes | - | - | References a Kubernetes Secret containing the connector configuration as base64-encoded JSON. |
| `configSecretRef.name` | string | Yes | - | - | Name of the Kubernetes Secret. |
| `configSecretRef.namespace` | string | No | CR namespace | - | Namespace of the Secret. Defaults to the Connector's namespace. |
| `configSecretRef.key` | string | No | `"config"` | - | Key within the Secret that holds the base64-encoded JSON config. |
| `enabled` | *bool | No | true | - | Whether this connector is included in the generated Dex configuration. |

- **Status fields:**

| Field | Type | Description |
|-------|------|-------------|
| `conditions` | []metav1.Condition | Conditions: SecretResolved, ConfigurationValid, Ready, Synced. |
| `observedGeneration` | int64 | Generation of the most recently observed Connector. |
| `phase` | string | Current phase: `Pending`, `Ready`, or `Failed`. |
| `message` | string | Human-readable details about the current state. |
| `lastUpdated` | *metav1.Time | Timestamp of last status update. |

- **Type-specific required config fields (in the secret JSON):**

| Connector Type | Required Fields | Optional Fields |
|---------------|----------------|-----------------|
| `oidc` | `issuer`, `clientID` | `clientSecret`, `redirectURI`, `scopes`, `userIDKey`, `userNameKey`, `insecureSkipEmailVerified` |
| `google` | `clientID`, `clientSecret` | `redirectURI`, `hostedDomains`, `groups`, `serviceAccountFilePath`, `adminEmail` |
| `saml` | (validated at Dex level) | `ssoURL`, `ca`, `redirectURI`, `entityIssuer`, `usernameAttr`, `emailAttr`, `groupsAttr` |
| `ldap` | (validated at Dex level) | `host`, `bindDN`, `bindPW`, `userSearch`, `groupSearch`, `insecureNoSSL` |
| `github` | (validated at Dex level) | `clientID`, `clientSecret`, `redirectURI`, `orgs`, `teamNameField` |
| `gitlab` | (validated at Dex level) | `clientID`, `clientSecret`, `redirectURI`, `baseURL`, `groups` |
| `bitbucket` | (validated at Dex level) | `clientID`, `clientSecret`, `redirectURI`, `teams` |
| `microsoft` | (validated at Dex level) | `clientID`, `clientSecret`, `redirectURI`, `tenant`, `groups`, `onlySecurityGroups` |

#### 5.3 Client
- API: `auth.stakater.com/v1alpha1`
- Kind: `Client`
- Scope: Namespaced
- **Spec fields:**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `id` | string | Yes | - | Pattern: `^[a-zA-Z0-9._-]+$` | OAuth2 client identifier. |
| `name` | string | Yes | - | - | Human-readable display name for this client. |
| `redirectURIs` | []string | Yes | - | MinItems: 1 | List of allowed redirect URIs. At least one required. |
| `public` | *bool | No | false | - | Whether this is a public client (no secret required). Set true for SPAs and mobile apps. |
| `secretRef` | SecretKeyReference | No | - | Required if `public` is false | References a Secret containing the client secret. |
| `secretRef.name` | string | Yes | - | - | Name of the Kubernetes Secret. |
| `secretRef.namespace` | string | No | CR namespace | - | Namespace of the Secret. |
| `secretRef.key` | string | No | `"secret"` | - | Key within the Secret containing the client secret string. |
| `trustedPeers` | []string | No | - | - | List of other client IDs that can exchange tokens with this client. |
| `logoURL` | string | No | - | - | URL to a logo image for this client. |
| `enabled` | *bool | No | true | - | Whether this client is included in the generated Dex configuration. |

- **Status fields:**

| Field | Type | Description |
|-------|------|-------------|
| `conditions` | []metav1.Condition | Conditions: SecretResolved, ConfigurationValid, Ready, Synced. |
| `observedGeneration` | int64 | Generation of the most recently observed Client. |
| `phase` | string | Current phase: `Pending`, `Ready`, or `Failed`. |
| `message` | string | Human-readable details about the current state. |
| `lastUpdated` | *metav1.Time | Timestamp of last status update. |

#### 5.4 LocalUser
- API: `auth.stakater.com/v1alpha1`
- Kind: `LocalUser`
- Scope: Namespaced
- **Spec fields:**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `userID` | string | Yes | - | - | Unique identifier for this user. |
| `credentialSecretRef` | SecretReference | Yes | - | - | References a Secret containing user credentials. |
| `credentialSecretRef.name` | string | Yes | - | - | Name of the Kubernetes Secret. |
| `credentialSecretRef.namespace` | string | No | CR namespace | - | Namespace of the Secret. |
| `credentialSecretRef.key` | string | No | - | - | If specified, reads structured JSON/YAML from this key. If omitted, reads individual keys from the secret. |
| `enabled` | *bool | No | true | - | Whether this user is included in the generated Dex configuration. |

- **Credential fields (stored in the referenced Secret):**

| Field | Required | Description |
|-------|----------|-------------|
| `username` | Yes | User's login username. |
| `email` | Yes | User's email address. |
| `password` | Yes | Bcrypt-hashed password (e.g., `$2y$10$...`). |
| `groups` | No | List of groups. Supports JSON array (`["admin","users"]`) or comma-separated string (`"admin,users"`). |

- **Status fields:**

| Field | Type | Description |
|-------|------|-------------|
| `conditions` | []metav1.Condition | Conditions: SecretResolved, ConfigurationValid, Ready, Synced. |
| `observedGeneration` | int64 | Generation of the most recently observed LocalUser. |
| `phase` | string | Current phase: `Pending`, `Ready`, or `Failed`. |
| `message` | string | Human-readable details about the current state. |
| `lastUpdated` | *metav1.Time | Timestamp of last status update. |

### 6. Operator Configuration Reference

#### 6.1 Command-Line Flags

| Flag | Default | Env Variable | Description |
|------|---------|-------------|-------------|
| `--dex-namespace` | `"dex"` | `DEX_NAMESPACE` | Namespace where the Dex deployment lives. |
| `--dex-deployment-name` | `"dex"` | `DEX_DEPLOYMENT` | Name of the Dex Deployment resource. |
| `--config-secret-name` | `"dex-config"` | `DEX_CONFIG_SECRET` | Name of the Secret that stores the generated Dex config.yaml. |
| `--config-secret-namespace` | (same as dex-namespace) | - | Namespace for the config Secret. |
| `--watch-namespace` | `""` (all) | - | Namespace to watch for CRDs. Empty string means cluster-wide. |
| `--leader-elect` | `false` | - | Enable leader election for HA deployments. |
| `--health-probe-bind-address` | `":8081"` | - | Address for health probe endpoints (`/healthz`, `/readyz`). |
| `--metrics-bind-address` | `"0"` | - | Address for metrics endpoint. `"0"` disables metrics. Use `":8443"` for HTTPS or `":8080"` for HTTP. |
| `--metrics-secure` | `true` | - | Serve metrics over HTTPS. |
| `--enable-http2` | `false` | - | Enable HTTP/2 for webhook and metrics servers. Disabled by default for security. |

#### 6.2 Environment Variables

| Variable | Description |
|----------|-------------|
| `DEX_NAMESPACE` | Overrides the Dex namespace flag. |
| `DEX_DEPLOYMENT` | Overrides the Dex deployment name flag. |
| `DEX_CONFIG_SECRET` | Overrides the config secret name flag. |
| `SECRET_CHANGE_ACTION` | Action on secret change. Default is `PatchDeployment` (rolling update). Alternative: `DeleteDeployment`. |

#### 6.3 Helm Chart Values

| Value | Default | Description |
|-------|---------|-------------|
| `image.repository` | `ghcr.io/stakater/dex-config-operator` | Container image repository. |
| `image.tag` | (chart appVersion) | Container image tag. |
| `resources.limits.cpu` | `500m` | CPU limit. |
| `resources.limits.memory` | `128Mi` | Memory limit. |
| `resources.requests.cpu` | `10m` | CPU request. |
| `resources.requests.memory` | `64Mi` | Memory request. |
| `env.dexConfigSecret` | `dex` | Name of the Dex config secret. |
| `env.dexDeployment` | `dex` | Name of the Dex deployment. |
| `env.dexNamespace` | `dex` | Namespace of the Dex deployment. |
| `env.secretChangeAction` | `""` | Action on secret change (PatchDeployment or DeleteDeployment). |

#### 6.4 RBAC Permissions

The operator requires the following cluster-level permissions:

| API Group | Resources | Verbs |
|-----------|-----------|-------|
| `""` (core) | `secrets` | create, delete, get, list, patch, update, watch |
| `apps` | `deployments` | delete, get, list, patch, update, watch |
| `auth.stakater.com` | `clients`, `connectors`, `dexconfigs`, `localusers` | create, delete, get, list, patch, update, watch |
| `auth.stakater.com` | `clients/status`, `connectors/status`, `dexconfigs/status`, `localusers/status` | get, patch, update |
| `auth.stakater.com` | `clients/finalizers`, `connectors/finalizers`, `dexconfigs/finalizers`, `localusers/finalizers` | update |

Pre-built RBAC roles are provided for end-users:
- **Admin**: Full CRUD on all CRDs
- **Editor**: Create, update, delete CRDs
- **Viewer**: Read-only access to CRDs

### 7. Status & Troubleshooting

#### 7.1 Understanding Status Conditions

Every CRD reports status through standardized conditions:

| Condition Type | Reason Values | Description |
|---------------|---------------|-------------|
| `Ready` | `ReconcileSuccess`, `ReconcileError`, `Disabled` | Overall readiness of the resource. |
| `SecretResolved` | `ReconcileSuccess`, `SecretNotFound`, `SecretKeyNotFound` | Whether all referenced Kubernetes Secrets exist and contain required keys. |
| `ConfigurationValid` | `ReconcileSuccess`, `ConfigurationInvalid`, `ValidationError` | Whether the configuration passes all validation checks. |
| `Synced` | `ReconcileSuccess`, `ReconcileError` | Whether the configuration has been synced to the generated Dex config secret. |

**Inspecting conditions:**
```bash
kubectl get connector <name> -o jsonpath='{.status.conditions}' | jq
kubectl get client <name> -o jsonpath='{.status.conditions}' | jq
kubectl get localuser <name> -o jsonpath='{.status.conditions}' | jq
kubectl get dexconfig <name> -o jsonpath='{.status.conditions}' | jq
```

**Phase lifecycle:**
```
Pending → Ready   (validation succeeds, config synced)
Pending → Failed  (validation error, secret missing)
Ready   → Ready   (re-validated successfully)
Ready   → Failed  (validation or sync error on update)
Failed  → Ready   (error resolved on retry)
```

#### 7.2 Troubleshooting Guide

**Resource stuck in Pending or Failed:**
```bash
# Check resource status and conditions
kubectl describe connector <name>
kubectl describe client <name>
kubectl describe localuser <name>

# Check operator logs
kubectl logs -n dex-config-operator-system deployment/dex-config-operator-controller-manager

# Verify referenced secrets exist
kubectl get secret <secret-name> -o yaml
```

**Dex config not updating:**
```bash
# View the current generated config
kubectl get secret dex -n dex -o jsonpath='{.data.config\.yaml}' | base64 -d

# Verify operator is running
kubectl get pods -n dex-config-operator-system

# Check operator logs for errors
kubectl logs -n dex-config-operator-system deployment/dex-config-operator-controller-manager --tail=100
```

**Dex deployment not restarting after config change:**
```bash
# Verify dex deployment exists with correct name
kubectl get deployment dex -n dex

# Check operator configuration flags
kubectl get deployment dex-config-operator-controller-manager -n dex-config-operator-system -o yaml | grep -A5 args

# Manually restart if needed
kubectl rollout restart deployment/dex -n dex
```

**Secret changes not being detected:**
```bash
# Check if secret has the watch label
kubectl get secret <secret-name> -o yaml | grep "dex-config-operator.stakater.com/watch"

# If missing, force reconciliation by annotating the CRD:
kubectl annotate connector <name> force-sync="$(date +%s)" --overwrite
```

**Multiple DexConfig error:**
```bash
# Only one DexConfig is allowed per cluster
kubectl get dexconfigs --all-namespaces

# Delete extra DexConfig resources
kubectl delete dexconfig <extra-name>
```

**Enable debug logging:**
```yaml
# In DexConfig spec (affects Dex's own logging):
spec:
  logger:
    level: debug
    format: text
```

#### 7.3 Viewing Generated Configuration
```bash
# View the full generated Dex config
kubectl get secret dex -n dex -o jsonpath='{.data.config\.yaml}' | base64 -d

# Optionally validate with Dex CLI
kubectl get secret dex -n dex -o jsonpath='{.data.config\.yaml}' | base64 -d > /tmp/dex-config.yaml
dex serve /tmp/dex-config.yaml --dry-run
```

### 8. Security Model
- **Secrets-first design**: All sensitive data (OAuth credentials, database passwords, client secrets, password hashes) is stored exclusively in Kubernetes Secrets. CRD specs only contain references to Secrets, never sensitive values directly.
- **Secret reference patterns**:
  - `SecretReference`: Used by Connectors and LocalUsers — fields: `name`, `namespace` (optional, defaults to CR namespace), `key` (optional, defaults to `"config"`)
  - `SecretKeyReference`: Used by Clients — fields: `name`, `namespace` (optional), `key` (optional, defaults to `"secret"`)
- **Selective secret watching**: The operator only watches secrets that are labeled with `dex-config-operator.stakater.com/watch: "true"`. Labels are applied automatically when a CRD references a secret.
- **Pod security**: The operator runs with `runAsNonRoot: true`, `seccompProfile: RuntimeDefault`, drops all Linux capabilities, and disables privilege escalation.
- **Cross-namespace references**: Connectors and Clients can reference secrets in different namespaces, enabling central secret management.

### 9. Architecture Deep Dive

For advanced users and contributors who want to understand the internal design:

- **Abstraction layer pattern**:
  ```
  Controllers (reconcile CRDs)
      ↓
  internal/config/Manager (orchestrates config generation)
      ↓
  pkg/config/types/ConfigManager interface
      ↓
  internal/config/dex/Manager (Dex-specific implementation)
      ↓
  Secret (stores generated config.yaml)
  ```
  This interface-based design allows swapping Dex for another OIDC provider without changing controllers.

- **Controller responsibilities**: One controller per CRD type (DexConfig, Connector, Client, LocalUser) plus a Secret controller. Each validates its resource, updates status conditions, and triggers config reconciliation.

- **Config generation pipeline**:
  1. Collect all CRDs (DexConfig + all enabled Connectors, Clients, LocalUsers)
  2. Fetch all referenced Secrets
  3. Build complete DexConfig struct
  4. Serialize to YAML
  5. Create/update the dex-config Secret
  6. If config changed, trigger Dex deployment rolling restart

- **Deployment restart strategy**: The operator patches the Dex Deployment's pod template with a timestamp annotation (`dex-config-operator.stakater.com/restartedAt`), triggering a Kubernetes rolling update.

- **Reconciliation timing**:
  - Immediate: on CRD create/update/delete or watched secret change
  - Periodic: every 10 minutes for drift detection
  - Error retry: 1 minute on reconciliation errors

- **Secret controller and labeling**: Referenced secrets are labeled with `dex-config-operator.stakater.com/watch: "true"` so the Secret controller efficiently watches only relevant secrets. When a secret changes, the controller immediately triggers a full config regeneration.

---

## Formatting Guidelines
- Use Markdown with clear heading hierarchy
- Every concept should have a working YAML example
- Use admonitions/callouts for warnings (e.g., "Only one DexConfig per cluster"), tips, and important notes
- Use tables for field references
- Include `kubectl` commands for verification steps
- Cross-reference between sections (e.g., "See CRD Reference > Connector for all fields")
- Keep language concise and action-oriented
- Target audience: Kubernetes administrators and platform engineers familiar with OIDC concepts
