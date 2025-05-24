extends Node
const BASE := "http://127.0.0.1:8000/v1"
const HDRS := [
	"Content-Type: application/json",
	"X-API-Key: local-dev-only"
]

signal post_completed(success, response_data)

@onready var http := HTTPRequest.new()

func _ready() -> void:
	add_child(http)
	http.request_completed.connect(_on_request_done)
	# pull config as soon as the game boots (agent_id hard-coded for now)
	http.request("%s/round_config?agent_id=17" % BASE, HDRS)

func _on_request_done(result:int, code:int, _hdrs:Array, body:PackedByteArray) -> void:
	if code != 200:
		push_error("Side-car HTTP %d" % code); return
	var cfg: Dictionary = JSON.parse_string(body.get_string_from_utf8()) as Dictionary
	get_tree().get_first_node_in_group("player").apply_config(cfg)

# -------------------------------------------------------------------------
# POST after the round ends
# -------------------------------------------------------------------------
func send_gather(path: PackedVector2Array, nodes_collected: int) -> void:
	print("Sidecar: send_gather called. Nodes collected:", nodes_collected) # DEBUG

	# 1.  JSON-friendly path
	var path_arr: Array = []
	for p in path:
		path_arr.append([p.x, p.y])

	# 2.  Body
	var body_dict := { # Renamed from 'body' to avoid conflict with response body variable
		"agent_id":      17,
		"zone_id":       3,
		"path":          path_arr,
		"nodes_collected": nodes_collected
	}
	var json_body_string := JSON.stringify(body_dict) # Store stringified body

	print("Sidecar: Preparing to POST. URL:", "%s/submit_gather" % BASE) # DEBUG
	print("Sidecar: Request body:", json_body_string) # DEBUG

	# 3.  Fire POST with throw-away HTTPRequest
	var http2 := HTTPRequest.new()
	add_child(http2) # Ensure it's in the tree to process signals

	# bind(http2) passes the node as last param so we can free it later
	http2.request_completed.connect(_on_submit_done.bind(http2), CONNECT_ONE_SHOT)

	var error_code = http2.request(
		"%s/submit_gather" % BASE,
		HDRS,
		HTTPClient.METHOD_POST,
		json_body_string # Use the stringified body
	)

	if error_code != OK:
		print("Sidecar: HTTPRequest node failed to send request! Error code: ", error_code) # DEBUG
	else:
		print("Sidecar: HTTPRequest sent successfully (pending completion).") # DEBUG

# -------------------------------------------------------------------------
# Callback for the POST 
# -------------------------------------------------------------------------
func _on_submit_done(result: int, code: int, response_hdrs: Array,
						 body_bytes: PackedByteArray, http2: HTTPRequest) -> void:
	print("Sidecar: _on_submit_done called.")
	print("Sidecar: Result enum (0=OK):", result, ", HTTP Code:", code)
	var response_body_string := body_bytes.get_string_from_utf8()
	print("Sidecar: Response Body:", response_body_string)

	var success_flag := false
	var parsed_data := {}

	if code == 200 and result == HTTPRequest.RESULT_SUCCESS:
		var res: Dictionary = JSON.parse_string(response_body_string) as Dictionary
		if res:
			print("Sidecar: POST ok →", res)
			parsed_data = res
			success_flag = true
		else:
			print("Sidecar: POST ok, but failed to parse JSON response:", response_body_string)
	else:
		push_error("Sidecar: Submit error! HTTP Code: %d, Result: %d" % [code, result])
		push_error("Sidecar: Response: " + response_body_string)

	post_completed.emit(success_flag, parsed_data) # Emit the signal

	if is_instance_valid(http2):
		http2.queue_free()
		print("Sidecar: http2 node queued for freeing.")
	else:
		print("Sidecar: http2 node was already invalid before queue_free.")
