class_name ResourceNode
extends Node2D
signal gathered

@export var gather_time := 2.0            # base seconds to harvest

# ── internal state ─────────────────────────────────────────────
var _time_left   : float  = 0.0
var _total_time : float = 0.0     # effective time after multiplier
var _is_gathering: bool   = false
var _done        : bool   = false
var _fading      : bool   = false
@onready var tween := create_tween()


# ── ready: stay idle until harvested ───────────────────────────
func _ready() -> void:
	$GatherBar.visible = false
	set_process(false)           # save CPU when nothing to do

func set_highlight(on: bool) -> void:
	tween.kill()                                       # stop any previous pulse

	if on:
		$Sprite2D.modulate = Color(1, 1, 0.5)
		$Sprite2D.scale = Vector2.ONE                  # reset scale
		tween = create_tween().set_loops(-1)           # infinite ping-pong
		tween.tween_property($Sprite2D, "scale",Vector2.ONE * 1.25, 0.25).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
		tween.tween_property($Sprite2D, "scale",Vector2.ONE, 0.25)        # shrink back
	else:
		tween = create_tween()
		tween.tween_property($Sprite2D, "scale", Vector2.ONE, 0.10)        # snap back quickly
		$Sprite2D.modulate = Color(1, 1, 1) # return to base color


func start_gather() -> void:
	# Guard against spam or already-finished nodes
	if _is_gathering or _done:
		return

	# --- fetch player multiplier (but keep original gather_time intact) ---
	var player := get_tree().get_first_node_in_group("player") as Player
	var speed_mult := player.gather_time_mult if player else 1.0
	_total_time   = gather_time / speed_mult          # faster tools finish sooner
	_time_left     = _total_time

	# --- begin gather ---
	_is_gathering = true
	$GatherBar.visible = true
	_update_bar()
	$GatherBar.value = 0.0
	_fading = false
	$Sprite2D.modulate.a = 1.0
	set_process(true)

func _update_bar() -> void:
	$GatherBar.value = 1.0 - (_time_left / _total_time)

func cancel_gather() -> void:
	if _is_gathering and not _done:
		_is_gathering = false
		$GatherBar.visible = false
		set_highlight(false)
		set_process(false)

# ── frame update ───────────────────────────────────────────────
func _process(delta: float) -> void:
	if _is_gathering:
		_time_left -= delta
		_update_bar()
		if _time_left <= 0.0:
			_finish_node()
	elif _fading:
		$Sprite2D.modulate.a -= delta * 4.0    # quick fade
		if $Sprite2D.modulate.a <= 0.0:
			queue_free()
			set_process(false)

func _finish_node() -> void:
	_done         = true
	_is_gathering = false
	emit_signal("gathered")

	# play SFX to completion without blocking new harvests
	var sfx := $CollectSFX.duplicate()
	get_tree().current_scene.add_child(sfx)
	sfx.play()
	sfx.finished.connect(func(): sfx.queue_free(), CONNECT_ONE_SHOT)

	$GatherBar.visible = false
	_fading = true
