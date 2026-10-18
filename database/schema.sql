-- ElectroMap — Schema completo de base de datos (PostgreSQL / Railway)
-- Generado: 2026-10-01. Incluye el rediseño a nivel de circuito y canal_acurev.
-- Fuente de verdad: chat de BBDD del proyecto. Cualquier cambio de schema debe pasar por ahí.

CREATE TABLE empresas (
    id              BIGSERIAL PRIMARY KEY,
    nombre          VARCHAR(150) NOT NULL,
    rut             VARCHAR(12),
    contacto_email  VARCHAR(150),
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE clientes (
    id          BIGSERIAL PRIMARY KEY,
    empresa_id  BIGINT NOT NULL REFERENCES empresas(id),
    nombre      VARCHAR(150) NOT NULL,
    activo      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sucursales (
    id          BIGSERIAL PRIMARY KEY,
    cliente_id  BIGINT NOT NULL REFERENCES clientes(id),
    nombre      VARCHAR(100) NOT NULL,
    direccion   VARCHAR(200),
    activo      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE usuarios (
    id              BIGSERIAL PRIMARY KEY,
    empresa_id      BIGINT REFERENCES empresas(id),
    cliente_id      BIGINT REFERENCES clientes(id),
    nombre_usuario  VARCHAR(50) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    rol             VARCHAR(20) NOT NULL,
    puede_editar    BOOLEAN NOT NULL DEFAULT FALSE,
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_rol_valido CHECK (rol IN ('vsc', 'empresa', 'cliente')),
    CONSTRAINT chk_scope_por_rol CHECK (
        (rol = 'vsc'     AND empresa_id IS NULL     AND cliente_id IS NULL) OR
        (rol = 'empresa' AND empresa_id IS NOT NULL AND cliente_id IS NULL) OR
        (rol = 'cliente' AND cliente_id IS NOT NULL AND empresa_id IS NULL)
    ),
    CONSTRAINT chk_cliente_nunca_edita CHECK (
        NOT (rol = 'cliente' AND puede_editar = TRUE)
    )
);

CREATE TABLE tableros (
    id                BIGSERIAL PRIMARY KEY,
    sucursal_id       BIGINT NOT NULL REFERENCES sucursales(id),
    codigo            VARCHAR(20) NOT NULL,
    nombre            VARCHAR(100) NOT NULL,
    ubicacion         VARCHAR(200),
    amperaje_nominal  NUMERIC(6,2),
    activo            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_codigo_por_sucursal UNIQUE (sucursal_id, codigo)
);

CREATE TABLE dispositivos (
    id                  BIGSERIAL PRIMARY KEY,
    tablero_id          BIGINT NOT NULL REFERENCES tableros(id),
    modelo              VARCHAR(50) NOT NULL DEFAULT 'AcuRev-2110',
    numero_serie        VARCHAR(50),
    direccion_ip        VARCHAR(45),
    fecha_instalacion   DATE,
    ultima_comunicacion TIMESTAMPTZ,
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    token_ingesta       VARCHAR(64) UNIQUE
);

CREATE TABLE calibres_cable (
    calibre_mm2       NUMERIC(5,2) PRIMARY KEY,
    corriente_maxima  NUMERIC(6,2) NOT NULL,
    activo            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Única tabla opcional/futura del diseño. Existe pero está vacía; no bloquea nada.

CREATE TABLE circuitos (
    id                    BIGSERIAL PRIMARY KEY,
    tablero_id            BIGINT NOT NULL REFERENCES tableros(id),
    dispositivo_id        BIGINT REFERENCES dispositivos(id),
    codigo                VARCHAR(20) NOT NULL,
    nombre                VARCHAR(100) NOT NULL,
    calibre_cable_mm2     NUMERIC(5,2) REFERENCES calibres_cable(calibre_mm2),
    corriente_automatico  NUMERIC(6,2),
    canal_acurev          VARCHAR(30),
    activo                BOOLEAN NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_codigo_circuito_por_tablero UNIQUE (tablero_id, codigo)
);
CREATE UNIQUE INDEX uq_canal_por_dispositivo
  ON circuitos (dispositivo_id, canal_acurev)
  WHERE canal_acurev IS NOT NULL;
-- Estructura CORE del sistema (no opcional). Un tablero tiene uno o más AcuRev según su
-- cantidad de circuitos; canal_acurev mapea el identificador de hardware del CSV al circuito.

CREATE TABLE mediciones (
    id                  BIGSERIAL PRIMARY KEY,
    dispositivo_id      BIGINT NOT NULL REFERENCES dispositivos(id),
    circuito_id         BIGINT NOT NULL REFERENCES circuitos(id),
    medido_en           TIMESTAMPTZ NOT NULL,
    voltaje_a           NUMERIC(6,2),
    voltaje_b           NUMERIC(6,2),
    voltaje_c           NUMERIC(6,2),
    corriente_a         NUMERIC(8,2),
    corriente_b         NUMERIC(8,2),
    corriente_c         NUMERIC(8,2),
    potencia_activa     NUMERIC(10,2),
    energia_kwh         NUMERIC(12,3),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    temperatura_tablero NUMERIC(5,2),
    CONSTRAINT uq_circuito_momento UNIQUE (circuito_id, medido_en)
);
CREATE INDEX idx_mediciones_dispositivo_tiempo ON mediciones (dispositivo_id, medido_en DESC);

CREATE TABLE alarmas (
    id              BIGSERIAL PRIMARY KEY,
    dispositivo_id  BIGINT NOT NULL REFERENCES dispositivos(id),
    circuito_id     BIGINT REFERENCES circuitos(id),
    tipo            VARCHAR(30) NOT NULL,
    severidad       VARCHAR(20) NOT NULL DEFAULT 'moderada',
    valor_medido    NUMERIC(10,2),
    valor_umbral    NUMERIC(10,2),
    mensaje         VARCHAR(255),
    generado_en     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resuelto        BOOLEAN NOT NULL DEFAULT FALSE,
    resuelto_en     TIMESTAMPTZ,
    resuelto_por    BIGINT REFERENCES usuarios(id),
    CONSTRAINT chk_tipo_valido CHECK (tipo IN (
        'umbral_corriente', 'umbral_voltaje', 'umbral_potencia',
        'fase_caida', 'dispositivo_offline', 'temperatura_alta', 'otro'
    )),
    CONSTRAINT chk_severidad_valida CHECK (severidad IN ('leve', 'moderada', 'critica'))
);
CREATE INDEX idx_alarmas_dispositivo_tiempo ON alarmas (dispositivo_id, generado_en DESC);
CREATE INDEX idx_alarmas_pendientes ON alarmas (resuelto) WHERE resuelto = FALSE;

CREATE TABLE umbrales_configurados (
    id             BIGSERIAL PRIMARY KEY,
    tablero_id     BIGINT REFERENCES tableros(id),
    circuito_id    BIGINT REFERENCES circuitos(id),
    tipo_variable  VARCHAR(30) NOT NULL,
    valor_umbral   NUMERIC(10,2) NOT NULL,
    activo         BOOLEAN NOT NULL DEFAULT TRUE,
    creado_por     BIGINT REFERENCES usuarios(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_tipo_variable_valido CHECK (tipo_variable IN ('corriente', 'voltaje', 'potencia', 'temperatura')),
    CONSTRAINT chk_scope_umbral CHECK (
        (tipo_variable = 'temperatura' AND tablero_id IS NOT NULL AND circuito_id IS NULL) OR
        (tipo_variable IN ('corriente','voltaje','potencia') AND circuito_id IS NOT NULL AND tablero_id IS NULL)
    )
);
CREATE UNIQUE INDEX uq_umbral_circuito_tipo ON umbrales_configurados (circuito_id, tipo_variable) WHERE circuito_id IS NOT NULL;
CREATE UNIQUE INDEX uq_umbral_tablero_tipo ON umbrales_configurados (tablero_id, tipo_variable) WHERE tablero_id IS NOT NULL;

-- Jerarquía multi-tenant: empresa -> cliente -> sucursal -> tablero -> dispositivo -> circuito -> mediciones/alarmas
-- Pendientes conocidos (no reflejados en este script porque aún no se aplican):
--   1) umbrales_configurados.valor_umbral es un solo valor; voltaje necesita min y max.
--   2) Formato exacto del CSV/canal del AcuRev aún sin confirmar.
