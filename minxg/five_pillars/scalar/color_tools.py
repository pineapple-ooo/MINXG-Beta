"""Color conversion and manipulation tools."""
from minxg.base import BaseWorker, tool

class ColorWorker(BaseWorker):
    facade_alias = "color_worker"
    worker_id = "color_worker"
    version = "0.17.1"

    @tool
    async def hex_to_rgb(self, hex_color: str = "#ffffff") -> dict:
        """Convert hex color to RGB."""
        h = hex_color.lstrip('#')
        return {"hex": hex_color, "rgb": tuple(int(h[i:i+2], 16) for i in (0,2,4))}

    @tool
    async def rgb_to_hex(self, r: int = 255, g: int = 255, b: int = 255) -> dict:
        """Convert RGB to hex color."""
        return {"rgb": (r,g,b), "hex": f"#{r:02x}{g:02x}{b:02x}"}

    @tool
    async def color_name(self, hex_color: str = "#ff0000") -> dict:
        """Get closest named color for a hex value."""
        colors = {
            "red": "#ff0000", "green": "#00ff00", "blue": "#0000ff",
            "yellow": "#ffff00", "cyan": "#00ffff", "magenta": "#ff00ff",
            "white": "#ffffff", "black": "#000000", "gray": "#808080",
            "orange": "#ffa500", "purple": "#800080", "pink": "#ffc0cb",
            "brown": "#a52a2a", "navy": "#000080", "teal": "#008080",
        }
        def dist(a,b): return sum((int(a[i:i+2],16)-int(b[i:i+2],16))**2 for i in (1,3,5))
        h = hex_color.lower()
        closest = min(colors, key=lambda c: dist(colors[c], h))
        return {"hex": h, "closest_name": closest, "closest_hex": colors[closest]}

    @tool
    async def color_palette(self, base_hex: str = "#3498db", count: int = 5) -> dict:
        """Generate a color palette from a base color."""
        h = base_hex.lstrip('#')
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        palette = []
        for i in range(count):
            factor = 0.5 + (i / (count-1)) * 1.0 if count > 1 else 1.0
            nr = min(255, int(r * factor))
            ng = min(255, int(g * factor))
            nb = min(255, int(b * factor))
            palette.append(f"#{nr:02x}{ng:02x}{nb:02x}")
        return {"base": base_hex, "palette": palette}

    @tool
    async def gradient(self, color1: str = "#ff0000", color2: str = "#0000ff", steps: int = 10) -> dict:
        """Generate a gradient between two colors."""
        c1 = tuple(int(color1.lstrip('#')[i:i+2],16) for i in (0,2,4))
        c2 = tuple(int(color2.lstrip('#')[i:i+2],16) for i in (0,2,4))
        gradient = []
        for i in range(steps):
            t = i / (steps - 1) if steps > 1 else 0
            r = int(c1[0] + (c2[0]-c1[0])*t)
            g = int(c1[1] + (c2[1]-c1[1])*t)
            b = int(c1[2] + (c2[2]-c1[2])*t)
            gradient.append(f"#{r:02x}{g:02x}{b:02x}")
        return {"color1": color1, "color2": color2, "gradient": gradient}

    @tool
    async def terminal_colors(self) -> dict:
        """List all 16 ANSI terminal colors."""
        return {"colors": [
            {"name":"black","code":30,"hex":"#000000"},
            {"name":"red","code":31,"hex":"#800000"},
            {"name":"green","code":32,"hex":"#008000"},
            {"name":"yellow","code":33,"hex":"#808000"},
            {"name":"blue","code":34,"hex":"#000080"},
            {"name":"magenta","code":35,"hex":"#800080"},
            {"name":"cyan","code":36,"hex":"#008080"},
            {"name":"white","code":37,"hex":"#c0c0c0"},
            {"name":"bright_black","code":90,"hex":"#808080"},
            {"name":"bright_red","code":91,"hex":"#ff0000"},
            {"name":"bright_green","code":92,"hex":"#00ff00"},
            {"name":"bright_yellow","code":93,"hex":"#ffff00"},
            {"name":"bright_blue","code":94,"hex":"#0000ff"},
            {"name":"bright_magenta","code":95,"hex":"#ff00ff"},
            {"name":"bright_cyan","code":96,"hex":"#00ffff"},
            {"name":"bright_white","code":97,"hex":"#ffffff"},
        ]}

    @tool
    async def color_scheme_random(self) -> dict:
        """Generate a random harmonized color scheme."""
        import random
        h = random.randint(0, 360)
        return {
            "primary": f"hsl({h}, 70%, 50%)",
            "secondary": f"hsl({(h+180)%360}, 50%, 60%)",
            "accent": f"hsl({(h+60)%360}, 80%, 55%)",
            "neutral": f"hsl({h}, 10%, 90%)",
            "dark": f"hsl({h}, 15%, 20%)",
        }
