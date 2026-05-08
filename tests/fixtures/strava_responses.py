"""Anonymized sample Strava API responses for use in tests."""

ACTIVITY_RUN = {
    "id": 11111111111,
    "name": "Morning Run",
    "sport_type": "Run",
    "workout_type": None,
    "start_date": "2024-03-15T09:30:00Z",
    "start_date_local": "2024-03-15T06:30:00Z",
    "timezone": "(GMT-03:00) America/Sao_Paulo",
    "distance": 10200.0,
    "moving_time": 3540,
    "elapsed_time": 3720,
    "total_elevation_gain": 45.0,
    "average_speed": 2.881,
    "max_speed": 4.1,
    "average_heartrate": 152.0,
    "max_heartrate": 172.0,
    "average_cadence": 84.0,
    "average_watts": None,
    "weighted_average_watts": None,
    "kilojoules": None,
    "suffer_score": 42,
    "has_heartrate": True,
    "device_watts": False,
    "trainer": False,
    "commute": False,
    "manual": False,
    "start_latlng": [-23.5505, -46.6333],
    "end_latlng": [-23.5510, -46.6340],
    "map": {"summary_polyline": "abc123encoded"},
}

ACTIVITY_RUN_2 = {
    **ACTIVITY_RUN,
    "id": 22222222222,
    "name": "Easy Recovery Run",
    "start_date": "2024-03-17T09:00:00Z",
    "start_date_local": "2024-03-17T06:00:00Z",
    "distance": 6500.0,
    "moving_time": 2400,
    "elapsed_time": 2500,
    "average_heartrate": 135.0,
    "suffer_score": 20,
}

ACTIVITY_LONG_RUN = {
    **ACTIVITY_RUN,
    "id": 33333333333,
    "name": "Long Run",
    "workout_type": None,
    "start_date": "2024-03-10T08:00:00Z",
    "start_date_local": "2024-03-10T05:00:00Z",
    "distance": 21097.5,
    "moving_time": 7200,
    "elapsed_time": 7500,
    "average_heartrate": 158.0,
    "suffer_score": 95,
}

ACTIVITY_NO_HR = {
    **ACTIVITY_RUN,
    "id": 44444444444,
    "name": "Run without HR monitor",
    "start_date": "2024-03-05T10:00:00Z",
    "start_date_local": "2024-03-05T07:00:00Z",
    "has_heartrate": False,
    "average_heartrate": None,
    "max_heartrate": None,
    "suffer_score": None,
    "start_latlng": [],
    "end_latlng": [],
}

ACTIVITY_RIDE = {
    **ACTIVITY_RUN,
    "id": 55555555555,
    "name": "Afternoon Ride",
    "sport_type": "Ride",
    "start_date": "2024-03-12T14:00:00Z",
    "start_date_local": "2024-03-12T11:00:00Z",
    "distance": 35000.0,
    "moving_time": 5400,
    "average_watts": 180.0,
    "device_watts": True,
}

SAMPLE_ACTIVITIES_PAGE_1 = [ACTIVITY_RUN, ACTIVITY_RUN_2, ACTIVITY_LONG_RUN]
SAMPLE_ACTIVITIES_PAGE_2 = [ACTIVITY_NO_HR, ACTIVITY_RIDE]

SAMPLE_STREAMS = {
    "time": {"data": [0, 1, 2, 3, 4], "resolution": "high"},
    "heartrate": {"data": [140, 145, 150, 148, 152], "resolution": "high"},
    "velocity_smooth": {"data": [2.8, 2.9, 2.85, 2.9, 2.88], "resolution": "high"},
    "altitude": {"data": [760.0, 761.0, 762.0, 761.5, 760.0], "resolution": "high"},
}
