import os
import sys
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

class PosterGenerator:
    def __init__(self, output_dir: Path = config.POSTER_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load fonts safely with fallbacks
        self.font_bold_path = r"C:\Windows\Fonts\segoeuib.ttf"
        self.font_reg_path = r"C:\Windows\Fonts\segoeui.ttf"
        self.font_impact_path = r"C:\Windows\Fonts\impact.ttf"

        self._init_fonts()

    def _init_fonts(self):
        try:
            self.f_tournament = ImageFont.truetype(self.font_bold_path, 28)
            self.f_sub = ImageFont.truetype(self.font_reg_path, 22)
            self.f_badge = ImageFont.truetype(self.font_bold_path, 20)
            self.f_team_title = ImageFont.truetype(self.font_bold_path, 42)
            self.f_score_huge = ImageFont.truetype(self.font_impact_path, 98)
            self.f_overs = ImageFont.truetype(self.font_bold_path, 36)
            self.f_heading = ImageFont.truetype(self.font_bold_path, 24)
            self.f_player_name = ImageFont.truetype(self.font_bold_path, 28)
            self.f_player_stat = ImageFont.truetype(self.font_reg_path, 24)
            self.f_stat_small = ImageFont.truetype(self.font_bold_path, 18)
            self.f_equation = ImageFont.truetype(self.font_bold_path, 32)
            self.f_footer = ImageFont.truetype(self.font_reg_path, 18)
        except Exception:
            # Fallback to default PIL fonts if Windows fonts missing
            self.f_tournament = ImageFont.load_default()
            self.f_sub = self.f_tournament
            self.f_badge = self.f_tournament
            self.f_team_title = self.f_tournament
            self.f_score_huge = self.f_tournament
            self.f_overs = self.f_tournament
            self.f_heading = self.f_tournament
            self.f_player_name = self.f_tournament
            self.f_player_stat = self.f_tournament
            self.f_stat_small = self.f_tournament
            self.f_equation = self.f_tournament
            self.f_footer = self.f_tournament

    def generate_poster(self, match: Dict[str, Any], filename: str = "latest_poster.png") -> str:
        """
        Generates a 1080x1080 high-res cricket scorecard poster.
        Returns the absolute filepath of the generated image.
        """
        W, H = 1080, 1080
        im = Image.new("RGB", (W, H), color=(15, 23, 42)) # Deep Slate 900
        draw = ImageDraw.Draw(im)

        # 1. Header Banner
        draw.rectangle([0, 0, W, 130], fill=(24, 34, 58))
        draw.line([0, 130, W, 130], fill=(59, 130, 246), width=3)

        # LIVE Badge
        badge_x, badge_y = 40, 35
        is_live = match.get("status", "live").lower() == "live"
        badge_bg = (220, 38, 38) if is_live else (100, 116, 139) # Red for live, gray for break/result
        badge_text = "● LIVE" if is_live else "● BREAK"

        draw.rounded_rectangle([badge_x, badge_y, badge_x + 115, badge_y + 42], radius=8, fill=badge_bg)
        draw.text((badge_x + 18, badge_y + 8), badge_text, font=self.f_badge, fill=(255, 255, 255))

        # Tournament Name & Details
        t_name = match.get("tournament_name", config.TOURNAMENT_NAME).upper()
        draw.text((175, 30), t_name, font=self.f_tournament, fill=(255, 255, 255))
        
        round_name = match.get("round_name", "League Matches")
        overs_limit = match.get("overs_limit", 8)
        ground_name = match.get("ground_name", "Nimbalkar sports Club, Pune")
        venue_line = f"{round_name} • {overs_limit} Overs • {ground_name}"
        draw.text((175, 75), venue_line, font=self.f_sub, fill=(148, 163, 184))

        # 2. Main Match Card
        card_top, card_bot = 160, 490
        draw.rounded_rectangle([40, card_top, W - 40, card_bot], radius=20, fill=(30, 41, 59), outline=(51, 65, 85), width=2)

        # Team Matchup
        team_a = match.get("team_a", "F Wing")
        team_b = match.get("team_b", "A wing")
        batting_team = match.get("batting_team", team_a)

        vs_text = f"{team_a}  VS  {team_b}"
        draw.text((70, card_top + 25), vs_text, font=self.f_team_title, fill=(241, 245, 249))

        # Batting Team Pill
        draw.rounded_rectangle([70, card_top + 85, 270, card_top + 120], radius=6, fill=(16, 185, 129))
        draw.text((85, card_top + 90), f"BATTING: {batting_team}", font=self.f_badge, fill=(255, 255, 255))

        # Score & Overs
        runs = match.get("runs", 0)
        wickets = match.get("wickets", 0)
        overs = match.get("overs", "0.0")

        score_text = f"{runs}/{wickets}"
        draw.text((70, card_top + 130), score_text, font=self.f_score_huge, fill=(250, 204, 21)) # Gold

        overs_text = f"({overs} / {overs_limit} ov)"
        draw.text((370, card_top + 175), overs_text, font=self.f_overs, fill=(203, 213, 225))

        # Run Rates
        crr = match.get("crr", "0.00")
        rrr = match.get("rrr", "-")
        target = match.get("target", "-")
        rr_str = f"Current Run Rate: {crr}"
        if target and target != "-" and target != 0:
            rr_str += f"   |   Target: {target} (Req RR: {rrr})"
        draw.text((70, card_top + 260), rr_str, font=self.f_heading, fill=(148, 163, 184))

        # Recent Balls (This Over)
        recent_balls = match.get("recent_balls", [])
        if not recent_balls:
            recent_balls = ["•", "•", "•", "•", "•", "•"]
        draw.text((70, card_top + 300), "This Over:", font=self.f_heading, fill=(203, 213, 225))

        ball_x = 205
        ball_y = card_top + 296
        for b in recent_balls[:8]: # cap to 8 balls max (in case of wides/no balls)
            b_str = str(b)
            ball_bg = (51, 65, 85)
            text_color = (255, 255, 255)
            if b_str == "W":
                ball_bg = (220, 38, 38)
            elif b_str == "4":
                ball_bg = (16, 185, 129)
            elif b_str == "6":
                ball_bg = (147, 51, 234)
            elif b_str in ["0", "•"]:
                ball_bg = (71, 85, 105)
            elif "wd" in b_str.lower() or "nb" in b_str.lower():
                ball_bg = (217, 119, 6) # Amber for extras

            draw.rounded_rectangle([ball_x, ball_y, ball_x + 36, ball_y + 36], radius=18, fill=ball_bg)
            # Center ball label
            draw.text((ball_x + (12 if len(b_str) == 1 else 6), ball_y + 6), b_str, font=self.f_badge, fill=text_color)
            ball_x += 48

        # 3. Two Split Columns: Batters on Crease & Current Bowler
        b_card_top, b_card_bot = 510, 820
        mid_x = W // 2 - 15

        # Left: Batters Card
        draw.rounded_rectangle([40, b_card_top, mid_x, b_card_bot], radius=16, fill=(30, 41, 59), outline=(51, 65, 85), width=2)
        draw.rectangle([40, b_card_top, mid_x, b_card_top + 50], fill=(40, 53, 76))
        draw.text((60, b_card_top + 12), "[BATTERS AT CREASE]", font=self.f_heading, fill=(56, 189, 248))

        batters = match.get("batters", [
            {"name": "Batter 1*", "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "sr": "0.0"},
            {"name": "Batter 2", "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "sr": "0.0"}
        ])

        cur_y = b_card_top + 65
        for idx, b in enumerate(batters[:2]):
            b_name = b.get("name", "Batter")
            draw.text((60, cur_y), b_name, font=self.f_player_name, fill=(255, 255, 255))
            stats_line1 = f"{b.get('runs', 0)} runs  ({b.get('balls', 0)} balls)"
            stats_line2 = f"4s: {b.get('fours', 0)}  |  6s: {b.get('sixes', 0)}  |  SR: {b.get('sr', '0.0')}"
            draw.text((60, cur_y + 38), stats_line1, font=self.f_player_stat, fill=(250, 204, 21))
            draw.text((60, cur_y + 70), stats_line2, font=self.f_stat_small, fill=(148, 163, 184))
            if idx == 0:
                draw.line([60, cur_y + 102, mid_x - 30, cur_y + 102], fill=(51, 65, 85), width=1)
            cur_y += 120

        # Right: Bowler Card
        r_card_left = W // 2 + 15
        draw.rounded_rectangle([r_card_left, b_card_top, W - 40, b_card_bot], radius=16, fill=(30, 41, 59), outline=(51, 65, 85), width=2)
        draw.rectangle([r_card_left, b_card_top, W - 40, b_card_top + 50], fill=(40, 53, 76))
        draw.text((r_card_left + 20, b_card_top + 12), "[CURRENT BOWLER]", font=self.f_heading, fill=(244, 63, 94))

        bowler = match.get("bowler", {
            "name": "Bowler", "overs": "0.0", "maidens": 0, "runs": 0, "wickets": 0, "econ": "0.0"
        })
        draw.text((r_card_left + 20, b_card_top + 75), bowler.get("name", "Bowler"), font=self.f_player_name, fill=(255, 255, 255))
        fig_text = f"{bowler.get('overs', '0.0')} - {bowler.get('maidens', 0)} - {bowler.get('runs', 0)} - {bowler.get('wickets', 0)}"
        draw.text((r_card_left + 20, b_card_top + 120), fig_text, font=self.f_overs, fill=(244, 63, 94))
        draw.text((r_card_left + 20, b_card_top + 175), "Figures (O - M - R - W)", font=self.f_stat_small, fill=(148, 163, 184))
        draw.text((r_card_left + 20, b_card_top + 210), f"Economy: {bowler.get('econ', '0.0')}", font=self.f_player_stat, fill=(203, 213, 225))

        # 4. Equation / Status Banner
        eq_top, eq_bot = 840, 930
        draw.rounded_rectangle([40, eq_top, W - 40, eq_bot], radius=14, fill=(30, 58, 138), outline=(59, 130, 246), width=2)
        equation = match.get("equation", f"{team_a} won the toss and elected to bat first")
        draw.text((70, eq_top + 25), equation.upper(), font=self.f_equation, fill=(255, 255, 255))

        # 5. Footer Bar
        now_str = datetime.now().strftime("%d-%b-%Y %I:%M %p")
        footer_text = f"Live Score Update • {now_str} • Local Scoreboard"
        draw.text((40, 960), footer_text, font=self.f_footer, fill=(100, 116, 139))
        draw.text((W - 350, 960), "CricHeroes Automated Pipeline", font=self.f_footer, fill=(100, 116, 139))

        # Save image
        target_path = self.output_dir / filename
        im.save(str(target_path), quality=95)
        
        # Also always save a copy as latest_poster.png for instant UI access
        latest_path = self.output_dir / "latest_poster.png"
        if target_path != latest_path:
            im.save(str(latest_path), quality=95)

        return str(target_path)

if __name__ == "__main__":
    generator = PosterGenerator()
    test_match = {
        "status": "live",
        "tournament_name": "VLV Ganapti Mens Cricket Tournament 2026",
        "round_name": "League Matches",
        "overs_limit": 8,
        "ground_name": "Nimbalkar sports Club, Lohegaon Pune",
        "team_a": "F Wing",
        "team_b": "A wing",
        "batting_team": "F Wing",
        "runs": 84,
        "wickets": 3,
        "overs": "5.4",
        "crr": "14.82",
        "rrr": "9.42",
        "target": "106",
        "recent_balls": ["1", "4", "W", "0", "6", "wd"],
        "batters": [
            {"name": "Biswajit Nath*", "runs": 48, "balls": 20, "fours": 5, "sixes": 3, "sr": "240.0"},
            {"name": "Darshit Patel", "runs": 21, "balls": 12, "fours": 2, "sixes": 1, "sr": "175.0"}
        ],
        "bowler": {
            "name": "Venkatesh Iyer", "overs": "1.4", "maidens": 0, "runs": 22, "wickets": 2, "econ": "13.2"
        },
        "equation": "Need 22 runs in 14 balls to win"
    }
    path = generator.generate_poster(test_match, "sample_live_poster.png")
    print(f"Sample poster created at: {path}")
