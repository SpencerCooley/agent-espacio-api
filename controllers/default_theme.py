"""
Default theme seed definitions for new theme creation.

This module contains the hard-coded Mint Cream theme as the sensible
starting point for any newly created theme. It is NOT stored in the
database — it lives purely in code and is deep-copied when a user
creates a new theme without providing full definitions.
"""

DEFAULT_THEME_DEFINITION = {
    "light": {
        "palette": {
            "mode": "light",
            "primary": {
                "main": "#4caf50",
                "light": "#81c784",
                "dark": "#388e3c",
            },
            "secondary": {
                "main": "#9c27b0",
                "light": "#ce93d8",
                "dark": "#7b1fa2",
            },
            "background": {
                "default": "#fef7ed",
                "paper": "#fff9f0",
            },
            "text": {
                "primary": "#1a202c",
                "secondary": "#4a5568",
            },
            "error": {"main": "#e53e3e"},
            "warning": {"main": "#d69e2e"},
            "success": {"main": "#38a169"},
            "info": {"main": "#3182ce"},
        },
        "typography": {
            "fontFamily": '"Roboto", "Helvetica", "Arial", sans-serif',
            "h1": {
                "fontSize": "2.5rem",
                "fontWeight": 500,
            },
            "h2": {
                "fontSize": "2rem",
                "fontWeight": 500,
            },
            "button": {
                "textTransform": "none",
            },
        },
        "components": {
            "MuiButton": {
                "styleOverrides": {
                    "root": {
                        "borderRadius": 8,
                    },
                },
            },
        },
    },
    "dark": {
        "palette": {
            "mode": "dark",
            "primary": {
                "main": "#69f0ae",
                "light": "#a7ffeb",
                "dark": "#00e676",
            },
            "secondary": {
                "main": "#ce93d8",
                "light": "#f3e5f5",
                "dark": "#9c27b0",
            },
            "background": {
                "default": "#2d2d2d",
                "paper": "#3a3a3a",
            },
            "text": {
                "primary": "#f0f6fc",
                "secondary": "#8b949e",
            },
            "error": {"main": "#f85149"},
            "warning": {"main": "#d29922"},
            "success": {"main": "#3fb950"},
            "info": {"main": "#58a6ff"},
        },
        "typography": {
            "fontFamily": '"Roboto", "Helvetica", "Arial", sans-serif',
            "h1": {
                "fontSize": "2.5rem",
                "fontWeight": 500,
            },
            "h2": {
                "fontSize": "2rem",
                "fontWeight": 500,
            },
            "button": {
                "textTransform": "none",
            },
        },
        "components": {
            "MuiButton": {
                "styleOverrides": {
                    "root": {
                        "borderRadius": 8,
                    },
                },
            },
        },
    },
}
