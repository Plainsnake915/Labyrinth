"""Player-movement analytics used by the predictive shadow boss."""

from settings import DIRECTIONS, MOVES


class MarkovPredictor:
    """Learn first-order move transitions and forecast a short direction sequence."""

    def __init__(self):
        self.transitions = {
            direction: {next_direction: 0 for next_direction in DIRECTIONS}
            for direction in DIRECTIONS
        }
        self.previous_direction = None
        self.last_direction = None
        self.transition_count = 0

    def record(self, direction):
        if direction not in MOVES:
            return
        if self.previous_direction is not None:
            self.transitions[self.previous_direction][direction] += 1
            self.transition_count += 1
        self.previous_direction = direction
        self.last_direction = direction

    def predict_next(self, direction):
        counts = self.transitions.get(direction)
        if not counts or not any(counts.values()):
            return direction
        return max(DIRECTIONS, key=lambda candidate: counts[candidate])

    def predict_sequence(self, steps=3):
        direction = self.last_direction
        predictions = []
        for _ in range(steps):
            if direction is None:
                break
            direction = self.predict_next(direction)
            predictions.append(direction)
        return predictions