import random
import time
import sys
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

class MatchSimulator:
    """
    Simulates a live 8-over cricket match between real tournament teams (e.g. F Wing vs A wing)
    with realistic ball-by-ball outcomes to allow testing the live score dashboard,
    automatic poster generator, and WhatsApp dispatcher ahead of match day.
    """
    def __init__(self, match_id: int = 27016163, team_a: str = "F Wing", team_b: str = "A wing"):
        self.match_id = match_id
        self.team_a = team_a
        self.team_b = team_b
        self.overs_limit = 8
        self.target = 94
        self.reset()

    def reset(self):
        self.runs = 0
        self.wickets = 0
        self.balls_bowled = 0
        self.is_completed = False
        self.status = "live" # "live" or "completed"
        self.current_over_balls: List[str] = []
        
        # Real players from A Wing & F Wing
        self.batters = [
            {"name": "Biswajit Nath*", "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "sr": "0.0"},
            {"name": "Darshit Patel", "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "sr": "0.0"}
        ]
        self.bowler = {
            "name": "Venkatesh Iyer", "overs": "0.0", "maidens": 0, "runs": 0, "wickets": 0, "econ": "0.0"
        }
        self.equation = f"{self.team_a} need {self.target} runs in {self.overs_limit * 6} balls to win"

    def bowl_next_ball(self) -> Dict[str, Any]:
        """Simulates one legal/extra delivery."""
        if self.is_completed or self.balls_bowled >= self.overs_limit * 6 or self.wickets >= 10:
            self.is_completed = True
            self.status = "completed"
            if self.runs >= self.target:
                self.equation = f"🏆 {self.team_a} won by {10 - self.wickets} wickets!"
            else:
                self.equation = f"🏆 {self.team_b} won by {self.target - 1 - self.runs} runs!"
            return self.get_state()

        # Outcome weights typical of tennis ball / quick cricket
        outcomes = [
            ("0", 0.25),
            ("1", 0.32),
            ("2", 0.12),
            ("4", 0.14),
            ("6", 0.09),
            ("W", 0.05),
            ("wd", 0.03),
        ]
        roll = random.random()
        cumulative = 0.0
        outcome = "1"
        for val, prob in outcomes:
            cumulative += prob
            if roll <= cumulative:
                outcome = val
                break

        # Process ball
        striker = self.batters[0]
        non_striker = self.batters[1]

        if outcome == "wd":
            self.runs += 1
            self.bowler["runs"] += 1
            self.current_over_balls.append("wd")
        elif outcome == "W":
            self.balls_bowled += 1
            striker["balls"] += 1
            self.wickets += 1
            self.bowler["wickets"] += 1
            self.current_over_balls.append("W")
            # Replace out batter
            next_batter_names = ["Manish Harne", "Rajat Bhati", "Sandeep Sahoo", "Vicky N", "Vishal S"]
            new_name = random.choice(next_batter_names) + "*"
            self.batters[0] = {"name": new_name, "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "sr": "0.0"}
        else:
            run_val = int(outcome)
            self.balls_bowled += 1
            self.runs += run_val
            striker["runs"] += run_val
            striker["balls"] += 1
            if run_val == 4:
                striker["fours"] += 1
            elif run_val == 6:
                striker["sixes"] += 1
            
            self.bowler["runs"] += run_val
            self.current_over_balls.append(outcome)

            # Rotate strike on odd runs
            if run_val in [1, 3]:
                striker["name"] = striker["name"].replace("*", "")
                non_striker["name"] = non_striker["name"].replace("*", "") + "*"
                self.batters = [non_striker, striker]

        # Recalculate strike rates
        for b in self.batters:
            if b["balls"] > 0:
                b["sr"] = f"{(b['runs'] / b['balls']) * 100:.1f}"

        # Check over completion
        completed_overs = self.balls_bowled // 6
        remaining_balls = self.balls_bowled % 6
        self.overs_str = f"{completed_overs}.{remaining_balls}"
        self.bowler["overs"] = f"{self.bowler.get('overs_bowled', 0) // 6}.{self.bowler.get('overs_bowled', 0) % 6}"

        # Current Run Rate
        overs_float = (self.balls_bowled / 6) if self.balls_bowled > 0 else 1.0
        self.crr = f"{(self.runs / overs_float):.2f}"

        # Required Run Rate
        balls_left = (self.overs_limit * 6) - self.balls_bowled
        runs_needed = self.target - self.runs
        if balls_left > 0 and runs_needed > 0:
            rrr_calc = (runs_needed / (balls_left / 6))
            self.rrr = f"{rrr_calc:.2f}"
            self.equation = f"Need {runs_needed} runs in {balls_left} balls to win"
        elif runs_needed <= 0:
            self.is_completed = True
            self.status = "completed"
            self.equation = f"🏆 {self.team_a} won by {10 - self.wickets} wickets!"
        else:
            self.is_completed = True
            self.status = "completed"
            self.equation = f"🏆 {self.team_b} won by {runs_needed - 1} runs!"

        # End of over strike rotation & new over reset
        if remaining_balls == 0 and outcome != "wd" and self.balls_bowled > 0:
            # Over completed: switch strike
            b0, b1 = self.batters
            b0["name"] = b0["name"].replace("*", "")
            b1["name"] = b1["name"].replace("*", "") + "*"
            self.batters = [b1, b0]
            # Change bowler
            next_bowlers = ["Darshit D Patel", "Chintan Selarka", "Manoj Pathak", "Divyam Pant"]
            self.bowler = {
                "name": random.choice(next_bowlers),
                "overs": f"0.0",
                "maidens": 0,
                "runs": 0,
                "wickets": 0,
                "econ": "0.0"
            }
            self.current_over_balls = []

        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        completed_overs = self.balls_bowled // 6
        remaining_balls = self.balls_bowled % 6
        overs_str = f"{completed_overs}.{remaining_balls}"
        overs_float = (self.balls_bowled / 6) if self.balls_bowled > 0 else 1.0
        crr = f"{(self.runs / overs_float):.2f}"

        return {
            "is_simulated": True,
            "status": self.status,
            "match_id": self.match_id,
            "tournament_name": config.TOURNAMENT_NAME,
            "round_name": "League Matches (Simulated)",
            "overs_limit": self.overs_limit,
            "ground_name": "Nimbalkar sports Club, Lohegaon Pune",
            "team_a": self.team_a,
            "team_b": self.team_b,
            "batting_team": self.team_a,
            "runs": self.runs,
            "wickets": self.wickets,
            "overs": overs_str,
            "balls_bowled": self.balls_bowled,
            "crr": crr,
            "rrr": getattr(self, "rrr", "11.75"),
            "target": self.target,
            "recent_balls": self.current_over_balls[-6:] if self.current_over_balls else ["-"],
            "batters": self.batters,
            "bowler": self.bowler,
            "equation": self.equation,
        }

# Global singleton simulator instance
simulator_instance = MatchSimulator()

if __name__ == "__main__":
    sim = MatchSimulator()
    print("Testing simulator for 12 balls...")
    for _ in range(12):
        s = sim.bowl_next_ball()
        print(f"Score: {s['runs']}/{s['wickets']} ({s['overs']} ov) | {s['equation']} | Balls: {s['recent_balls']}")
