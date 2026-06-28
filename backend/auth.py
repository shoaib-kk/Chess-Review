"""Anonymous per-device identity.

There are no accounts. On first visit the browser generates a random UUID, stores
it in ``localStorage``, and sends it as the ``X-Device-Id`` header on every
request. That UUID *is* the credential: with 122 bits of entropy it is
unguessable, so it both scopes a device's data and prevents one device from
reaching another's (you can't target an id you can't guess). No server-issued
token or signing is needed — possession of the UUID is the whole capability.

This is privacy-friendly (no username required) and makes per-device data — e.g.
puzzle streaks — "just work" and persist on that device.

Threat model (deliberate, documented tradeoff — NOT an oversight)
-----------------------------------------------------------------
The device id is a *bearer capability*, and a weak one by design:

  * It lives in ``localStorage``, so it is readable by any script on the page —
    a single XSS bug exfiltrates it. It also rides in the URL/headers and can be
    leaked through a shared link, copy-paste, proxy log, or browser sync.
  * There is NO rotation, expiry, revocation, or binding to the browser/IP. Once
    an id leaks, the holder has the device's data forever; there is no way to
    "log out" or invalidate it server-side.
  * The 122 bits of entropy only stop *guessing*. They do nothing against
    *theft* of a known id.

This is acceptable ONLY because the data it guards is low-sensitivity: a user's
own chess game reviews, mined puzzles, drills, and streaks. Worst case on
compromise is that someone sees or perturbs another person's chess practice
data — there is no PII, money, or account takeover at stake.

Consequently this mechanism MUST NOT be reused to protect anything sensitive
(payments, real identity, private messages, admin actions, etc.). Anything in
that class needs real authentication (server-issued, signed, rotatable tokens),
not a localStorage UUID.
"""

from __future__ import annotations

import uuid

from fastapi import Header, HTTPException

DEVICE_HEADER = "X-Device-Id"

# The nil UUID is a guessable "default" value that some clients/libraries emit
# when an id is unset. Rejecting it stops every such caller from colliding on one
# shared ownership bucket (and an attacker from trivially probing it).
_NIL_UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def current_device(x_device_id: str = Header(..., alias=DEVICE_HEADER)) -> str:
    """FastAPI dependency: the caller's validated device id.

    Requires a well-formed UUID so junk values can't pollute the ownership
    column or be used to probe for data. Returns the canonical lowercase form.
    """
    try:
        device = uuid.UUID(x_device_id.strip())
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Missing or invalid device id.") from exc
    # Reject the all-zero "default" id — it is not a real per-device capability.
    if device == _NIL_UUID:
        raise HTTPException(status_code=400, detail="Missing or invalid device id.")
    return str(device)
