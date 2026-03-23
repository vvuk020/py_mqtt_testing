import requests
import json, time

# Replace these with your actual values
DEVICE_ID = "989d8280-0691-11f1-8e2c-5b598f4f6273"
ORGANIZATION_ID = "c5e2a810-b8c1-11f0-a9f4-47bd6669e40b"
API_KEY = "ed_h0hzgbg2njfkzlysrkocgysn4oi8dwp11ct5tf6a9wm8ufnc2kc9pv2uz3jytqqg"

# Endpoint URLs
url_devices = f"https://api.edenic.io/api/v1/device/{ORGANIZATION_ID}"
url_telemetry = f"https://api.edenic.io/api/v1/telemetry/{DEVICE_ID}"
url = f"https://api.edenic.io/api/v1/telemetry/{DEVICE_ID}"


url = f"https://api.edenic.io/api/v1/telemetry/{DEVICE_ID}"
# --- Get current time and calculate start time (e.g., last 1 hour) ---
end_ts = int(time.time() * 1000)
start_ts = end_ts - (2 * 60 * 60 * 1000)  # last 2 hours

# --- Query parameters ---
params = {
    "keys": "temperature,ph,electrical_conductivity",
    "startTs": start_ts,
    "endTs": end_ts,
    "orderBy": "DESC",  # latest first
    "agg": "NONE"       # raw values, no averaging
}

headers = {"Authorization": API_KEY}

# --- Make request ---
response = requests.get(url, headers=headers, params=params)
print("Status Code:", response.status_code)

if response.status_code == 200:
    telemetry = response.json()

    # --- Function to print last N entries per key ---
    def print_last_entries(key, n=5):
        if key in telemetry and telemetry[key]:
            print(f"\nLast {n} entries for {key}:")
            for entry in telemetry[key][:n]:  # latest first
                ts = entry["ts"]
                value = entry["value"]
                readable_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts/1000))
                print(f"{readable_time} -> {value}")
        else:
            print(f"\nNo data for {key}")

    for key in ["temperature", "ph", "electrical_conductivity"]:
        print_last_entries(key, n=5)
else:
    print("Error:", response.text)