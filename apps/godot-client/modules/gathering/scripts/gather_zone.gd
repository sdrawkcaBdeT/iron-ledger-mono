extends Node2D

@onready var nav := $NavigationRegion2D
@onready var res_parent := $Resources
@onready var hud := $HUD
@onready var round_end := $RoundEnd
@onready var player := $Player
@onready var marker := $TargetMarker
const RES_NODE := preload("res://scenes/ResourceNode.tscn")

var total_nodes: int = 0
var time_left := 15.0
var weights := {1:0.42, 2:0.21, 3:0.17, 5:0.08, 6:0.06, 7:0.04, 8:0.02}
var _busy: bool = false

func _ready() -> void:
	marker.visible = false
	player.harvest_requested.connect(_begin_gather)
	player.harvest_cancelled.connect(_on_gather_cancelled)
	call_deferred("_spawn_clusters", 16)
	set_process(true)

func _process(delta: float) -> void:
	time_left -= delta
	hud.set_time_left(time_left)
	hud.set_sprint(player.sprint_cd_fraction())
	if time_left <= 0.0:
		_finish_round()

func update_marker(pos: Vector2) -> void:
	marker.global_position = pos
	marker.visible = true

# === spawning ===

func _add_resource(pos: Vector2) -> void:
	var inst := RES_NODE.instantiate()
	inst.global_position = pos
	res_parent.add_child(inst)
	total_nodes += 1

func _spawn_clusters(total: int) -> void:	
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	var map_rid: RID = nav.get_navigation_map()        # cache once
	
	while NavigationServer2D.map_get_iteration_id(map_rid) == 0:
		await get_tree().process_frame
		
	for _i in range(total):                            # range()
		var size: int = _weighted_pick(rng)
		var center: Vector2 = _random_navpoint(rng)
		_add_resource(center)
		
		for _j in range(size):                         # range()
			var spread := (128 if size <= 3 else 1024)
			var p := center + Vector2(
				rng.randf_range(-spread, spread),
				rng.randf_range(-spread, spread)
			)
			
			var nearest := NavigationServer2D.map_get_closest_point(map_rid, p)
			if nearest != Vector2.ZERO:
				_add_resource(nearest)
				#print("Spawned:", res_parent.get_child_count())

	hud.set_nodes_remaining(total_nodes - hud.score)

func _weighted_pick(rng: RandomNumberGenerator) -> int:
	var r := rng.randf()
	var acc := 0.0
	for k in weights:
		acc += weights[k]
		if r <= acc: return k
	return 1

func _random_navpoint(rng: RandomNumberGenerator) -> Vector2:
	# 1. Get the navigation-map RID from this region.
	var map_rid: RID = nav.get_navigation_map()

	# 2. Fetch the list of region RIDs inside that map.
	var regions: Array = NavigationServer2D.map_get_regions(map_rid)
	if regions.is_empty():
		push_error("Navigation map has no regions!")
		return Vector2.ZERO

	# 3. Use the first region’s bounds as our sampling rectangle.
	var region_rid: RID = regions[0]
	var rect: Rect2 = NavigationServer2D.region_get_bounds(region_rid)

	# 4. Pick random points until one lands on the mesh.
	while true:
		var p := Vector2(
			rng.randf_range(rect.position.x, rect.position.x + rect.size.x),
			rng.randf_range(rect.position.y, rect.position.y + rect.size.y)
		)

		var closest := NavigationServer2D.map_get_closest_point(map_rid, p)
		if closest.distance_to(p) < 1.0:        # on the mesh (50-px tolerance)
			return p

	# unreachable, but satisfies the type checker
	return rect.position

# === gather flow ===
func _begin_gather(node: ResourceNode) -> void:
	if _busy: return
	_busy = true
	node.start_gather()
	node.gathered.connect(_on_node_gathered, CONNECT_ONE_SHOT)


func _on_node_gathered() -> void:
	var last: ResourceNode = player._focus      # cache before nulling
	player._gather_target = null
	player._focus        = null
	if last:
		player._overlaps.erase(last)            # remove finished node
	
	player.refresh_focus()
	
	hud.score += 1
	hud.set_nodes_remaining(total_nodes - hud.score)
	_busy = false

func _on_gather_cancelled() -> void:
	_busy = false

# === round end ===
func _finish_round() -> void:
	print("GatherZone: _finish_round called. Time left:", time_left)
	set_process(false)
	player.set_process(false)
	marker.visible = false
	var path: PackedVector2Array = player.take_click_path()
	print("GatherZone: Calling Sidecar.send_gather with path size:", path.size(), "and score:", hud.score)

	# Connect to Sidecar's new signal (assuming Sidecar is an autoload)
	Sidecar.post_completed.connect(_on_sidecar_post_completed, CONNECT_ONE_SHOT)
	Sidecar.send_gather(path, hud.score)
	# DO NOT call round_end.show_results here anymore
	print("GatherZone: Waiting for Sidecar post to complete...")

func _on_sidecar_post_completed(success: bool, response_data: Dictionary) -> void:
	print("GatherZone: Sidecar post completed. Success:", success, "Data:", response_data)
	# Now it's safe to show the results
	if round_end and is_instance_valid(round_end): # Check if round_end is valid
		round_end.show_results(hud.score)
	else:
		push_error("GatherZone: round_end node is not valid!")
