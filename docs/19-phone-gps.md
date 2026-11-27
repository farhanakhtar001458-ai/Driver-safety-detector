# Phone GPS sharing

On the Live Tracking page, an organisation admin, fleet manager, or driver can opt in to share the current browser's location for an eligible vehicle. A driver can only use a vehicle assigned to their linked driver profile; admins and fleet managers can select non-archived vehicles in their own organisation. The server checks this on every request.

1. Add a vehicle and, for a driver account, link the user to a driver profile and assign that driver to the vehicle.
2. Open the website over HTTPS in an Android browser, sign in and open **Live Tracking**.
3. Select a vehicle, tick the location-sharing consent box, tap **Start phone GPS** and allow browser location permission.
4. Keep the page visible. Tap **Stop sharing** when finished. Leaving or hiding the page stops the watch; a request already in progress can still finish.

The browser sends at most one fresh GPS position every 15 seconds when available, and rejects stale or very inaccurate readings. Server records use `source=phone` and `is_simulated=false`. Location is sensitive data visible to authorised organisation users: obtain appropriate consent, set retention and access policies, and test on the intended devices before operational use.

Phone locations are self-reported, can be spoofed or inaccurate, and are not proof the phone is in the vehicle. The existing database requires speed, heading and ignition values, so missing values are stored as placeholders; the tracking UI labels these as unverified for phone data. No trips, geofence alerts, driver scores, sleep detection or risk events are generated from this phone location endpoint. It does not contact emergency services. The page must remain open and visible; browser background tracking is not guaranteed.

Both the backend and frontend must be deployed together. GPS requires HTTPS (or a browser's secure localhost development exception). This feature has automated tests but still needs testing on real Android hardware and a privacy/security review before production.
