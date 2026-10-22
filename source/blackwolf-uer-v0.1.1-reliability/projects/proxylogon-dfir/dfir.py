import re

def detect_iis(line: str) -> list[str]:
    """Training detector: suspicious Exchange request patterns, not incident attribution."""
    indicators = []
    if re.search(r"/ecp/.*\.js(?:\?|$)", line, re.I):
        indicators.append("suspicious_ecp_js")
    if "X-BEResource=".lower() in line.lower():
        indicators.append("x_beresource")
    if re.search(r"/aspnet_client/[^ ]+\.aspx", line, re.I):
        indicators.append("possible_webshell_path")
    return indicators
