import re

def bbcode_to_html(text: str) -> str:
    safe = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    safe = re.sub(r"\[b\](.*?)\[/b\]", r"<b>\1</b>", safe, flags=re.DOTALL)
    safe = re.sub(r"\[i\](.*?)\[/i\]", r"<i>\1</i>", safe, flags=re.DOTALL)
    safe = re.sub(r"\[u\](.*?)\[/u\]", r"<u>\1</u>", safe, flags=re.DOTALL)
    safe = re.sub(r"\[s\](.*?)\[/s\]", r"<s>\1</s>", safe, flags=re.DOTALL)

    size_map = {
        "1": "7pt",
        "2": "9pt",
        "3": "11pt",
        "4": "14pt",
        "5": "18pt",
        "6": "24pt",
        "7": "32pt",
    }
    def replace_size(m):
        sz = m.group(1)
        content = m.group(2)
        px = size_map.get(sz, "11pt")
        return f'<span style="font-size: {px};">{content}</span>'
    safe = re.sub(r"\[size=(\d)\](.*?)\[/size\]", replace_size, safe, flags=re.DOTALL)

    safe = re.sub(r"\[color=([#a-zA-Z0-9]+)\](.*?)\[/color\]", r'<span style="color: \1;">\2</span>', safe, flags=re.DOTALL)

    safe = re.sub(r"\[left\](.*?)\[/left\]", r'<div style="text-align: left;">\1</div>', safe, flags=re.DOTALL)
    safe = re.sub(r"\[center\](.*?)\[/center\]", r'<div style="text-align: center;">\1</div>', safe, flags=re.DOTALL)
    safe = re.sub(r"\[right\](.*?)\[/right\]", r'<div style="text-align: right;">\1</div>', safe, flags=re.DOTALL)

    safe = re.sub(r"\[li\](.*?)\[/li\]", r"<li>\1</li>", safe, flags=re.DOTALL)
    safe = re.sub(r"\[ul\](.*?)\[/ul\]", r"<ul>\1</ul>", safe, flags=re.DOTALL)
    safe = re.sub(r"\[ol\](.*?)\[/ol\]", r"<ol>\1</ol>", safe, flags=re.DOTALL)

    safe = re.sub(
        r"\[quote\](.*?)\[/quote\]",
        r'<blockquote style="border-left: 3px solid #3b82f6; margin: 5px 0; padding-left: 10px; color: #a0a6b5;">\1</blockquote>',
        safe,
        flags=re.DOTALL,
    )
    safe = re.sub(
        r"\[code\](.*?)\[/code\]",
        r'<pre style="background: #14161c; padding: 6px; border-radius: 4px; font-family: Consolas, monospace; color: #79d279;">\1</pre>',
        safe,
        flags=re.DOTALL,
    )

    safe = re.sub(r"\[url=(.*?)\](.*?)\[/url\]", r'<a href="\1" style="color: #3b82f6;">\2</a>', safe, flags=re.DOTALL)

    def replace_img_scaled(m):
        dims = m.group(1)
        url = m.group(2)
        w, h = "", ""
        if "x" in dims:
            w, h = dims.split("x", 1)
        style = ' style="'
        if w: style += f'width: {w}px; '
        if h: style += f'height: {h}px; '
        style += '"'
        return f'<img src="{url}"{style} />'

    safe = re.sub(r"\[img=([0-9]*x?[0-9]*)\](.*?)\[/img\]", replace_img_scaled, safe, flags=re.DOTALL)
    safe = re.sub(r"\[img\](.*?)\[/img\]", r'<img src="\1" style="max-width: 100%;" />', safe, flags=re.DOTALL)

    safe = safe.replace("\n", "<br>")
    return safe