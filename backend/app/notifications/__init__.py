"""In-app alerts (docs/plans/10-alerts.md).

`categories.py` decides what is worth an alert (pure), `service.py` turns an analysis into one alert per invoice
version, `channels.py` delivers it (in-app now; email and browser notifications are added as more channels), and
`router.py` is the API the extension polls.
"""
