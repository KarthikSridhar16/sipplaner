import re


def plan_of(text: str) -> str:
    words = set(re.findall(r"[a-z]+", text.lower()))
    if "direct" in words or "dir" in words:
        return "Direct"
    if "regular" in words or "reg" in words:
        return "Regular"
    return "Unknown"


def option_of(text: str) -> str:
    lowered = text.lower()
    if re.search(r"\b(idcw|dividend|income distribution)\b", lowered):
        return "IDCW"
    if re.search(r"\b(growth|gr)\b", lowered):
        return "Growth"
    return "Unknown"


def scheme_key(text: str) -> str:
    # Exact normalized matching only. No fuzzy acceptance of a nearby scheme.
    text = re.sub(r"(?i)\bmid[ -]?cap\b", "midcap", text)
    text = re.sub(r"(?i)\bsmall[ -]?cap\b", "smallcap", text)
    text = re.sub(r"(?i)\blarge[ -]?cap\b", "largecap", text)
    words = re.findall(r"[a-z0-9]+", text.lower())
    ignored = {"direct", "regular", "plan", "option", "growth", "fund", "and"}
    return " ".join(w for w in words if w not in ignored)


def same_growth_fund(scheme: str, plan: str, candidate: str) -> bool:
    return (plan != "Unknown" and plan_of(candidate) == plan
            and option_of(candidate) == "Growth" and scheme_key(scheme) == scheme_key(candidate))


def advisor_slug(name: str) -> str:
    # Matches getSchemeAmfiUrl in the provider's public common.js.
    name = re.sub(r"[()]", "", name)
    name = re.sub(r"[-&_/.:'%\[\]<>=+,]", " ", name)
    return "-".join(name.split())
