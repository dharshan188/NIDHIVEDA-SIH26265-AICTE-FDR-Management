"""Search production code assets for development-only text and simulator controls."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
patterns = ["demo", "OTP on screen", "Reset demo data", "Use demo credentials",
            "Bank debits (issues UTR)", "Bank returns payment", "Beneficiary bank confirms credit",
            "/api/sim/", "/sim/totp/", "/sim/otp-outbox/", "Sample FDR PDF", "Sign with simulated DSC"]
files = sorted(p for p in (root / "frontend/dist").rglob("*") if p.suffix in (".js", ".css", ".html"))
assert files, "No production bundle; build it first"
matches = []
for pattern in patterns:
    found = []
    for path in files:
        if re.search(re.escape(pattern), path.read_text(), re.I):
            found.append(str(path.relative_to(root)))
    print(f"{pattern!r}: {'FOUND in ' + ', '.join(found) if found else '0 matches'}")
    matches.extend(found)
print(f"Production assets searched: {len(files)}; matched assets (with repeats): {len(matches)}")
assert not matches, "Development-only content remains in production assets"
