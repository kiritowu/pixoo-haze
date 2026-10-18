#!/usr/bin/env python3
"""Show live Singapore 24-hour PSI readings on a Divoom Pixoo-64."""

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime


PSI_URL = "https://api-open.data.gov.sg/v2/real-time/api/psi"
WEATHER_URL = "https://api-open.data.gov.sg/v2/real-time/api/twenty-four-hr-forecast"
REGIONS = ("north", "south", "east", "west", "central")
SIZE = 64
ANIMATION_LEVELS = (0.70, 0.80, 0.90, 1.00, 1.00, 0.90, 0.80, 0.70)

# Tiny 3x5 font. Keeping it here avoids dependencies on Pillow or system fonts.
FONT = {
    " ": ("000", "000", "000", "000", "000"),
    "-": ("000", "000", "111", "000", "000"),
    ".": ("000", "000", "000", "000", "010"),
    ":": ("000", "010", "000", "010", "000"),
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("111", "100", "100", "100", "111"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("111", "100", "101", "101", "111"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "101", "111"),
    "K": ("101", "101", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("111", "101", "101", "101", "111"),
    "P": ("111", "101", "111", "100", "100"),
    "Q": ("111", "101", "101", "111", "001"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("111", "100", "111", "001", "111"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
}


def fetch_psi():
    headers = {"Accept": "application/json", "User-Agent": "pixoo-haze/1.0"}
    if os.getenv("DATA_GOV_SG_API_KEY"):
        headers["x-api-key"] = os.environ["DATA_GOV_SG_API_KEY"]

    request = urllib.request.Request(PSI_URL, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except urllib.error.URLError as error:
        raise RuntimeError(f"data.gov.sg request failed: {error.reason}") from error

    if payload.get("code") != 0:
        raise RuntimeError(payload.get("errorMsg") or "data.gov.sg returned an error")

    item = payload["data"]["items"][0]
    readings = item["readings"]["psi_twenty_four_hourly"]
    values = {region: int(readings[region]) for region in REGIONS}
    return values, item["timestamp"]


def fetch_weather():
    headers = {"Accept": "application/json", "User-Agent": "pixoo-haze/1.0"}
    if os.getenv("DATA_GOV_SG_API_KEY"):
        headers["x-api-key"] = os.environ["DATA_GOV_SG_API_KEY"]

    request = urllib.request.Request(WEATHER_URL, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except urllib.error.URLError as error:
        raise RuntimeError(f"data.gov.sg weather request failed: {error.reason}") from error

    if payload.get("code") != 0:
        raise RuntimeError(payload.get("errorMsg") or "data.gov.sg returned a weather error")

    record = payload["data"]["records"][0]
    temperature = record["general"]["temperature"]
    reading_time = datetime.fromisoformat(record["timestamp"])
    current_period = next(
        (
            period
            for period in record["periods"]
            if datetime.fromisoformat(period["timePeriod"]["start"])
            <= reading_time
            < datetime.fromisoformat(period["timePeriod"]["end"])
        ),
        record["periods"][0],
    )
    return {
        "forecast": current_period["regions"]["west"]["text"],
        "low": int(temperature["low"]),
        "high": int(temperature["high"]),
        "date": record["general"]["validPeriod"]["start"],
    }


def psi_style(value):
    if value <= 50:
        return "GOOD", (40, 210, 100)
    if value <= 100:
        return "MODERATE", (245, 210, 55)
    if value <= 200:
        return "UNHEALTHY", (255, 125, 35)
    if value <= 300:
        return "VERY UNHEALTHY", (245, 45, 55)
    return "HAZARDOUS", (170, 55, 210)


def set_pixel(frame, x, y, color):
    if 0 <= x < SIZE and 0 <= y < SIZE:
        offset = (y * SIZE + x) * 3
        frame[offset : offset + 3] = bytes(color)


def fill_rect(frame, x, y, width, height, color):
    for row in range(y, y + height):
        for column in range(x, x + width):
            set_pixel(frame, column, row, color)


def text_width(text, scale=1):
    return max(0, len(text) * 4 * scale - scale)


def draw_text(frame, text, x, y, color, scale=1):
    cursor = x
    for character in text.upper():
        glyph = FONT.get(character, FONT[" "])
        for row, bits in enumerate(glyph):
            for column, bit in enumerate(bits):
                if bit == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            set_pixel(
                                frame,
                                cursor + column * scale + dx,
                                y + row * scale + dy,
                                color,
                            )
        cursor += 4 * scale


def draw_centered(frame, text, y, color, scale=1, x_offset=0):
    draw_text(
        frame,
        text,
        (SIZE - text_width(text, scale)) // 2 + x_offset,
        y,
        color,
        scale,
    )


def dim_color(color, level):
    return tuple(round(channel * level) for channel in color)


def nus_week_label(day):
    first_block = datetime(2026, 8, 10).date()
    second_block = datetime(2026, 9, 28).date()
    if first_block <= day <= datetime(2026, 9, 18).date():
        return f"W{(day - first_block).days // 7 + 1}"
    if second_block <= day <= datetime(2026, 11, 13).date():
        return f"W{(day - second_block).days // 7 + 7}"
    return ""


def draw_cloud(frame, x, y):
    blue = (105, 155, 205)
    cloud = (225, 230, 228)
    mask = (
        "......BBBB............",
        ".....BWWWWWWW.........",
        ".....BWWWWWWWW.BBB....",
        ".....BWWWWWWWWBWWW....",
        "..BBBWWWWWWWWWBWWWWW..",
        ".BWWWWWWWWWWWBBWWWWWW.",
        ".BWWWWWWWWWWBWWWWWWWWW",
        ".BWWWWWWWWWWBWWWWWWWWW",
        ".BBWWWWWWWWWWWWWWWWWWW",
        "..BBBBBBBBBBBBBBBBBBBB.",
        "....BBBBBBBBBBBBBBB....",
    )
    for row, pixels in enumerate(mask):
        for column, pixel in enumerate(pixels):
            if pixel == "B":
                set_pixel(frame, x + column, y + row, blue)
            elif pixel == "W":
                set_pixel(frame, x + column, y + row, cloud)


def draw_weather_icon(frame, forecast, animation_frame):
    condition = forecast.upper()
    x = 9
    y = 42
    yellow = dim_color((255, 205, 45), ANIMATION_LEVELS[animation_frame])

    if any(word in condition for word in ("HAZY", "MIST", "FOG")):
        fill_rect(frame, x + 7, y, 6, 6, yellow)
        for offset, width in ((7, 17), (10, 13)):
            fill_rect(frame, x + 2, y + offset, width, 2, (125, 160, 175))
    elif "WIND" in condition:
        for row, width in ((2, 15), (6, 19), (10, 12)):
            fill_rect(frame, x + 2, y + row, width, 2, (95, 205, 235))
    elif any(word in condition for word in ("RAIN", "SHOWER")):
        draw_cloud(frame, x, y)
        rain_y = y + 11 + animation_frame % 2
        for rain_x in (x + 5, x + 10, x + 15):
            set_pixel(frame, rain_x, rain_y, (65, 155, 255))
            set_pixel(frame, rain_x - 1, rain_y + 1, (65, 155, 255))
        if "THUNDER" in condition:
            fill_rect(frame, x + 10, y + 9, 2, 3, (255, 220, 40))
            set_pixel(frame, x + 9, y + 12, (255, 220, 40))
    elif "CLOUD" in condition:
        if "PARTLY" in condition:
            fill_rect(frame, x + 1, y, 6, 6, yellow)
        draw_cloud(frame, x, y + 2)
    else:
        fill_rect(frame, x + 7, y + 3, 7, 7, yellow)
        for sun_x, sun_y in ((10, 0), (10, 12), (4, 6), (16, 6)):
            set_pixel(frame, x + sun_x, y + sun_y, yellow)


def render_screen(values, weather, animation_frame=0):
    frame = bytearray((4, 8, 14) * (SIZE * SIZE))
    value = values["west"]
    category, accent = psi_style(value)
    display_date = datetime.fromisoformat(weather["date"]).date()
    date_text = display_date.strftime("%a %d %b").upper()
    week = nus_week_label(display_date)
    heading = f"{week} {date_text}" if week else date_text

    level = ANIMATION_LEVELS[animation_frame]

    draw_centered(frame, heading, 2, (235, 240, 245))
    draw_centered(frame, "24H PSI", 10, (190, 205, 220))
    draw_centered(frame, str(value), 17, dim_color(accent, level), scale=3)
    draw_centered(frame, category, 34, accent)
    draw_weather_icon(frame, weather["forecast"], animation_frame)
    temperature = f"{weather['low']}-{weather['high']}C"
    draw_text(
        frame,
        temperature,
        48 - text_width(temperature) // 2,
        47,
        (100, 195, 245),
    )
    draw_centered(
        frame,
        "TECHD X MAKERS",
        58,
        dim_color((235, 240, 245), 0.85 + 0.15 * level),
    )
    return frame


def post_pixoo(ip_address, payload):
    request = urllib.request.Request(
        f"http://{ip_address}/post",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                result = json.load(response)
            break
        except urllib.error.URLError as error:
            last_error = error
            if attempt < 2:
                time.sleep(2)
    else:
        raise RuntimeError(
            f"Pixoo at {ip_address} is unreachable: {last_error.reason}"
        ) from last_error
    if result.get("error_code", result.get("errorCode", 0)) != 0:
        raise RuntimeError(f"Pixoo rejected the request: {result}")


def push_animation(ip_address, frames, speed_ms=250):
    post_pixoo(ip_address, {"Command": "Draw/ResetHttpGifId"})
    picture_id = int(time.time())
    for index, frame in enumerate(frames):
        post_pixoo(
            ip_address,
            {
                "Command": "Draw/SendHttpGif",
                "PicNum": len(frames),
                "PicWidth": SIZE,
                "PicOffset": index,
                "PicID": picture_id,
                "PicSpeed": speed_ms,
                "PicData": base64.b64encode(frame).decode(),
            },
        )


def write_ppm(path, frame):
    with open(path, "wb") as output:
        output.write(f"P6\n{SIZE} {SIZE}\n255\n".encode())
        output.write(frame)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pixoo-ip", help="Pixoo-64 IP address on the local network")
    parser.add_argument("--once", action="store_true", help="Update once, then exit")
    parser.add_argument("--preview", metavar="FILE", help="Write a 64x64 PPM preview")
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.pixoo_ip and not args.preview:
        raise SystemExit("Provide --pixoo-ip, --preview, or both")

    while True:
        failed = False
        try:
            values, timestamp = fetch_psi()
            weather = fetch_weather()
            frames = [
                render_screen(values, weather, index)
                for index in range(len(ANIMATION_LEVELS))
            ]
            if args.preview:
                write_ppm(args.preview, frames[3])
            if args.pixoo_ip:
                push_animation(args.pixoo_ip, frames)
            print(f"Updated {timestamp}: {values} (8-frame animation)", flush=True)
        except Exception as error:
            failed = True
            print(f"Update failed: {error}", flush=True)
            if args.once:
                raise

        if args.once:
            break
        time.sleep(60 if failed else 15 * 60)


if __name__ == "__main__":
    main()
