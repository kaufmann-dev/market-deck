"""Standalone HTML error pages for browser requests outside the JSON API."""

_COPY = {
    403: ("Access denied", "You don't have permission to view this page."),
    404: ("Page not found", "This page doesn't exist. It may have been moved, or the address has a typo."),
    500: ("Something went wrong", "An unexpected error occurred. Try again in a moment."),
}
_CLIENT_ERROR = ("Request could not be completed", "The request was invalid.")


def render_error_page(status: int) -> str:
    title, message = _COPY.get(status) or (_COPY[500] if status >= 500 else _CLIENT_ERROR)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex">
  <title>{title} · Market Deck</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; }}
    body {{
      display: grid; place-items: center; min-height: 100vh; padding: 24px;
      background: #000000; color: #ffffff; text-align: center;
      font-family: 'Google Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    main {{ max-width: 420px; }}
    .status {{
      color: #a0a0a0; font-size: 12px; font-weight: 600;
      letter-spacing: 0.08em; text-transform: uppercase;
    }}
    h1 {{ margin-top: 10px; font-size: 28px; font-weight: 600; }}
    p.message {{ margin-top: 10px; color: #a0a0a0; line-height: 1.5; }}
    a {{
      display: inline-block; margin-top: 24px; padding: 10px 18px; border: 1px solid #333333;
      border-radius: 8px; color: #ffffff; font-weight: 600; text-decoration: none;
    }}
    a:hover {{ border-color: #555555; background: rgba(255, 255, 255, 0.07); }}
    a:focus-visible {{ outline: 2px solid #ffffff; outline-offset: 2px; }}
  </style>
</head>
<body>
  <main>
    <p class="status">Error {status}</p>
    <h1>{title}</h1>
    <p class="message">{message}</p>
    <a href="/">Back to Market Deck</a>
  </main>
</body>
</html>
"""
