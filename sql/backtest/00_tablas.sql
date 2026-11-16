-- Tablas donde el loop acumula el resultado de cada día evaluado.
CREATE TABLE bt_normales (
    dia DATE,
    equipment_id VARCHAR,
    inicio_ventana TIMESTAMP,
    min_ts_usada TIMESTAMP,
    max_ts_usada TIMESTAMP,
    n_lecturas BIGINT,
    normal_vib DOUBLE,
    normal_temp DOUBLE
);

CREATE TABLE bt_alertas (
    combo_id VARCHAR,
    dia DATE,
    equipment_id VARCHAR,
    detalle VARCHAR,
    racha_max BIGINT
);
