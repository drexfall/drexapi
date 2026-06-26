DEFAULT_THEME = {
	"bg_color": "#0c0d11",
	"surface_color": "#161820",
	"accent_color": "#c9a254",
	"text_color": "#f0f0f2",
	"muted_color": "#8b92a0",
	"font_family": "Cinzel, Georgia, serif",
}

CATEGORY_COLORS = {
	"tech": "#3b82f6",
	"business": "#10b981",
	"politics": "#ef4444",
	"sports": "#f59e0b",
	"world": "#8b5cf6",
	"india": "#f97316",
	"health": "#06b6d4",
	"science": "#6366f1",
	"entertainment": "#ec4899",
	"other": "#6b7280",
}


def category_color(cat: str) -> str:
	return CATEGORY_COLORS.get((cat or "").lower(), CATEGORY_COLORS["other"])
