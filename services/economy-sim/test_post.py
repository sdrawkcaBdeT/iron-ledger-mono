import requests
import json

url = "http://127.0.0.1:8000/v1/submit_gather" # Exact URL from your Godot script

# Match the headers Godot is sending
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "local-dev-only" # Ensure this matches your HDRS in Godot
}

# Mimic the body structure from Sidecar.gd.
# Use a small, valid sample for the path.
payload = {
    "agent_id": 17,
    "zone_id": 3,
    "path": [[100.0, 200.0], [150.0, 250.0]], # Example path
    "nodes_collected": 9 # Example score
}

print(f"Attempting to POST to: {url}")
print(f"With headers: {headers}")
print(f"With body: {json.dumps(payload)}")

try:
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    print(f"\n--- Response ---")
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response JSON: {response.json()}")
    except json.JSONDecodeError:
        print(f"Response Text (not JSON): {response.text}")
except requests.exceptions.ConnectionError as e:
    print(f"\n--- Error ---")
    print(f"Connection Error: Could not connect to the server at {url}.")
    print(f"Details: {e}")
except Exception as e:
    print(f"\n--- Error ---")
    print(f"An unexpected error occurred: {e}")