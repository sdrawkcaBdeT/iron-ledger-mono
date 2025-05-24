extends AnimatedSprite2D

@export var fps: int = 10         # still useful

func _ready():
	# ────────────────────────────────────────────────────
	# 2.  Build the SpriteFrames from three stand-alone PNGs
	# ────────────────────────────────────────────────────
	var tex_paths := [
		"res://assets/nav1_18px.png",
		"res://assets/nav2_22px.png",
		"res://assets/nav3_28px.png",
	]

	var sf := SpriteFrames.new()
	sf.add_animation("pulse")
	sf.set_animation_speed("pulse", fps)
	sf.set_animation_loop("pulse", true)      # make sure it loops

	for p in tex_paths:
		var tex := load(p) as Texture2D
		sf.add_frame("pulse", tex)

	sprite_frames = sf
	animation = "pulse"      # optional but explicit
	play()                   # defaults to current Animation, loops forever
