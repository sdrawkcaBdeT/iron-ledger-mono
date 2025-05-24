extends CanvasLayer
var score := 0:
	set(v):
		score = v
		$VBox/ScoreLabel.text = "Score: %d" % score

func set_sprint(t):         $VBox/SprintHUD.value = t
func set_time_left(sec):
	var m = int(sec)/60
	var s = int(sec)%60
	$VBox/TimerLabel.text = "%02d:%02d" % [m,s]

func set_nodes_remaining(n: int) -> void:
	$VBox/RemainingLabel.text = "Nodes remaining: %d" % n
