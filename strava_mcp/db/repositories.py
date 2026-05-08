import gzip
import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Activity mapping
# ---------------------------------------------------------------------------


def _activity_to_row(activity: dict[str, Any]) -> dict[str, Any]:
    start_latlng = activity.get("start_latlng") or []
    end_latlng = activity.get("end_latlng") or []
    map_data = activity.get("map") or {}
    return {
        "id": activity["id"],
        "name": activity["name"],
        "sport_type": activity.get("sport_type") or activity.get("type", ""),
        "workout_type": activity.get("workout_type"),
        "start_date_utc": activity["start_date"],
        "start_date_local": activity["start_date_local"],
        "timezone": activity.get("timezone"),
        "distance_m": activity.get("distance"),
        "moving_time_s": activity.get("moving_time"),
        "elapsed_time_s": activity.get("elapsed_time"),
        "elevation_gain_m": activity.get("total_elevation_gain"),
        "average_speed_mps": activity.get("average_speed"),
        "max_speed_mps": activity.get("max_speed"),
        "average_heartrate": activity.get("average_heartrate"),
        "max_heartrate": activity.get("max_heartrate"),
        "average_cadence": activity.get("average_cadence"),
        "average_watts": activity.get("average_watts"),
        "weighted_average_watts": activity.get("weighted_average_watts"),
        "kilojoules": activity.get("kilojoules"),
        "suffer_score": activity.get("suffer_score"),
        "has_heartrate": bool(activity.get("has_heartrate", False)),
        "has_powermeter": bool(activity.get("device_watts", False)),
        "trainer": bool(activity.get("trainer", False)),
        "commute": bool(activity.get("commute", False)),
        "manual": bool(activity.get("manual", False)),
        "start_latlng_lat": start_latlng[0] if len(start_latlng) >= 2 else None,
        "start_latlng_lng": start_latlng[1] if len(start_latlng) >= 2 else None,
        "end_latlng_lat": end_latlng[0] if len(end_latlng) >= 2 else None,
        "end_latlng_lng": end_latlng[1] if len(end_latlng) >= 2 else None,
        "map_polyline": map_data.get("summary_polyline"),
        "raw_json": json.dumps(activity),
        "synced_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# ActivityRepository
# ---------------------------------------------------------------------------


class ActivityRepository:
    @staticmethod
    def upsert(conn: sqlite3.Connection, activity: dict[str, Any]) -> None:
        row = _activity_to_row(activity)
        conn.execute(
            """
            INSERT INTO activities (
                id, name, sport_type, workout_type,
                start_date_utc, start_date_local, timezone,
                distance_m, moving_time_s, elapsed_time_s, elevation_gain_m,
                average_speed_mps, max_speed_mps, average_heartrate, max_heartrate,
                average_cadence, average_watts, weighted_average_watts, kilojoules,
                suffer_score, has_heartrate, has_powermeter, trainer, commute, manual,
                start_latlng_lat, start_latlng_lng, end_latlng_lat, end_latlng_lng,
                map_polyline, raw_json, synced_at
            ) VALUES (
                :id, :name, :sport_type, :workout_type,
                :start_date_utc, :start_date_local, :timezone,
                :distance_m, :moving_time_s, :elapsed_time_s, :elevation_gain_m,
                :average_speed_mps, :max_speed_mps, :average_heartrate, :max_heartrate,
                :average_cadence, :average_watts, :weighted_average_watts, :kilojoules,
                :suffer_score, :has_heartrate, :has_powermeter, :trainer, :commute, :manual,
                :start_latlng_lat, :start_latlng_lng, :end_latlng_lat, :end_latlng_lng,
                :map_polyline, :raw_json, :synced_at
            )
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                sport_type = excluded.sport_type,
                workout_type = excluded.workout_type,
                start_date_utc = excluded.start_date_utc,
                start_date_local = excluded.start_date_local,
                timezone = excluded.timezone,
                distance_m = excluded.distance_m,
                moving_time_s = excluded.moving_time_s,
                elapsed_time_s = excluded.elapsed_time_s,
                elevation_gain_m = excluded.elevation_gain_m,
                average_speed_mps = excluded.average_speed_mps,
                max_speed_mps = excluded.max_speed_mps,
                average_heartrate = excluded.average_heartrate,
                max_heartrate = excluded.max_heartrate,
                average_cadence = excluded.average_cadence,
                average_watts = excluded.average_watts,
                weighted_average_watts = excluded.weighted_average_watts,
                kilojoules = excluded.kilojoules,
                suffer_score = excluded.suffer_score,
                has_heartrate = excluded.has_heartrate,
                has_powermeter = excluded.has_powermeter,
                trainer = excluded.trainer,
                commute = excluded.commute,
                manual = excluded.manual,
                start_latlng_lat = excluded.start_latlng_lat,
                start_latlng_lng = excluded.start_latlng_lng,
                end_latlng_lat = excluded.end_latlng_lat,
                end_latlng_lng = excluded.end_latlng_lng,
                map_polyline = excluded.map_polyline,
                raw_json = excluded.raw_json,
                synced_at = excluded.synced_at
            """,
            row,
        )

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, activity_id: int) -> dict[str, Any] | None:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def count(conn: sqlite3.Connection) -> int:
        return conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]

    @staticmethod
    def count_by_sport(conn: sqlite3.Connection) -> dict[str, int]:
        rows = conn.execute(
            "SELECT sport_type, COUNT(*) FROM activities GROUP BY sport_type ORDER BY COUNT(*) DESC"
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    @staticmethod
    def get_newest_start_date(conn: sqlite3.Connection) -> str | None:
        row = conn.execute("SELECT MAX(start_date_utc) FROM activities").fetchone()
        return row[0] if row else None

    @staticmethod
    def get_oldest_start_date(conn: sqlite3.Connection) -> str | None:
        row = conn.execute("SELECT MIN(start_date_utc) FROM activities").fetchone()
        return row[0] if row else None

    @staticmethod
    def count_without_streams(conn: sqlite3.Connection) -> int:
        return conn.execute(
            "SELECT COUNT(*) FROM activities WHERE streams_synced_at IS NULL"
        ).fetchone()[0]

    @staticmethod
    def list_ids_without_streams(conn: sqlite3.Connection, limit: int = 100) -> list[int]:
        rows = conn.execute(
            "SELECT id FROM activities WHERE streams_synced_at IS NULL LIMIT ?", (limit,)
        ).fetchall()
        return [row[0] for row in rows]

    @staticmethod
    def mark_streams_synced(conn: sqlite3.Connection, activity_id: int, synced_at: str) -> None:
        conn.execute(
            "UPDATE activities SET streams_synced_at = ? WHERE id = ?",
            (synced_at, activity_id),
        )


# ---------------------------------------------------------------------------
# StreamRepository
# ---------------------------------------------------------------------------


class StreamRepository:
    @staticmethod
    def upsert(
        conn: sqlite3.Connection,
        activity_id: int,
        stream_type: str,
        data: list[Any],
        resolution: str,
    ) -> None:
        blob = gzip.compress(json.dumps(data).encode())
        conn.execute(
            """
            INSERT INTO activity_streams (activity_id, stream_type, data, resolution)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(activity_id, stream_type) DO UPDATE SET
                data = excluded.data,
                resolution = excluded.resolution
            """,
            (activity_id, stream_type, blob, resolution),
        )

    @staticmethod
    def get(conn: sqlite3.Connection, activity_id: int, stream_type: str) -> list[Any] | None:
        row = conn.execute(
            "SELECT data FROM activity_streams WHERE activity_id = ? AND stream_type = ?",
            (activity_id, stream_type),
        ).fetchone()
        if not row:
            return None
        return json.loads(gzip.decompress(row[0]).decode())

    @staticmethod
    def get_activity_ids_with_streams(conn: sqlite3.Connection) -> set[int]:
        rows = conn.execute("SELECT DISTINCT activity_id FROM activity_streams").fetchall()
        return {row[0] for row in rows}


# ---------------------------------------------------------------------------
# SyncStateRepository
# ---------------------------------------------------------------------------


class SyncStateRepository:
    @staticmethod
    def get(conn: sqlite3.Connection, key: str) -> str | None:
        row = conn.execute("SELECT value FROM sync_state WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    @staticmethod
    def set(conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            """
            INSERT INTO sync_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, datetime.now(UTC).isoformat()),
        )


# ---------------------------------------------------------------------------
# AthleteConfigRepository
# ---------------------------------------------------------------------------


class AthleteConfigRepository:
    @staticmethod
    def get(conn: sqlite3.Connection, key: str) -> str | None:
        row = conn.execute("SELECT value FROM athlete_config WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    @staticmethod
    def set(conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            """
            INSERT INTO athlete_config (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, datetime.now(UTC).isoformat()),
        )

    @staticmethod
    def get_all(conn: sqlite3.Connection) -> dict[str, str]:
        rows = conn.execute("SELECT key, value FROM athlete_config").fetchall()
        return {row[0]: row[1] for row in rows}


# ---------------------------------------------------------------------------
# MetricsRepository
# ---------------------------------------------------------------------------


class MetricsRepository:
    @staticmethod
    def upsert_activity_metrics(
        conn: sqlite3.Connection,
        activity_id: int,
        metrics: dict[str, Any],
    ) -> None:
        from datetime import UTC, datetime

        now = datetime.now(UTC).isoformat()
        metrics = {**metrics, "activity_id": activity_id, "computed_at": now}
        conn.execute(
            """
            INSERT INTO activity_metrics (
                activity_id, trimp, hr_tss, r_tss,
                aerobic_efficiency, decoupling_pct, ngp_mps, intensity_factor,
                z1_seconds, z2_seconds, z3_seconds, z4_seconds, z5_seconds,
                computed_at
            ) VALUES (
                :activity_id, :trimp, :hr_tss, :r_tss,
                :aerobic_efficiency, :decoupling_pct, :ngp_mps, :intensity_factor,
                :z1_seconds, :z2_seconds, :z3_seconds, :z4_seconds, :z5_seconds,
                :computed_at
            )
            ON CONFLICT(activity_id) DO UPDATE SET
                trimp = excluded.trimp,
                hr_tss = excluded.hr_tss,
                r_tss = excluded.r_tss,
                aerobic_efficiency = excluded.aerobic_efficiency,
                decoupling_pct = excluded.decoupling_pct,
                ngp_mps = excluded.ngp_mps,
                intensity_factor = excluded.intensity_factor,
                z1_seconds = excluded.z1_seconds,
                z2_seconds = excluded.z2_seconds,
                z3_seconds = excluded.z3_seconds,
                z4_seconds = excluded.z4_seconds,
                z5_seconds = excluded.z5_seconds,
                computed_at = excluded.computed_at
            """,
            metrics,
        )

    @staticmethod
    def upsert_daily_metrics(
        conn: sqlite3.Connection,
        rows: list[dict[str, Any]],
    ) -> None:
        conn.executemany(
            """
            INSERT INTO daily_metrics (
                date, daily_tss, ctl, atl, tsb, n_activities, total_distance_m, total_moving_time_s
            ) VALUES (
                :date, :daily_tss, :ctl, :atl, :tsb,
                :n_activities, :total_distance_m, :total_moving_time_s
            )
            ON CONFLICT(date) DO UPDATE SET
                daily_tss = excluded.daily_tss,
                ctl = excluded.ctl,
                atl = excluded.atl,
                tsb = excluded.tsb,
                n_activities = excluded.n_activities,
                total_distance_m = excluded.total_distance_m,
                total_moving_time_s = excluded.total_moving_time_s
            """,
            rows,
        )

    @staticmethod
    def get_activity_metrics(
        conn: sqlite3.Connection, activity_id: int
    ) -> dict[str, Any] | None:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM activity_metrics WHERE activity_id = ?", (activity_id,)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_daily_metrics_range(
        conn: sqlite3.Connection, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM daily_metrics WHERE date BETWEEN ? AND ? ORDER BY date",
            (start_date, end_date),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_all_activities_for_metrics(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        """Return all activities with the columns needed for metric computation."""
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, sport_type, start_date_utc,
                   average_heartrate, max_heartrate,
                   moving_time_s, distance_m, elevation_gain_m
            FROM activities
            ORDER BY start_date_utc
            """
        ).fetchall()
        return [dict(r) for r in rows]
