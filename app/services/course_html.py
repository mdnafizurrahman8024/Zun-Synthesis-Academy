from urllib.parse import urlparse

import nh3

ALLOWED_TAGS = {
    "p", "br", "h1", "h2", "h3", "h4", "strong", "b", "em", "i", "u", "s",
    "ol", "ul", "li", "blockquote", "a", "img", "iframe",
}
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "width", "height"},
    "iframe": {"src", "title", "allow", "allowfullscreen", "loading", "referrerpolicy", "width", "height"},
}


def _allow_attribute(tag: str, attribute: str, value: str) -> bool:
    if attribute not in ALLOWED_ATTRIBUTES.get(tag, set()):
        return False
    if tag == "iframe" and attribute == "src":
        parsed = urlparse(value)
        return (
            parsed.scheme == "https"
            and (
                (parsed.hostname in {"www.youtube-nocookie.com", "www.youtube.com"} and parsed.path.startswith("/embed/"))
                or (parsed.hostname == "player.vimeo.com" and parsed.path.startswith("/video/"))
            )
        )
    if tag == "img" and attribute == "src":
        parsed = urlparse(value)
        return value.startswith("/uploads/") or (parsed.scheme == "https" and bool(parsed.hostname))
    if tag == "a" and attribute == "href":
        parsed = urlparse(value)
        return not parsed.scheme or parsed.scheme in {"https", "http", "mailto"}
    return True


def sanitize_course_html(value: str) -> str:
    return nh3.clean(
        value or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        attribute_filter=_allow_attribute,
        url_schemes={"https", "http", "mailto"},
        link_rel="noopener noreferrer",
    )
