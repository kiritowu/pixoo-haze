# Pixoo Haze Display

Displays live West-region 24-hour PSI plus today's date, current West-region
forecast and daily temperature range from data.gov.sg on a Divoom Pixoo-64. It
uses only Python's standard library.

The display is uploaded as an eight-frame loop: the PSI value gently pulses,
the graphical weather icon animates for the current condition, and the footer
subtly changes brightness. The Pixoo loops those frames locally until the next
15-minute data refresh.

## Test with a preview

```bash
python3 pixoo_haze.py --preview haze.ppm --once
```

Open `haze.ppm` to inspect the 64x64 screen without a Pixoo.

## Send it to the Pixoo

The laptop and Pixoo must be on the same local network. Replace the example IP:

```bash
python3 pixoo_haze.py --pixoo-ip 192.168.1.123 --once
```

Remove `--once` to keep it running and refresh every 15 minutes:

```bash
python3 pixoo_haze.py --pixoo-ip 192.168.1.123
```

If either network request fails, the service identifies whether data.gov.sg or
the Pixoo was unreachable and retries after one minute. Pixoo requests also get
three short retries to tolerate brief Wi-Fi or hotspot interruptions.

The large number is the West region's 24-hour PSI, chosen for NUS College's
location in western Singapore. The date header includes the current NUS
AY2026/27 instructional week. The footer is labelled `TECHD X MAKERS`.

The public API works without a key. For a higher data.gov.sg rate limit, set
`DATA_GOV_SG_API_KEY` in the environment.
