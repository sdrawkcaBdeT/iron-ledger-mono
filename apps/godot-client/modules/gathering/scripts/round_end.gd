# RoundEnd.gd   (attached to RoundEnd)
extends CanvasLayer

@onready var label  : Label  = $Panel/MessageLabel
@onready var button : Button = $Panel/Close

func _ready() -> void:
	visible = false
	button.pressed.connect(_on_close)

func show_results(score: int) -> void:
	label.text = "You gathered %d resources." % score
	visible = true                          # show the panel
	get_tree().paused = true                # freeze everything else

func _on_close() -> void:
	get_tree().quit()               # ← exits the application
