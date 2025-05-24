# res://scenes/Player.gd
extends CharacterBody2D
class_name Player

# --------------------------------------------------------------------------
# 1.  Constants (design knobs)  – scaled by apply_config()
# --------------------------------------------------------------------------
const BASE_MOVE_SPEED  := 120.0
const BASE_SPRINT_MULT := 2.0
const BASE_SPRINT_TIME := 0.8            # seconds

# --------------------------------------------------------------------------
# 2.  Runtime variables (will be overwritten by side-car multipliers)
# --------------------------------------------------------------------------
var move_speed      : float = BASE_MOVE_SPEED
var sprint_mult     : float = BASE_SPRINT_MULT
var sprint_time     : float = BASE_SPRINT_TIME
var gather_time_mult: float = 1.0        # divisor for ResourceNode
var tool_durability : int   = 999

# path poly-line to POST back
var _click_path := PackedVector2Array()

# existing selection / sprint state
var _target          := Vector2.ZERO
var _is_sprinting    := false
var _focus           : ResourceNode = null
var _gather_target   : ResourceNode = null
var _overlaps        : Array[ResourceNode] = []

signal harvest_requested(node: ResourceNode)
signal harvest_cancelled


# --------------------------------------------------------------------------
# 3.  Startup
# --------------------------------------------------------------------------
func _ready() -> void:
	add_to_group("player")               # lets Sidecar find us
	$SprintTimer.timeout.connect(_on_sprint_end)
	$SprintCDTimer.timeout.connect(_on_cd_end)
	$NavigationAgent2D.max_speed = BASE_MOVE_SPEED * BASE_SPRINT_MULT
	$Camera2D.enabled = true
	$HarvestArea.area_entered.connect(_on_area_entered)
	$HarvestArea.area_exited.connect(_on_area_exited)

# --------------------------------------------------------------------------
# 4.  Side-car injection
# --------------------------------------------------------------------------
func apply_config(cfg: Dictionary) -> void:
	move_speed       = BASE_MOVE_SPEED  * cfg.move_speed_mult
	sprint_mult      = BASE_SPRINT_MULT * cfg.sprint_speed_mult
	sprint_time      = BASE_SPRINT_TIME * cfg.sprint_time_mult
	gather_time_mult = cfg.gather_time_mult
	tool_durability  = cfg.tool.durability
	print("Config applied:", cfg)

# --------------------------------------------------------------------------
# 5.  Input
# --------------------------------------------------------------------------
func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_click"):
		_click_path.append(get_global_mouse_position())
		_target = _click_path[-1]
		get_parent().update_marker(_target)
		$NavigationAgent2D.target_position = _target
		if _gather_target:
			_gather_target.cancel_gather()
			_gather_target = null
			emit_signal("harvest_cancelled")

	elif event.is_action_pressed("ui_sprint") \
			and not _is_sprinting \
			and $SprintCDTimer.is_stopped():
		_start_sprint()

	elif event.is_action_pressed("ui_harvest") and _focus:
		_gather_target = _focus
		emit_signal("harvest_requested", _focus)

# --------------------------------------------------------------------------
# 6.  Movement & sprint timers
# --------------------------------------------------------------------------
func _physics_process(delta: float) -> void:
	if $NavigationAgent2D.is_navigation_finished(): return
	var next_pt: Vector2 = $NavigationAgent2D.get_next_path_position()
	var dir:     Vector2 = (next_pt - global_position).normalized()
	var speed   := move_speed * (sprint_mult if _is_sprinting else 1.0)
	velocity    = dir * speed
	move_and_slide()

	# update HUD sprint bar (optional)
	if $"../HUD".has_node("SprintBar"):
		$"../HUD/SprintBar".value = sprint_cd_fraction()

func _start_sprint() -> void:
	_is_sprinting = true
	$SprintTimer.start(sprint_time)
	$SprintCDTimer.start()

func _on_sprint_end() -> void:
	_is_sprinting = false

func _on_cd_end() -> void:
	pass

func sprint_cd_fraction() -> float:
	return $SprintCDTimer.time_left / $SprintCDTimer.wait_time if $SprintCDTimer.wait_time > 0 else 1.0

# --------------------------------------------------------------------------
# 7.  Harvest-range focus helpers (unchanged)
# --------------------------------------------------------------------------
func _on_area_entered(area: Area2D) -> void:
	var res := area.get_parent() as ResourceNode
	if res:
		_overlaps.append(res)
		_update_focus()

func _on_area_exited(area: Area2D) -> void:
	var res := area.get_parent() as ResourceNode
	if res:
		_overlaps.erase(res)
		if res == _focus:
			res.set_highlight(false)
			_focus = null
			_update_focus()

func _update_focus() -> void:
	if _focus and _focus in _overlaps:
		return                         # keep current
	# choose nearest
	var best: ResourceNode = null
	var best_d := INF
	for res in _overlaps:
		var d := res.global_position.distance_to(global_position)
		if d < best_d:
			best   = res
			best_d = d
	if best != _focus:
		if _focus: _focus.set_highlight(false)
		_focus = best
		if _focus: _focus.set_highlight(true)

func refresh_focus() -> void:
	_update_focus()
# --------------------------------------------------------------------------
# 8.  Utility for GatherZone
# --------------------------------------------------------------------------
func take_click_path() -> PackedVector2Array:
	var p := _click_path.duplicate()
	_click_path.clear()
	return p
