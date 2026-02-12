"""Color palette constants for dark theme.

Reference: FRD §6 — UI/UX Design.
"""

# Base theme colors
BACKGROUND = "#0F172A"
PANEL_BG = "#1E293B"
SURFACE = "#334155"
BORDER = "#475569"

# Canvas background (slightly lighter for better contrast)
CANVAS_BG = "#151E31"

# Accent colors
ACCENT = "#3B82F6"
ACCENT_HOVER = "#60A5FA"
ACCENT_PRESSED = "#2563EB"

# Semantic colors
WARNING = "#F59E0B"
ERROR = "#EF4444"
SUCCESS = "#10B981"

# Text colors
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#B0BEC5"  # brighter than old #94A3B8
TEXT_DISABLED = "#64748B"

# Material display colors (brighter/more saturated for canvas visibility)
MATERIAL_COLORS = {
    "Pb": "#7986CB",        # Lead — brighter blue-purple
    "W": "#FF8A65",         # Tungsten — brighter orange
    "SS304": "#90A4AE",     # Stainless 304 — brighter gray-blue
    "SS316": "#B0BEC5",     # Stainless 316 — lighter gray
    "Bi": "#CE93D8",        # Bismuth — brighter purple
    "Al": "#81C784",        # Aluminum — brighter green
    "Cu": "#EF5350",        # Copper — red (already bright)
    "Bronze": "#FFB74D",    # Bronze — brighter orange
}

# Phantom display colors
PHANTOM_WIRE = "#42A5F5"    # brighter blue
PHANTOM_LINE_PAIR = "#AB47BC"  # brighter purple
PHANTOM_GRID = "#26C6DA"    # brighter cyan
