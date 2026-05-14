CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    sport_type TEXT NOT NULL,
    workout_type INTEGER,
    start_date_utc TIMESTAMP NOT NULL,
    start_date_local TIMESTAMP NOT NULL,
    timezone TEXT,
    distance_m REAL,
    moving_time_s INTEGER,
    elapsed_time_s INTEGER,
    elevation_gain_m REAL,
    average_speed_mps REAL,
    max_speed_mps REAL,
    average_heartrate REAL,
    max_heartrate REAL,
    average_cadence REAL,
    average_watts REAL,
    weighted_average_watts REAL,
    kilojoules REAL,
    suffer_score INTEGER,
    has_heartrate BOOLEAN,
    has_powermeter BOOLEAN,
    trainer BOOLEAN,
    commute BOOLEAN,
    manual BOOLEAN,
    start_latlng_lat REAL,
    start_latlng_lng REAL,
    end_latlng_lat REAL,
    end_latlng_lng REAL,
    map_polyline TEXT,
    raw_json TEXT NOT NULL,
    synced_at TIMESTAMP NOT NULL,
    streams_synced_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_activities_start_date ON activities(start_date_utc);
CREATE INDEX IF NOT EXISTS idx_activities_sport ON activities(sport_type);
CREATE INDEX IF NOT EXISTS idx_activities_workout_type ON activities(workout_type);

CREATE TABLE IF NOT EXISTS activity_streams (
    activity_id INTEGER NOT NULL,
    stream_type TEXT NOT NULL,
    data BLOB NOT NULL,
    resolution TEXT NOT NULL,
    PRIMARY KEY (activity_id, stream_type),
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS activity_metrics (
    activity_id INTEGER PRIMARY KEY,
    trimp REAL,
    hr_tss REAL,
    r_tss REAL,
    aerobic_efficiency REAL,
    decoupling_pct REAL,
    ngp_mps REAL,
    intensity_factor REAL,
    z1_seconds INTEGER,
    z2_seconds INTEGER,
    z3_seconds INTEGER,
    z4_seconds INTEGER,
    z5_seconds INTEGER,
    weather_temp_c REAL,
    weather_humidity_pct REAL,
    weather_wind_mps REAL,
    weather_precipitation_mm REAL,
    computed_at TIMESTAMP NOT NULL,
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS activity_best_efforts (
    activity_id INTEGER NOT NULL,
    distance_label TEXT NOT NULL,
    distance_m REAL NOT NULL,
    time_s REAL NOT NULL,
    segment_start_s REAL NOT NULL,
    segment_end_s REAL NOT NULL,
    start_idx INTEGER NOT NULL,
    end_idx INTEGER NOT NULL,
    computed_at TIMESTAMP NOT NULL,
    PRIMARY KEY (activity_id, distance_label),
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_best_efforts_distance_time
    ON activity_best_efforts(distance_label, time_s);

CREATE TABLE IF NOT EXISTS daily_metrics (
    date DATE PRIMARY KEY,
    daily_tss REAL NOT NULL DEFAULT 0,
    ctl REAL NOT NULL,
    atl REAL NOT NULL,
    tsb REAL NOT NULL,
    n_activities INTEGER NOT NULL DEFAULT 0,
    total_distance_m REAL NOT NULL DEFAULT 0,
    total_moving_time_s INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS athlete_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    id INTEGER PRIMARY KEY DEFAULT 1,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    athlete_id INTEGER,
    CHECK (id = 1)
);
