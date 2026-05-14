from fastapi.routing import APIRoute


def simple_generate_unique_route_id(route: APIRoute):
    return f"{route.tags[0]}-{route.name}"


def strip_markdown_for_student_chat(text: str) -> str:
    """Remove paired **bold** markers for student-facing chat strings."""
    t = text or ""
    while "**" in t:
        start = t.find("**")
        if start == -1:
            break
        end = t.find("**", start + 2)
        if end == -1:
            return t.replace("**", "", 1)
        inner = t[start + 2 : end]
        t = t[:start] + inner + t[end + 2 :]
    return t
