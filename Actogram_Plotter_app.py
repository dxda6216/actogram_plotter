#!/usr/bin/env python3
"""
Actogram Plotter (desktop app)

    Draws a double-plotted (or single-plotted) actogram from peak and trough times given
    in hours after time zero, together with the light/dark conditions of the experiment,
    and analyses the period and phase of selected peaks and troughs.

    Settings column (left)
    * Green areas = values from your records (enter them exactly):
      - Clock time of the data: the local date/time of 0 h and its time zone (default US
        Central Time, America/Chicago); every date/time is picked in a calendar picker and
        entered as local wall-clock time - daylight saving time is handled automatically.
      - Peaks and troughs (h after 0 h; one value per line).  Load example / Clear data /
        Clear all (asks first).
        Or "Detect them in time-series data" (the default input): paste or open a time
        series (column 1 = time in h after 0 h, or a date and time in ISO 8601 form such as
        2026-10-05T10:15:00-0500 or 20261005T1015; column 2 = signal, e.g. bioluminescence;
        tab, space or comma separated; header lines skipped).  Two examples: hours, and an
        8-minute record with dates/times and its own LD 12:12 / LL / LD 11.5:11.5 / DD schedule.  As in ttron2excel_data_analysis.py: unequal
        intervals are resampled onto a regular grid, the trend (Sinc Filter: cutoff period
        and order; or Moving Average: window) is subtracted, and the peaks/troughs are the
        maxima/minima of the raw data (default) or of the detrended data, optionally after a
        centred moving average (1 = none, 3, 5, 7 (default), ... 15 points), at least the minimum
        spacing (default 12 h) apart.  The
        time-series window shows the raw data with the trend line and the detection curve
        with the markers (click to remove, or to add a peak/trough), and, when light/dark
        conditions are shown, a light/dark bar above each plot.  The detected times feed the
        actogram and the phase analysis like typed values.
      - Sample placement: when the samples were put into the conditions.
      - Light/dark conditions: one card per condition (LD with L, D and Light/Dark first;
        LL; DD) and its start; Add condition / x.  L and D are picked with a mouse-wheel
        picker (click the field).  After an LD condition, the start picker suggests the
        ends of D or L of that LD cycle.
    * Blue areas = view settings (change freely): actogram day 0, 0 h (six choices),
      period T (0:01-240:00, with a one-click 24:00 reset), double/single plot, row labels,
      major/minor ticks, colours of the light and dark bands (12 each), labels of light
      and dark onsets and of each cycle's start, asterisks at 0 h (green) and at the sample
      placement (orange), light-purple lines at condition changes; with time-series input
      the data themselves can be drawn in every row as activity bars or a heat map.

    Right side
    * Fine-tune (above the actogram): day 0, 0 h and period T in 1-minute steps; rows.
    * The actogram (matplotlib, with the usual zoom/pan toolbar).
    * Phase analysis (below): click a point or drag a box to select peaks/troughs (Alt:
      deselect; switch the toolbar's zoom/pan off first).
        LD:    phase = ZT / (L + D) x 360 deg (circular mean, r, circular SD).
        LL/DD: t = b + tau*n fitted on the cycle number n (cycle 0 begins at the chosen
               0 deg reference); tau = period, phase = (b mod tau)/tau x 360 deg,
               Phase (CT) = (b mod tau) x 24/tau; SE, R^2.
      Fitted lines can be drawn on the actogram.  Results: table, "Phase results..." window
      (dials and tables per condition, savable as an image), CSV export, clipboard copy.
    * Save the figure as PNG, SVG or PDF; save/load all settings as JSON (the same format as
      the web version, https://dxda6216.github.io/actogram_plotter/).
      Display options are kept between sessions in ~/.actogram_plotter.json; every session
      starts with the example data (title "Example Data"), T = 24:00 and America/Chicago.

Requirements
    Python 3.9+ and:   pip install matplotlib        (numpy comes with it)
    On Windows also:   pip install tzdata      (time zone data; without it the US
                                               zones still work with built-in rules)
    tkinter ships with Python on Windows and macOS (python.org installers).
    On Debian/Ubuntu:  sudo apt install python3-tk

Run
    python Actogram_Plotter_app.py

Build a double-clickable app (run on each OS you want to target):
    pip install pyinstaller
    pyinstaller --onefile --windowed --name Actogram_Plotter Actogram_Plotter_app.py
    Windows, with the icon (Actogram_Plotter.ico next to this script):
    pyinstaller --onefile --windowed --name Actogram_Plotter --icon Actogram_Plotter.ico
                --add-data "Actogram_Plotter.ico;." --hidden-import tzdata Actogram_Plotter_app.py
    (macOS / Linux: use ':' instead of ';' in --add-data, and Actogram_Plotter.png)
"""

from __future__ import annotations

# =========================================================================== #
# How this file is organised
# =========================================================================== #
# The program has two layers:
#
# 1. A pure computation layer (no tkinter): functions that take the *settings dictionary*
#    and return plain data.  The settings dictionary is the single source of truth: it is
#    what the controls show, what get_settings()/apply_settings() exchange with the UI, and
#    what is written to a settings file (the same JSON keys as the web version index.html).
#      - Time zones and local clock times ........ get_time_zone, parse_local, local_to_utc
#      - compute(settings) -> Result .............. 0 h, LD schedule, placement, origin, period
#      - analyze_series(settings) ................. time series -> trend -> peaks/troughs
#      - analyze(settings, Result) ................ phase/period of the selected points
#      - draw_actogram(fig, settings, Result) ..... the figure (matplotlib)
#    All times inside the program are *hours after 0 h of the data* (floats).  Clock times
#    are converted to UTC once (local_to_utc) and then to hours, so daylight-saving changes
#    never distort intervals.
#
# 2. The user interface (tkinter): App builds the controls, keeps one Tk variable per
#    setting and calls redraw() whenever something changes.  Helper widgets: TimeField
#    (hh:mm with a mouse-wheel pop-up), DateTimeField/DateTimePicker (calendar picker that
#    knows about clock changes), ScrollFrame, Tooltip, SeriesWindow (time-series plot).
#
# Sections below, in order: constants and palettes; time zones; parsing and formatting;
# the light/dark model and compute(); time-series analysis (parsing incl. ISO 8601 dates,
# resampling, detrending, peak detection, hand edits); drawing the series in the actogram;
# phase analysis; drawing the actogram; examples and defaults; widgets; the App.

# Standard library: calendar (month names/grids for the date picker), contextlib (suppress errors
# when closing windows), json (settings files), math, re (parsing typed text), sys (platform
# checks for mouse-wheel handling), dataclasses (plain record types), datetime (all clock-time
# work), pathlib (file paths).
import calendar
import contextlib
import json
import math
import re
import unicodedata
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path

# tkinter = the GUI toolkit that ships with Python; ttk = its themed widgets.
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# matplotlib draws the actogram and the time-series plot; numpy does the array maths of the
# time-series analysis (filtering, peak finding).
import matplotlib
import matplotlib.lines
import numpy as np            # comes with matplotlib

# Use the Tk backend so the figures can be embedded in the tkinter window.  This must be
# selected before pyplot/backends are imported, hence the 'noqa: E402' on the imports below.
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import AutoMinorLocator, FormatStrFormatter, NullFormatter  # noqa: E402

# zoneinfo (Python 3.9+) provides the IANA time-zone database (America/Chicago, Asia/Tokyo, ...).
# On Windows it also needs the 'tzdata' package; without it the US zones fall back to the
# built-in rules of _USRuleZone below.
try:
    from zoneinfo import ZoneInfo
except ImportError:          # Python < 3.9
    ZoneInfo = None

# ---- general constants -------------------------------------------------------------
# APP_NAME: window titles and message boxes.  LD_MODES: the three kinds of condition.
# LD_MAX_HOURS: the longest L or D that can be entered (99:59).  MAX_CHANGES: up to 5
# changes after the first condition, i.e. 6 condition cards.
APP_NAME = "Actogram Plotter"
LD_MODES = ("LD", "LL", "DD")
LD_MAX_HOURS = 99 + 59 / 60      # L and D lengths: 00:00 - 99:59
MAX_CHANGES = 5
# colours of the light and dark bands (12 each; the first is the default)
# Each palette entry is (name shown to the user, hex colour).  The settings store the hex code;
# pick_color() maps it back (unknown values fall back to the first entry).
LIGHT_COLORS = (
    ("Pale yellow", "#fff8d6"),
    ("Lemon", "#fff9c4"),
    ("Cream", "#fffbf0"),
    ("Amber", "#ffecb3"),
    ("Peach", "#ffe8d2"),
    ("Apricot", "#ffe0b2"),
    ("White", "#ffffff"),
    ("Pale green", "#eaf4df"),
    ("Mint", "#dff1e0"),
    ("Sky", "#e6f2fb"),
    ("Pale pink", "#fbe6e8"),
    ("Lavender", "#f0ecf8"),
)
DARK_COLORS = (
    ("Light grey", "#dadada"),
    ("Grey", "#c4c4c4"),
    ("Mid grey", "#adadad"),
    ("Dark grey", "#969696"),
    ("Graphite", "#808080"),
    ("Slate", "#c3c9d2"),
    ("Blue grey", "#aebbcc"),
    ("Steel", "#9dadc7"),
    ("Indigo", "#a9abcf"),
    ("Purple grey", "#bfb5cc"),
    ("Taupe", "#c4bbb1"),
    ("Teal grey", "#9dbab8"),
)
# Default band colours (first entry of each palette).
LIGHT_COLOR, DARK_COLOR = LIGHT_COLORS[0][1], DARK_COLORS[0][1]


# Look up a colour in a palette.  `value` may be a hex code ('#fff8d6') or a palette name
# ('Pale yellow'), in any letter case; anything else (empty, a typo, an old colour) gives the
# palette's default so the drawing never fails because of a bad setting.
def pick_color(value, palette):
    """A colour of the palette (by hex code or name); the palette's first colour otherwise."""
    # normalise the stored value for comparison
    v = str(value or "").strip().lower()
    # accept either the hex code or the name
    for name, hex_code in palette:
        if v in (hex_code, name.lower()):
            return hex_code
    # not found -> default colour
    return palette[0][1]
# ---- colours and symbols used in the plots ----------------------------------------
PEAK_COLOR = "#d32f2f"
TROUGH_COLOR = "#1f4fd1"
PLACED_COLOR = "#f57c00"       # orange asterisk: when the samples were put into the conditions
ZERO_COLOR = "#2e7d32"         # green asterisk: 0 h of the data
CHANGE_COLOR = "#b39ddb"       # light purple: start of each light/dark condition
ASTERISK = (6, 2, 0)           # matplotlib marker: six-armed asterisk
# Allowed range of the actogram period T, in minutes (1 min ... 240 h).
PERIOD_MIN_MIN, PERIOD_MAX_MIN = 1, 240 * 60     # period T: 0:01 - 240:00
# Display options are remembered between sessions in this file in the user's home folder.
SETTINGS_FILE = Path.home() / ".actogram_plotter.json"
# Colour scheme of the boxes in the settings column.  Each kind is (text colour, colour of the
# left bar, background tint, small tag text above the box).
# Green: values that must match the lab notebook / experiment records.
# Blue: view settings that only change how the actogram looks.
# (text colour, bar colour, tint, tag)
FRAME_KINDS = {"rec": ("#2e6b3f", "#8cc79a", "#eef7ef", "FROM YOUR RECORDS \u00b7 enter exactly"),
               "disp": ("#2f64a8", "#9dbde6", "#eef4fb", "VIEW SETTINGS \u00b7 change freely")}
# Format of every date/time field; DEFAULT_TIME_ZONE / DEFAULT_PERIOD are the start values.
DATETIME_HINT = "YYYY-MM-DD hh:mm"
DEFAULT_TIME_ZONE = "America/Chicago"           # US Central Time (CST / CDT)
DEFAULT_PERIOD = "24:00"                        # actogram period T
# Time-zone list shown in the combobox: (IANA key, readable description).
# Time-zone list: from the zone furthest ahead of UTC (east) westwards, the Americas
# included; UTC last.  Offsets: standard time / daylight time.
TIME_ZONES = (
    ("Pacific/Auckland", "Auckland (UTC+12:00 / +13:00)"),
    ("Australia/Sydney", "Sydney, Melbourne (UTC+10:00 / +11:00)"),
    ("Australia/Brisbane", "Brisbane (UTC+10:00)"),
    ("Asia/Tokyo", "Tokyo (UTC+09:00)"),
    ("Asia/Seoul", "Seoul (UTC+09:00)"),
    ("Asia/Shanghai", "Beijing, Shanghai (UTC+08:00)"),
    ("Asia/Hong_Kong", "Hong Kong (UTC+08:00)"),
    ("Asia/Taipei", "Taipei (UTC+08:00)"),
    ("Asia/Singapore", "Singapore (UTC+08:00)"),
    ("Australia/Perth", "Perth (UTC+08:00)"),
    ("Asia/Bangkok", "Bangkok, Hanoi, Jakarta (UTC+07:00)"),
    ("Asia/Kolkata", "India \u2013 Delhi, Mumbai (UTC+05:30)"),
    ("Asia/Dubai", "Dubai (UTC+04:00)"),
    ("Europe/Moscow", "Moscow (UTC+03:00)"),
    ("Europe/Istanbul", "Istanbul (UTC+03:00)"),
    ("Africa/Nairobi", "Nairobi (UTC+03:00)"),
    ("Europe/Athens", "Athens, Helsinki (UTC+02:00 / +03:00)"),
    ("Africa/Cairo", "Cairo (UTC+02:00 / +03:00)"),
    ("Africa/Johannesburg", "Johannesburg (UTC+02:00)"),
    ("Europe/Berlin", "Berlin, Amsterdam, Stockholm (UTC+01:00 / +02:00)"),
    ("Europe/Paris", "Paris, Madrid, Rome (UTC+01:00 / +02:00)"),
    ("Africa/Lagos", "Lagos (UTC+01:00)"),
    ("Europe/London", "London, Dublin, Lisbon (UTC\u00b100:00 / +01:00)"),
    ("America/Sao_Paulo", "São Paulo (UTC\u221203:00)"),
    ("America/Halifax", "Atlantic Time \u2013 Halifax (UTC\u221204:00 / \u221203:00)"),
    ("America/New_York", "Eastern Time \u2013 New York (UTC\u221205:00 / \u221204:00)"),
    ("America/Chicago", "Central Time \u2013 Chicago (UTC\u221206:00 / \u221205:00)"),
    ("America/Mexico_City", "Mexico City (UTC\u221206:00)"),
    ("America/Denver", "Mountain Time \u2013 Denver (UTC\u221207:00 / \u221206:00)"),
    ("America/Phoenix", "Mountain Time, no DST \u2013 Arizona (UTC\u221207:00)"),
    ("America/Los_Angeles", "Pacific Time \u2013 Los Angeles (UTC\u221208:00 / \u221207:00)"),
    ("America/Anchorage", "Alaska Time \u2013 Anchorage (UTC\u221209:00 / \u221208:00)"),
    ("Pacific/Honolulu", "Hawaii Time \u2013 Honolulu (UTC\u221210:00)"),
    ("UTC", "Coordinated Universal Time (UTC\u00b100:00)"),
)
# The combobox shows 'Key   -   description'; TIME_ZONE_CHOICES is that list in order.
TIME_ZONE_LABELS = {key: f"{key}   \u2013   {text}" for key, text in TIME_ZONES}
TIME_ZONE_CHOICES = tuple(TIME_ZONE_LABELS.values())
# Common alternative spellings that users type, mapped to the IANA key.
TIME_ZONE_ALIASES = {"asia/beijing": "Asia/Shanghai", "beijing": "Asia/Shanghai",
                     "asia/calcutta": "Asia/Kolkata", "us/central": "America/Chicago",
                     "us/eastern": "America/New_York", "us/mountain": "America/Denver",
                     "us/pacific": "America/Los_Angeles"}


# --------------------------------------------------------------------------- #
# Input normalisation: numbers typed with non-ASCII input methods
# --------------------------------------------------------------------------- #
# Japanese, Chinese and Korean input methods easily produce full-width characters
# ('１２．５', 'ー', '　'); Arabic, Persian, Hindi, Thai, ... keyboards produce their own
# digits ('١٢٫٥', '१२.५', '๑๒.๕'); word processors and web pages add typographic minus signs,
# dashes, no-break spaces and invisible characters.  ascii_numbers() turns all of these into the
# plain ASCII characters the parsers expect, so a pasted column or a typed value is read
# correctly instead of being reported as 'Not a number'.
# Characters that are removed (zero-width space/joiners, word joiner, byte-order mark, soft hyphen):
_ZERO_WIDTH = re.compile("[\u200b-\u200d\u2060\ufeff\u00ad]")
# Characters that mean a minus sign: hyphen, non-breaking hyphen, figure dash, en dash, em dash,
# horizontal bar, minus sign, heavy minus, small em dash, small and full-width hyphen-minus:
_DASHES = re.compile("[\u2010-\u2015\u2212\u2796\ufe58\ufe63\uff0d]")
# Separators of other scripts: ideographic comma (、), Arabic comma, Arabic thousands separator,
# small commas -> ','; ideographic full stop (。), Arabic decimal separator, small full stop -> '.';
# Arabic semicolon, small semicolon -> ';'.
_TO_COMMA = re.compile("[\u3001\u060c\u066c\ufe50\ufe51]")
_TO_POINT = re.compile("[\u3002\u066b\ufe52]")
_TO_SEMICOLON = re.compile("[\u061b\ufe54]")


def ascii_numbers(text) -> str:
    """Normalise text that holds numbers, dates and separators to ASCII.

    Steps: (1) Unicode NFKC normalisation: full-width digits, letters and signs
    (U+FF01-FF5E, used by Japanese, Chinese and Korean input), the ideographic space and other
    compatibility characters become their ordinary forms; (2) invisible characters are removed;
    (3) Unicode line separators become newlines and every other kind of space becomes ' '
    (tabs and newlines are kept, they separate columns and rows); (4) dashes and minus signs
    become '-'; (5) commas, decimal points and semicolons of other scripts become ',', '.', ';';
    (6) decimal digits of any script (Unicode category Nd) become '0'-'9'.
    """
    s = unicodedata.normalize("NFKC", str(text or ""))       # (1)
    s = _ZERO_WIDTH.sub("", s)                                 # (2)
    s = re.sub("[\u2028\u2029\u0085]", "\n", s)                # (3) line separators
    s = re.sub(r"[^\S\n\r\t]", " ", s)                         #     other white space
    s = _DASHES.sub("-", s)                                    # (4)
    s = _TO_COMMA.sub(",", s)                                  # (5)
    s = _TO_POINT.sub(".", s)
    s = _TO_SEMICOLON.sub(";", s)
    if not s.isascii():                                        # (6) only when needed (fast path)
        s = "".join(str(unicodedata.decimal(c)) if c.isdecimal() and not "0" <= c <= "9" else c
                    for c in s)
    return s


# Extract the IANA zone name from whatever the user selected or typed.
# A list entry starts with the key ('America/Chicago   -   Central Time ...'), so the first word is
# taken; a fixed offset like 'UTC + 9' keeps all of its characters (spaces removed).  Empty input
# means the default zone; known aliases are translated.
def time_zone_key(text: str) -> str:
    """'America/Chicago   \u2013   Central Time \u2026' (a list entry) or a typed name -> the zone name."""
    # ascii_numbers: 'ＵＴＣ＋９' or 'UTC−5' typed with other input methods work too
    t = ascii_numbers(text).strip()
    if not t:
        return DEFAULT_TIME_ZONE
    # first word, unless the text is an offset such as 'UTC+09:00' / 'GMT - 5'
    key = t.split()[0] if not re.match(r"(?i)(utc|gmt)\s*[+-]", t) else t.replace(" ", "")
    # case-insensitive alias lookup; otherwise the key as typed
    return TIME_ZONE_ALIASES.get(key.lower(), key)


# Opposite direction: the text to show in the combobox for a stored zone name.
def time_zone_display(text: str) -> str:
    """The list entry for a zone name (unchanged if it is not in the list)."""
    key = time_zone_key(text)
    return TIME_ZONE_LABELS.get(key, str(text).strip() or TIME_ZONE_LABELS[DEFAULT_TIME_ZONE])


# --------------------------------------------------------------------------- #
# Time zones and clock time
# --------------------------------------------------------------------------- #

# Every date/time is entered as the LOCAL clock time of the zone (standard or daylight
# time alike) and converted to UTC, so spans that cross a daylight-saving change get
# their true length.
# US zones, used if the system has no time-zone database (Windows without the 'tzdata'
# package): standard offset (h), names; DST from the 2nd Sunday of March 2:00 to the
# 1st Sunday of November 2:00 (rules in force since 2007).
# Standard-time offset (hours) and the abbreviations in standard / daylight time.
_US_ZONES = {"America/Chicago": (-6, "CST", "CDT"), "America/New_York": (-5, "EST", "EDT"),
             "America/Denver": (-7, "MST", "MDT"), "America/Los_Angeles": (-8, "PST", "PDT")}


# A minimal tzinfo implementation for four US zones, used only when the IANA database is
# missing.  tzinfo is Python's interface for time zones: datetime asks it for utcoffset(),
# dst() and tzname(), and calls fromutc() to convert UTC to local time.  'fold' (PEP 495)
# distinguishes the two occurrences of the repeated hour in November (fold=0: first, still
# daylight time; fold=1: second, standard time).
class _USRuleZone(tzinfo):
    """Fallback for a US time zone (post-2007 DST rules), PEP 495 'fold' aware."""

    def __init__(self, key: str) -> None:
        """Set up the zone from its key in _US_ZONES: standard offset and the two abbreviations."""
        self.key = key
        # unpack (offset hours, standard abbreviation, daylight abbreviation)
        hours, self._std_name, self._dst_name = _US_ZONES[key]
        self._std = timedelta(hours=hours)

    @staticmethod
    def _sunday(year: int, month: int, nth: int) -> datetime:
        """Date of the nth Sunday of a month (US rules: DST starts on the 2nd Sunday of March, ends on the 1st Sunday of November)."""
        # the 1st of the month; weekday(): Monday = 0 ... Sunday = 6
        first = datetime(year, month, 1)
        # days to the first Sunday, then whole weeks to the nth one
        return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (nth - 1))

    def _is_dst(self, dt: datetime) -> bool:
        """True if the local (wall-clock) time dt falls in daylight time under the post-2007 US rules."""
        # compare naive wall-clock times (the zone itself is not needed for that)
        local = dt.replace(tzinfo=None)
        start = self._sunday(dt.year, 3, 2) + timedelta(hours=2)    # 2:00 -> 3:00
        end = self._sunday(dt.year, 11, 1) + timedelta(hours=1)     # 1:00-2:00 happens twice
        # between the switch in March and the start of the repeated hour: daylight time
        if start <= local < end:
            return True
        # inside the repeated hour: the first pass (fold=0) is still daylight time
        if end <= local < end + timedelta(hours=1):                 # the repeated hour
            return dt.fold == 0
        return False

    def utcoffset(self, dt):
        """tzinfo API: offset from UTC for a local time (standard offset + 1 h in daylight time)."""
        return self._std + (timedelta(hours=1) if self._is_dst(dt) else timedelta(0))

    def dst(self, dt):
        """tzinfo API: the daylight-saving part of the offset (1 h or 0)."""
        return timedelta(hours=1) if self._is_dst(dt) else timedelta(0)

    def tzname(self, dt):
        """tzinfo API: abbreviation such as CST or CDT."""
        return self._dst_name if self._is_dst(dt) else self._std_name

    def fromutc(self, dt):
        """tzinfo API: convert a UTC time to local time, choosing the correct offset; fold=1 marks the second (standard-time) pass through the repeated hour in November."""
        # work on naive UTC values
        utc = dt.replace(tzinfo=None)
        # the two switch moments expressed in UTC (local switch time minus the standard offset)
        start_utc = self._sunday(utc.year, 3, 2) + timedelta(hours=2) - self._std
        end_utc = self._sunday(utc.year, 11, 1) + timedelta(hours=1) - self._std
        # in summer: local = UTC + standard offset + 1 h
        if start_utc <= utc < end_utc:                       # daylight time
            return (utc + self._std + timedelta(hours=1)).replace(tzinfo=self, fold=0)
        # otherwise standard time
        local = (utc + self._std).replace(tzinfo=self)
        # UTC times that map onto the second 01:00-01:59 get fold=1
        if end_utc <= utc < end_utc + timedelta(hours=1):    # second pass of 1:00-2:00
            return local.replace(fold=1)
        return local

    def __repr__(self) -> str:
        """Readable name used in messages and the settings file."""
        return f"{self.key} (built-in US rules)"


# Turn a zone name into a tzinfo object (the thing datetime uses to convert times).
# Order of attempts: UTC; a fixed offset 'UTC+09:00'; the IANA database (zoneinfo); the
# built-in US rules; otherwise a ValueError with a helpful message.
def get_time_zone(name: str):
    """'America/Chicago' (default), 'UTC' or a fixed offset such as 'UTC+09:00' -> tzinfo."""
    text = time_zone_key(name)
    # plain UTC
    if text.upper() in ("UTC", "GMT", "Z"):
        return timezone.utc
    # a fixed offset written as +9, -05:30, UTC+09:00, GMT-5 ...
    match = re.fullmatch(r"(?:UTC|GMT)?\s*([+-])(\d{1,2})(?::?(\d{2}))?", text, re.IGNORECASE)
    if match:
        # +1 or -1 from the sign character
        sign = 1 if match.group(1) == "+" else -1
        # hours, and minutes (absent = 0)
        hours, minutes = int(match.group(2)), int(match.group(3) or 0)
        # real-world offsets lie between UTC-12 and UTC+14
        if hours > 14 or minutes > 59:
            raise ValueError(f"Time zone: '{text}' is not a valid UTC offset.")
        # a fixed-offset tzinfo; its name is normalised to 'UTC+hh:mm'
        return timezone(sign * timedelta(hours=hours, minutes=minutes),
                        f"UTC{match.group(1)}{hours:02d}:{minutes:02d}")
    # IANA database (raises if the name is unknown or the database is missing)
    try:
        if ZoneInfo is None:
            raise ValueError
        return ZoneInfo(text)
    except Exception:
        # fallback when zoneinfo cannot load the zone
        if text in _US_ZONES:          # no time-zone database: built-in US rules
            return _USRuleZone(text)
        # on Windows the usual cause is the missing tzdata package: say how to fix it
        hint = "  On Windows, install the time zone data: pip install tzdata" \
            if sys.platform.startswith("win") else ""
        raise ValueError(f"Time zone: '{text}' is not a known time zone "
                         f"(e.g. Asia/Tokyo, America/Chicago, UTC, UTC+09:00).{hint}") from None


def zone_name(tz) -> str:
    """Name of a time-zone object for display (its IANA key if it has one)."""
    return getattr(tz, "key", None) or str(tz)


# Parse a typed or stored date/time into a naive datetime (no zone attached yet).
# Accepted: '2026-10-05 10:15', '2026/10/05 10:15', '2026-10-05T10:15:30'.  Single-digit month,
# day or hour are allowed.  `what` names the field in the error message.
def parse_local(text: str, what: str) -> datetime:
    """'YYYY-MM-DD hh:mm[:ss]' ('/' or 'T' separators accepted) -> naive datetime."""
    # unify the separators so one regular expression covers all forms
    clean = str(text).strip().replace("T", " ").replace("/", "-")
    # groups: year, month, day, hour, minute, optional second
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", clean)
    if not match:
        raise ValueError(f"{what}: '{text}' is not a date/time of the form {DATETIME_HINT}.")
    try:
        # datetime() itself rejects impossible values such as 2026-02-30 or hour 25
        return datetime(*(int(v) for v in match.groups(default="0")))
    except ValueError:
        raise ValueError(f"{what}: '{text}' is not a valid date/time.") from None


# Convert a naive local time to UTC, handling daylight-saving transitions explicitly.
# For each 'fold' (0 = first, 1 = second occurrence of a repeated local time) the local time is
# converted to UTC and back; only conversions that round-trip to the same wall-clock time are
# real.  0 results = a skipped time (spring forward), 2 results = a repeated time (fall back).
def local_dt_to_utc(local: datetime, tz, what: str = "Date/time") -> datetime:
    """Naive local wall-clock time -> aware UTC.  A repeated hour (clocks going back)
    is taken as its first occurrence (daylight time); a skipped one is an error."""
    # fixed offsets have no transitions
    if isinstance(tz, timezone):
        return local.replace(tzinfo=tz).astimezone(timezone.utc)
    found = []
    # try both possible occurrences
    for fold in (0, 1):
        utc = local.replace(tzinfo=tz, fold=fold).astimezone(timezone.utc)
        # keep only the ones that really show this wall-clock time
        if utc.astimezone(tz).replace(tzinfo=None) == local:
            found.append(utc)
    if not found:
        raise ValueError(f"{what}: {local:%Y-%m-%d %H:%M} does not exist in {zone_name(tz)} "
                         f"(the clocks jump forward then).")
    # of two candidates the earlier one is the first pass (daylight time)
    return min(found)


# Like local_dt_to_utc, but from text, with an optional zone abbreviation at the end that
# selects one of the two candidates of a repeated hour ('01:30 CST' = the second 01:30).
def local_to_utc(text: str, tz, what: str = "Date/time") -> datetime:
    """Local clock time 'YYYY-MM-DD hh:mm', optionally followed by the zone abbreviation
    ('2026-11-01 01:30 CST'), which picks the first or second pass of a repeated hour."""
    text = str(text).strip()
    abbreviation = ""
    # split off a trailing abbreviation such as 'CDT' / 'CST' / 'JST'
    match = re.fullmatch(r"(.*\d)\s*([A-Za-z]{2,5})", text)
    if match:
        text, abbreviation = match.group(1), match.group(2).upper()
    local = parse_local(text, what)
    if isinstance(tz, timezone):
        return local.replace(tzinfo=tz).astimezone(timezone.utc)
    found = []
    # same round-trip test as in local_dt_to_utc, remembering each candidate's abbreviation
    for fold in (0, 1):
        aware = local.replace(tzinfo=tz, fold=fold)
        utc = aware.astimezone(timezone.utc)
        if utc.astimezone(tz).replace(tzinfo=None) == local:
            found.append((utc, (aware.tzname() or "").upper()))
    if not found:
        raise ValueError(f"{what}: {local:%Y-%m-%d %H:%M} does not exist in {zone_name(tz)} "
                         f"(the clocks jump forward then).")
    # an abbreviation only matters if the time really is ambiguous
    if abbreviation and len({u for u, _ in found}) == 2:
        for utc, name in found:
            if name == abbreviation:
                return utc
    # default: the first occurrence
    return min(u for u, _ in found)


# True when the local time occurs twice (end of daylight time).  Used to decide whether the
# stored text needs a CDT/CST suffix and whether the picker must ask which occurrence is meant.
def is_ambiguous_local(text: str, tz) -> bool:
    """True if the local clock time occurs twice (clocks set back) in tz."""
    # ignore an abbreviation that may already be attached
    text = re.sub(r"\s*[A-Za-z]{2,5}$", "", str(text).strip())
    try:
        local = parse_local(text, "Date/time")
    except ValueError:
        return False
    # collect the distinct UTC offsets that produce this wall-clock time
    found = set()
    for fold in (0, 1):
        aware = local.replace(tzinfo=tz, fold=fold)
        if aware.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) == local:
            found.add(aware.utcoffset())
    # two different offsets -> the time occurs twice
    return len(found) == 2


def utc_offset_label(offset: timedelta) -> str:
    """Format an offset as 'UTC+09:00' / 'UTC−06:00' (true minus sign)."""
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "\u2212"
    return f"UTC{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}"


# Does the clock of `tz` change on calendar day `day`?  Returns None, or a pair
# (direction, explanation) used to shade the day in the picker and to explain it.
# Method: compare the offsets at the start of this day and the next; if they differ, probe each
# hour at hh:30 to find the skipped (does not exist) or repeated (occurs twice) hour.
def clock_change_on(day, tz):
    """None, or ('forward' | 'back', note) if the clocks of tz change on that day."""
    # offset at 00:00 of this day and of the next day
    first = datetime(day.year, day.month, day.day).replace(tzinfo=tz).utcoffset()
    nxt = day + timedelta(days=1)
    last = datetime(nxt.year, nxt.month, nxt.day).replace(tzinfo=tz).utcoffset()
    # same offset -> no change on this day
    if first == last:
        return None
    for hour in range(24):
        text = f"{day:%Y-%m-%d} {hour:02d}:30"
        try:
            # a time that cannot be converted lies in the skipped hour
            local_to_utc(text, tz)
        except ValueError:
            before = datetime(day.year, day.month, day.day, hour).replace(tzinfo=tz, fold=0)
            after = datetime(day.year, day.month, day.day, hour).replace(tzinfo=tz, fold=1)
            return ("forward", f"clocks go forward at {hour:02d}:00 {before.tzname()} to "
                               f"{hour + 1:02d}:00 {after.tzname()} \u2013 {hour:02d}:00\u2013"
                               f"{hour:02d}:59 does not exist.")
        # a time that occurs twice lies in the repeated hour
        if is_ambiguous_local(text, tz):
            first_pass = datetime(day.year, day.month, day.day, hour).replace(tzinfo=tz, fold=0)
            second = first_pass.replace(fold=1)
            return ("back", f"clocks go back at {hour + 1:02d}:00 {first_pass.tzname()} to "
                            f"{hour:02d}:00 {second.tzname()} \u2013 {hour:02d}:00\u2013"
                            f"{hour:02d}:59 occurs twice.")
    # change found but not located (unusual zones): give a generic note
    return ("forward" if last > first else "back", "the clocks change on this day.")


# Calendar grid for the date picker: always 6 weeks so the dialog does not change size.
def month_weeks(year: int, month: int) -> list:
    """Day numbers of the month in 6 rows of 7 (Sunday first); 0 = outside the month."""
    # firstweekday=6 makes Sunday the first column
    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(year, month)
    while len(weeks) < 6:
        weeks.append([0] * 7)
    return weeks


# One-line check text shown in the picker: weekday, date, local time, abbreviation, offset and
# the same moment in UTC, so the user can verify the conversion.
def describe_local_time(text: str, tz) -> str:
    """'Sunday, 18 October 2026, 11:41 CDT (UTC-05:00) = 2026-10-18 16:41 UTC'."""
    moment = local_to_utc(text, tz)
    local = moment.astimezone(tz)
    return (f"{local:%A}, {local.day} {local:%B %Y}, {local:%H:%M} {local.tzname()} "
            f"({utc_offset_label(local.utcoffset())}) = {moment:%Y-%m-%d %H:%M} UTC")


def format_local(utc: datetime, tz) -> str:
    """Show a UTC moment as local wall-clock time with the zone abbreviation, e.g. '2026-10-05 10:15 CDT'."""
    local = utc.astimezone(tz)
    return f"{local:%Y-%m-%d %H:%M} {local.tzname()}"


# Inverse of local_to_utc: produce text that local_to_utc() maps back to exactly the same
# moment.  The abbreviation is only added when the local time is ambiguous.
def wall_string(utc: datetime, tz) -> str:
    """Aware datetime -> 'YYYY-MM-DD hh:mm' (plus the zone abbreviation for a repeated hour)."""
    local = utc.astimezone(tz)
    text = f"{local:%Y-%m-%d %H:%M}"
    return f"{text} {local.tzname()}" if is_ambiguous_local(text, tz) else text


# Midnight in local time.  Used for the 'day 0 = 00:00 ...' choices of the actogram origin.
def local_midnight(utc: datetime, tz, add_days: int = 0) -> datetime:
    """UTC moment of local midnight (00:00) on the day of `utc` plus `add_days`; falls back to 01:00 on the rare days where midnight does not exist (DST switches at midnight in some zones)."""
    day = utc.astimezone(tz).date() + timedelta(days=add_days)
    # a few zones switch at midnight; then 00:00 does not exist and 01:00 is the first time
    for hour in (0, 1):
        try:
            return local_dt_to_utc(datetime(day.year, day.month, day.day, hour), tz)
        except ValueError:
            continue
    # should never be reached; return something sensible instead of failing
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Small parsers
# --------------------------------------------------------------------------- #

# Durations are entered as 'hh:mm' (L, D, period T).  Plain numbers are read as hours.
# Returns NaN rather than raising, so callers can show a message.
def parse_duration(text: str) -> float:
    """'hh:mm' (hh may be 24 or more) or plain hours -> hours (nan if invalid)."""
    t = ascii_numbers(text).strip()       # also '１２：３０', '١٢:٣٠', ...
    # hours may have up to 3 digits (e.g. 240:00); minutes must be 00-59
    match = re.fullmatch(r"(\d{1,3}):([0-5]\d)", t)
    if match:
        return int(match.group(1)) + int(match.group(2)) / 60.0
    try:
        value = float(t)
        # negative durations make no sense
        return value if value >= 0 else math.nan
    except ValueError:
        return math.nan


# Inverse of parse_duration for display (24.5 -> '24:30').
def format_duration(hours: float) -> str:
    """Hours as 'h:mm' (e.g. 24.5 -> '24:30'), rounded to the minute."""
    # round to whole minutes first, so 23.9999 becomes '24:00', not '23:60'
    minutes = int(round(float(hours) * 60))
    return f"{minutes // 60:d}:{minutes % 60:02d}"


# Read the peak/trough lists.  Anything between separators is a token; tokens that are numbers
# become values, all others are returned in `bad` so the UI can show 'Not a number: ...'.
# Digits, signs, separators and spaces of other input methods (full-width Japanese/Chinese/
# Korean, Arabic-Indic, Devanagari, ..., typographic minus signs) are converted first.
def parse_list(text: str) -> tuple[list, list]:
    """Numbers separated by newlines, commas, tabs, spaces or ';' -> (values, bad tokens)."""
    values, bad = [], []
    # normalise non-ASCII digits, signs, separators and spaces (see ascii_numbers)
    text = ascii_numbers(text)
    # split on any run of whitespace, commas or semicolons
    for token in re.split(r"[\s,;]+", text):
        if not token:
            continue
        try:
            value = float(token)
            # inf / nan are not valid times
            if math.isfinite(value):
                values.append(value)
                continue
        except ValueError:
            pass
        bad.append(token)
    return values, bad


# Short numbers in labels and messages: 12.5 instead of 12.500, 24 instead of 24.000.
def g(value: float) -> str:
    """Compact number for labels: at most 3 decimals, trailing zeros removed (12.500 -> '12.5')."""
    return f"{value:.3f}".rstrip("0").rstrip(".")


# --------------------------------------------------------------------------- #
# Light/dark schedule (in hours after 0 h of the data)
# --------------------------------------------------------------------------- #

# @dataclass generates __init__/__repr__ from the annotated fields below.
@dataclass
class Segment:
    """One light/dark condition of the schedule, on the time axis of the data (hours after 0 h).

    mode is 'LD', 'LL' or 'DD'; light/dark are the lengths (h) of the light and dark parts of an LD
    cycle; starts_with_light says which part comes first at start_hour.
    """
    # 'LD', 'LL' or 'DD'
    mode: str
    # length of the light part (h); LL is stored as light=24, dark=0
    light: float
    # length of the dark part (h); DD is stored as light=0, dark=24
    dark: float
    # True: each cycle begins with light at start_hour
    starts_with_light: bool
    # start of the condition in hours after 0 h of the data
    start_hour: float
    # the same moment as an aware UTC datetime
    start_utc: datetime
    # start as local text, e.g. '2026-10-28 14:37 CDT' (for messages)
    label: str

    def intervals(self, begin: float, end: float) -> list:
        """Light and dark intervals of this condition between `begin` and `end` (h), as a list of
        (start, end, is_light) tuples.  LD cycles repeat with period light + dark from start_hour (also
        backwards, so a condition can be extended before its start); LL/DD give one interval.
        """
        # one LD cycle
        period = self.light + self.dark
        if period <= 0 or end <= begin:
            return []
        # the order of the two parts inside a cycle
        parts = ((self.light, True), (self.dark, False)) if self.starts_with_light \
            else ((self.dark, False), (self.light, True))
        # start of the cycle that contains `begin` (cycles extend in both directions from start_hour)
        t = self.start_hour + math.floor((begin - self.start_hour) / period) * period
        out = []
        # walk cycle by cycle and clip each part to [begin, end)
        while t < end:
            for length, is_light in parts:
                a, b = max(t, begin), min(t + length, end)
                # skip zero-length parts (LL has no dark part, DD no light part)
                if length > 0 and b > a:
                    out.append((a, b, is_light))
                # next part starts where this one ended
                t += length
        return out


@dataclass
class Schedule:
    """The whole light/dark schedule: the conditions in time order, whether the first one is also
    drawn before its start, and the hour/label of its first light-on (used for 'day 0 = lights-on').
    """
    segments: list
    extend_before: bool
    origin_hour: float
    origin_label: str

    # Merge the conditions: condition i covers [its start, start of condition i+1).
    def intervals(self, lo: float, hi: float) -> list:
        """All light/dark intervals between lo and hi: each condition lasts until the next one starts."""
        out = []
        for i, seg in enumerate(self.segments):
            # the first condition may optionally extend back to -infinity
            begin = -math.inf if (i == 0 and self.extend_before) else seg.start_hour
            # the last condition lasts forever
            end = self.segments[i + 1].start_hour if i + 1 < len(self.segments) else math.inf
            # intersect with the requested window [lo, hi]
            out += seg.intervals(max(lo, begin), min(hi, end))
        return out


# Used for the default actogram origin: the light-on of the first condition on its start date,
# so that the x axis counts hours after lights-on (zeitgeber time).
def light_onset_on_date(start: datetime, starts_with_light: bool, light: float,
                        dark: float, tz) -> datetime:
    """Lights-on on the local calendar date of `start` (the last one before it if the
    cycle has none that day); with no light at all, `start` itself."""
    period = light + dark
    # no light at all (DD): there is no light-on
    if light <= 0 or period <= 0:
        return start
    # a cycle that begins with dark has its light-on `dark` hours later; go back one light period
    # so `base` is a light-on that lies on or before `start`
    base = start if starts_with_light else start - timedelta(hours=light)
    midnight, next_midnight = local_midnight(start, tz), local_midnight(start, tz, 1)
    # number of whole periods from `base` to the first light-on at or after local midnight
    k = math.ceil((midnight - base).total_seconds() / 3600.0 / period - 1e-9)
    candidate = base + timedelta(hours=k * period)
    # this light-on lies on the same calendar day
    if candidate < next_midnight:
        return candidate
    # none that day: use the last light-on before the start
    return base if base <= start else start


@dataclass
class Origin:
    """Actogram 'day 0, 0 h': its position on the data's time axis (hours after 0 h) plus the texts
    used for the x-axis title, the y-axis title, the information line and an optional note.
    """
    # position of day 0, 0 h in hours after 0 h of the data
    hour: float = 0.0
    # short text for the x-axis title, e.g. '0 = lights-on, 14:37'
    x_text: str = ""
    # text for the y-axis title, e.g. '0 = LD start'
    y_text: str = ""
    # information line shown under the 'Actogram day 0' options
    info: str = "Day 0, 0 h = 0 h of the data"
    # explanation when the chosen reference is missing and 0 h of the data is used instead
    note: str = ""


@dataclass
class Result:
    """Everything `compute` derives from the settings: the time zone, 0 h of the data as a UTC moment,
    the parsed light/dark schedule (or its errors), the sample placement, the actogram origin and
    period, and the messages shown under the inputs.
    """
    # tzinfo of the data (None if the zone is invalid)
    tz: object = None
    # 0 h of the data as an aware UTC datetime (None until a valid clock time is entered)
    zero: datetime | None = None
    # message for the 'Clock time of the data' box
    clock_error: str = ""
    # the parsed light/dark schedule (None if hidden or invalid)
    ld: Schedule | None = None
    # messages for the light/dark condition cards
    ld_errors: list = field(default_factory=list)
    # blue information lines listing every condition and its start in hours
    ld_info: str = ""
    # actogram day 0, 0 h
    origin: Origin = field(default_factory=Origin)
    origin_error: str = ""
    # period T of one actogram row (hours)
    period: float = 24.0
    period_error: str = ""
    # sample placement as UTC, as hours after 0 h and as local text, or its error
    placed_utc: datetime | None = None
    placed_hour: float | None = None
    placed_label: str = ""
    placed_error: str = ""


def compute(st: dict) -> Result:
    """Turn the settings (strings from the UI or a settings file) into a Result.

    Steps: (1) time zone and the clock time of 0 h; (2) the sample placement in hours after 0 h;
    (3) every LD/LL/DD condition: lengths, start time -> hours after 0 h, order checks; (4) the
    actogram origin (day 0, 0 h) from the chosen reference; (5) the period T.  Problems are
    collected as messages instead of raising, so the UI can show them next to the inputs.
    """
    # start with an empty result; every step fills in its part or a message
    res = Result()
    # (1) time zone and the clock time of 0 h.  Everything else is measured in hours after this
    #     moment, so without it no date/time input (LD starts, placement, origin) can be placed.
    try:
        res.tz = get_time_zone(st["tz"])
    except ValueError as exc:
        res.clock_error = str(exc)
    if res.tz is not None:
        try:
            res.zero = local_to_utc(st["t0"], res.tz, "Clock time of 0 h")
        except ValueError as exc:
            res.clock_error = str(exc)
    # most later steps need a valid 0 h
    has_clock = res.zero is not None

    # (5, done early because nothing depends on the clock) period T of one actogram row, whole minutes
    period = parse_duration(st["period"])
    # T must be a whole number of minutes within the allowed range
    if math.isfinite(period) and PERIOD_MIN_MIN <= round(period * 60) <= PERIOD_MAX_MIN:
        # round to whole minutes
        res.period = round(period * 60) / 60
    else:
        res.period_error = "Period T must be between 0:01 and 240:00 (hh:mm)."

    def hours(utc: datetime) -> float:
        """Hours between 0 h of the data and a UTC moment (the time axis of everything in the app)."""
        return (utc - res.zero).total_seconds() / 3600.0

    # (3) the light/dark schedule: each condition card -> a Segment on the data's time axis.
    #     LL is stored as an all-light cycle and DD as an all-dark one, so drawing and the phase
    #     analysis can treat every condition the same way.
    # the schedule is only parsed when 'Show the light/dark conditions' is ticked
    if st["show_ld"]:
        if not has_clock:
            res.ld_errors.append("LD cycles: set a valid clock time of 0 h first.")
        else:
            # segments = valid conditions so far; previous = start of the previous one (for the order check)
            segments, previous = [], None
            # the first card plus the n_changes visible change cards
            for i, c in enumerate(st["cycles"][: 1 + st["n_changes"]]):
                what = f"Condition {i + 1}"
                # unknown modes from old/odd settings files are treated as LD
                mode = c["mode"] if c["mode"] in LD_MODES else "LD"
                if mode == "LL":
                    # LL: one long light period; the 'cycle length' 24 h is only used for counting cycles
                    light, dark, phase = 24.0, 0.0, "Light"
                elif mode == "DD":
                    light, dark, phase = 0.0, 24.0, "Dark"
                else:
                    # LD: L and D from 'hh:mm', and which part comes first
                    light, dark, phase = parse_duration(c["L"]), parse_duration(c["D"]), c["phase"]
                    # both lengths 0..99:59 and the cycle must not be empty
                    if not (0 <= light <= LD_MAX_HOURS and 0 <= dark <= LD_MAX_HOURS) \
                            or light + dark <= 0:
                        res.ld_errors.append(f"{what}: L and D must be between 00:00 and 99:59 "
                                             f"(hh:mm), and L + D longer than 00:00.")
                        # skip this card, keep checking the others
                        continue
                try:
                    # the start date/time of the condition, local clock time -> UTC
                    start = local_to_utc(c["start"], res.tz, f"{what} start")
                except ValueError as exc:
                    res.ld_errors.append(str(exc))
                    continue
                # conditions must be entered in time order
                if previous is not None and start <= previous:
                    res.ld_errors.append(f"{what}: its start must be later than the start of "
                                         f"the previous cycle.")
                    continue
                previous = start
                # store everything later steps need: lengths, order, start in hours, UTC and as text
                segments.append(Segment(mode, light, dark, phase == "Light", hours(start), start,
                                        format_local(start, res.tz)))
            # build the schedule only if every card is valid
            if not res.ld_errors and segments:
                # the first light-on of the first condition is the default actogram origin ("ZT0")
                f = segments[0]
                # first light-on on the start date (for 'day 0 = lights-on')
                onset = light_onset_on_date(f.start_utc, f.starts_with_light, f.light, f.dark, res.tz)
                res.ld = Schedule(segments, bool(st["extend_before"]), hours(onset),
                                  format_local(onset, res.tz))
                # the blue lines under the cards: one per condition with its start in hours of the data
                lines = []
                for i, s in enumerate(segments):
                    head = f"Condition {i + 1}"
                    if s.mode == "LD":
                        lines.append(f"{head}: L {format_duration(s.light)} / D "
                                     f"{format_duration(s.dark)} (T = {format_duration(s.light + s.dark)}), "
                                     f"{'light' if s.starts_with_light else 'dark'} period starts at "
                                     f"{s.label} = {g(s.start_hour)} h")
                    else:
                        lines.append(f"{head}: {s.mode} from {s.label} = {g(s.start_hour)} h")
                res.ld_info = "\n".join(lines)

    # when the samples were put into the light/dark conditions (optional)
    # only if a placement time was entered
    if str(st.get("placed", "") or "").strip():
        if not has_clock:
            res.placed_error = "Sample placement: set a valid clock time of 0 h first."
        else:
            try:
                # parse it like every other local time
                res.placed_utc = local_to_utc(st["placed"], res.tz, "Sample placed at")
                # the orange asterisk is drawn at this hour
                res.placed_hour = hours(res.placed_utc)
                res.placed_label = format_local(res.placed_utc, res.tz)
            except ValueError as exc:
                res.placed_error = str(exc)

    # (4) actogram day 0, 0 h: the moment at the left end of the top row.  Each option returns
    #     early when its reference exists; otherwise we fall through to 0 h of the data and say why.
    kind = st["origin"]
    # '00:00 (midnight) on the day of 0 h of the data'
    if kind == "zero_midnight" and has_clock:
        midnight = local_midnight(res.zero, res.tz)
        h = hours(midnight)
        res.origin = Origin(h, "0 = 00:00", "",
                            f"Day 0, 0 h = 00:00 on the day of 0 h of the data: "
                            f"{format_local(midnight, res.tz)} (= {g(h)} h of the data)")
        return res
    # '00:00 on the day the first LD/LL/DD started' (works even if later cards are invalid)
    if kind == "first_midnight" and has_clock:
        try:
            first_start = local_to_utc(st["cycles"][0]["start"], res.tz, "First cycle start")
        except (ValueError, KeyError, IndexError):
            first_start = None
        if first_start is not None:
            midnight = local_midnight(first_start, res.tz)
            h = hours(midnight)
            res.origin = Origin(h, "0 = 00:00", "",
                                f"Day 0, 0 h = 00:00 on the day the first LD/LL/DD started: "
                                f"{format_local(midnight, res.tz)} (= {g(h)} h of the data)")
            return res
    # '00:00 on the day the sample was placed'
    if kind == "placed_midnight" and res.placed_utc is not None:
        midnight = local_midnight(res.placed_utc, res.tz)
        h = hours(midnight)
        res.origin = Origin(h, "0 = 00:00", "",
                            f"Day 0, 0 h = 00:00 on the day the sample was placed: "
                            f"{format_local(midnight, res.tz)} (= {g(h)} h of the data)")
        return res
    # 'light-on of the first LD cycle on its start date' (the recommended default)
    if kind == "lights_on" and res.ld is not None:
        first = res.ld.segments[0]
        word = "lights-on" if first.mode == "LD" else f"start of {first.mode}"
        # x-axis text shows the clock time of that light-on (characters 11-16 of 'YYYY-MM-DD hh:mm')
        res.origin = Origin(res.ld.origin_hour, f"0 = {word}, {res.ld.origin_label[11:16]}",
                            "0 = LD start",
                            f"Day 0, 0 h = {word} of the first cycle: {res.ld.origin_label} "
                            f"(= {g(res.ld.origin_hour)} h of the data)")
        return res
    # 'Another date/time' typed or picked by the user (also set by the fine-tune panel)
    if kind == "custom":
        if not has_clock:
            res.origin_error = "Set a valid clock time of 0 h first."
        else:
            try:
                moment = local_to_utc(st["origin_time"], res.tz, "Actogram day 0, 0 h")
                h = hours(moment)
                res.origin = Origin(h, f"0 = {moment.astimezone(res.tz):%H:%M}", "",
                                    f"Day 0, 0 h = {format_local(moment, res.tz)} (= {g(h)} h of the data)")
                return res
            except ValueError as exc:
                res.origin_error = str(exc)
    # fallback for every option whose reference is missing: 0 h of the data
    if has_clock:
        res.origin = Origin(0.0, f"0 = {res.zero.astimezone(res.tz):%H:%M}", "",
                            f"Day 0, 0 h = {format_local(res.zero, res.tz)} (= 0 h of the data)")
    # explain why the fallback was used
    if kind == "first_midnight":
        res.origin.note = "The first LD/LL/DD cycle has no valid start date/time, so 0 h of the data is used."
    if kind == "placed_midnight":
        res.origin.note = "The sample placement time is not set (or not valid), so 0 h of the data is used."
    if kind == "lights_on":
        res.origin.note = ("The LD cycles are not valid yet, so 0 h of the data is used."
                           if st["show_ld"] else
                           "The LD cycles are not shown, so 0 h of the data is used.")
    return res


# --------------------------------------------------------------------------- #
# Time-series data (e.g. bioluminescence) -> peaks and troughs
# --------------------------------------------------------------------------- #
# The same steps as ttron2excel_data_analysis.py, implemented with numpy only (no
# scipy/pandas needed; the web version uses the identical algorithm):
#   1. rows sorted by time, duplicate times averaged; if the intervals are not equal
#      (more than +-5 % from the median), the data are resampled by linear interpolation
#      onto a regular grid (step = median interval); grid times inside a gap longer than
#      2.5 x the median interval stay empty.
#   2. trend: Sinc Filter (windowed-sinc FIR low-pass = scipy.signal.firwin, applied
#      forwards and backwards = scipy.signal.filtfilt) or a centred Moving Average;
#      detrended = raw - trend.
#   3. optionally a centred moving average (3-15 points; 1 = none) of the raw (default) or
#      detrended data.
#   4. peaks / troughs = local maxima / minima of that curve at least the minimum
#      spacing apart (scipy.signal.find_peaks with 'distance').
#   5. hand edits (removed / added peaks and troughs) are applied on top.

# ---- settings of the time-series analysis ---------------------------------------------
# TS_METHODS: the two detrending methods.  TS_SMOOTH_CHOICES: widths (points) of the centred
# moving average of the detection line.  TS_MIN_POINTS: fewer rows cannot be analysed.
TS_METHODS = ("Sinc Filter", "Moving Average")
TS_SMOOTH_CHOICES = (1, 3, 5, 7, 9, 11, 13, 15)   # centred moving average (points; 1 = none)
TS_MIN_POINTS = 10
TS_TOLERANCE = 0.05           # intervals within +-5 % of the median count as equal
TS_GAP_FACTOR = 2.5           # gap limit = 2.5 x the median interval
TS_MAX_HOURS = 240.0          # upper limit of the window / cutoff period / spacing
# default detection settings (strings, like everything that comes from an entry field)
TS_DEFAULTS = {"ts_source": "raw", "ts_smooth": "7", "ts_method": "Sinc Filter", "ts_ma_window": "24",
               "ts_sinc_cutoff": "48", "ts_sinc_order": "101", "ts_min_sep": "12"}
# signal tokens that mean 'value missing' (kept as a gap instead of skipping the row)
_MISSING = re.compile(r"^(nan|na|n/a|-+)$", re.IGNORECASE)
# full-width digits/signs from Japanese input -> ASCII


# The edits are stored as *times* (hours), not as row indices, so they survive a change of the
# data or of the detection settings: a removed time is matched to the nearest detected point
# within half a sampling interval; an added time snaps to the nearest sample.
def empty_edits() -> dict:
    """Hand edits of the detected peaks/troughs: times (h) added or removed by clicking in the plot."""
    return {"add_peaks": [], "add_troughs": [], "del_peaks": [], "del_troughs": []}


def clean_edits(value) -> dict:
    """Validate hand edits read from a settings file: keep only the four known lists of finite numbers."""
    # start from empty lists and copy only valid entries
    out = empty_edits()
    if isinstance(value, dict):
        for key in out:
            items = value.get(key, [])
            if isinstance(items, list):
                for v in items:
                    # ignore entries that are not numbers
                    with contextlib.suppress(TypeError, ValueError):
                        if math.isfinite(float(v)):
                            # round to 0.0001 h (0.36 s) so the stored file stays tidy
                            out[key].append(round(float(v), 4))
    return out


def _number(token: str) -> float:
    """float(token), or NaN when the token is not a number."""
    try:
        return float(token)
    except ValueError:
        return math.nan


# Regular expression for an ISO 8601 date/time at the start of a row.  Groups: 1 year, 2 month,
# 3 day, 4 hour, 5 minute, 6 second (optional), 7 fraction of a second (optional), 8 UTC offset
# (optional: Z, +hh, +hhmm, +hh:mm).  '-?' and ':?' make the separators optional, '[T ]' allows a
# space instead of 'T'; the look-ahead requires a separator (or the end) after the time.
# date and time (ISO 8601) at the start of a row: 2026-10-05T10:15:00-0500, 20261005T1015,
# 2026-10-05 10:15, ...-05:00, ...Z; seconds and the '-' / ':' separators are optional
_DATETIME = re.compile(r"(\d{4})-?(\d{2})-?(\d{2})[T ](\d{2}):?(\d{2})(?::?(\d{2})(?:[.,](\d+))?)?"
                       r"\s*(Z|[+-]\d{2}(?::?\d{2})?)?(?=[\s,;]|$)", re.IGNORECASE)


# Convert the offset text of group 8 into minutes east of UTC (negative = west).
def _offset_minutes(text: str):
    """UTC offset of an ISO 8601 time ('Z', '+09', '+0900', '-05:00') in minutes; None if absent."""
    if text is None:
        return None
    if text.upper() == "Z":
        return 0
    # '+' = ahead of UTC (east), '-' = behind (west)
    sign = 1 if text[0] == "+" else -1
    # '+05:00' -> '0500'
    digits = text[1:].replace(":", "")
    # hours * 60 + minutes (minutes optional)
    return sign * (int(digits[:2]) * 60 + int(digits[2:4] or 0))


def parse_series(text: str):
    """Two columns separated by tabs, spaces, commas or ';': the time (hours after 0 h, or a
    date and time in ISO 8601 form) and the signal.

    Returns (times, values, number of lines skipped, date/time rows): times are hours, or
    for date/time rows (y, m, d, h, mi, s, microseconds, UTC offset in minutes or None).
    Lines whose first two fields cannot be read (headers, notes) are skipped; a missing
    value (NaN, NA, -) is kept as a gap.  If any row has a date/time, rows with plain
    numbers are skipped, and the other way round (the kind with more rows wins).
    """
    # two collections: rows whose time is in hours, and rows whose time is a date/time;
    # each is a pair (list of times, list of values)
    hours, dates, skipped = ([], []), ([], []), 0
    # normalise the whole text first: non-ASCII digits, signs, separators and spaces (ascii_numbers)
    for line in ascii_numbers(text).splitlines():
        # trim the line
        s = line.strip()
        # empty lines and comment lines (#) are ignored
        if not s or s.startswith("#"):
            continue
        # does the row start with a date/time?
        m = _DATETIME.match(s)
        if m:
            # the fields after the date/time; the first one is the signal
            rest = [x for x in re.split(r"[\s,;]+", s[m.end():]) if x]
            # the date/time parts as numbers; the fraction is padded/cut to microseconds
            when = (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)),
                    int(m.group(6) or 0), int(((m.group(7) or "") + "000000")[:6]), _offset_minutes(m.group(8)))
            target, token = dates, (rest[0] if rest else "")
        else:
            # plain row: split into fields
            tokens = [x for x in re.split(r"[\s,;]+", s) if x]
            # needs at least time and signal
            if len(tokens) < 2:
                skipped += 1
                continue
            # column 1 must be a number (hours)
            when = _number(tokens[0])
            # a header such as 'Time  Lum' fails here and is skipped
            if not math.isfinite(when):
                skipped += 1
                continue
            target, token = hours, tokens[1]
        # column 2: the signal
        y = _number(token) if token else math.nan
        if not math.isfinite(y):
            # not a number: either an explicit 'missing' marker (keep as NaN) or garbage (skip the row)
            if not (token and _MISSING.match(token)):
                skipped += 1
                continue
            y = math.nan
        target[0].append(when)
        target[1].append(y)
    # decide which kind of rows the data consist of; the other kind is counted as skipped
    if len(dates[0]) > len(hours[0]):
        return dates[0], np.array(dates[1], dtype=float), skipped + len(hours[0]), True
    return (np.array(hours[0], dtype=float), np.array(hours[1], dtype=float),
            skipped + len(dates[0]), False)


# Convert date/time rows into hours after 0 h of the data.
# `zero` = 0 h as UTC (from 'Clock time of the data'), or None -> the earliest time point is used.
# `tz` = the time zone of the data, used for rows without an explicit UTC offset.
# Returns (hours array, validity mask, number of invalid rows, the 0 h actually used).
def series_dates_to_hours(rows: list, zero, tz):
    """Date/time rows -> (hours after 0 h, valid mask, note).  Rows without a UTC offset are
    read as local clock time of the time zone of the data."""
    out, ok, bad = [], [], 0
    # each row: (year, month, day, hour, minute, second, microsecond, offset minutes or None)
    for (y, mo, d, h, mi, sec, us, off) in rows:
        try:
            # explicit offset: the time is exact, the time zone setting does not matter
            if off is not None:
                utc = datetime(y, mo, d, h, mi, sec, us, tzinfo=timezone(timedelta(minutes=off)))
            else:
                # no offset: local clock time of the data's zone (minute precision via local_to_utc), then add
                # the seconds and microseconds
                utc = local_to_utc(f"{y:04d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}", tz) \
                    + timedelta(seconds=sec, microseconds=us)
            # normalise to UTC
            utc = utc.astimezone(timezone.utc)
        # impossible dates (2026-02-30) or times in the skipped DST hour
        except (ValueError, OverflowError):
            bad += 1
            out.append(math.nan)
            ok.append(False)
            continue
        out.append(utc)
        ok.append(True)
    valid = [u for u in out if isinstance(u, datetime)]
    # 0 h not set: count from the first time point
    if zero is None and valid:
        zero = min(valid)
    # difference to 0 h in hours; NaN for invalid rows
    hrs = np.array([(u - zero).total_seconds() / 3600.0 if isinstance(u, datetime) else math.nan
                    for u in out], dtype=float)
    return hrs, np.array(ok, dtype=bool), bad, zero


# Bring the raw rows into a form the filters can use: strictly increasing, unique, and (if the
# sampling was irregular) on a regular time grid.  `info` collects what was done for the message
# under the data box.
def prepare_series(t: np.ndarray, y: np.ndarray):
    """(hours, values, info): sorted, duplicates averaged, resampled if irregular."""
    info = {"points_read": len(t), "notes": []}
    # count rows that go back in time (they are sorted below)
    if len(t) > 1 and np.any(np.diff(t) < 0):
        info["notes"].append(f"{int((np.diff(t) < 0).sum())} rows out of time order (sorted)")
    # stable sort keeps the original order of equal times
    order = np.argsort(t, kind="stable")
    t, y = t[order], y[order]
    # unique times and, for every row, the index of its unique time
    uniq, inverse = np.unique(t, return_inverse=True)
    if len(uniq) < len(t):
        # duplicate time points: average their measured values
        info["notes"].append(f"{len(t) - len(uniq)} duplicate time points (averaged)")
        ok = np.isfinite(y)
        sums, counts = np.zeros(len(uniq)), np.zeros(len(uniq))
        # np.add.at accumulates repeated indices correctly (plain fancy indexing would not)
        np.add.at(sums, inverse[ok], y[ok])
        np.add.at(counts, inverse[ok], 1)
        # mean of the measured values; NaN where all values at that time were missing
        y = np.where(counts > 0, sums / np.maximum(counts, 1), np.nan)
        t = uniq
    # the sampling intervals
    d = np.diff(t)
    median = float(np.median(d)) if len(d) else math.nan
    # relative deviation of each interval from the median
    deviation = np.abs(d - median) / median if median > 0 else np.zeros_like(d)
    # regular = every interval within +-5 % of the median
    regular = bool(len(d)) and not bool((deviation > TS_TOLERANCE).any())
    info.update(median=median, regular=regular, resampled=False, first=float(t[0]), last=float(t[-1]))
    # regular data are used as they are
    if regular or not median > 0:
        return t, y, info
    # irregular: resample with step = median interval
    interval, max_gap = median, TS_GAP_FACTOR * median
    # number of grid points from the first to the last time
    n = int(math.floor((t[-1] - t[0]) / interval + 1e-6)) + 1
    # the grid times (rounded to avoid 0.30000000004-style noise)
    grid = np.round(t[0] + interval * np.arange(n), 9)
    # interpolate only between measured values
    valid = np.isfinite(y)
    tv, yv = t[valid], y[valid]
    if len(tv) < 2:
        return t, y, info
    # linear interpolation onto the grid; outside the record -> NaN
    out = np.interp(grid, tv, yv, left=np.nan, right=np.nan)
    # for every grid time, the measured points to its left and right
    right = np.clip(np.searchsorted(tv, grid, side="left"), 1, len(tv) - 1)
    left = right - 1
    # grid times that coincide with a measured point keep its value
    exact = np.isclose(grid, tv[right], atol=1e-9) | np.isclose(grid, tv[left], atol=1e-9)
    # grid times inside a long gap (> 2.5 intervals) must not be invented
    in_gap = (tv[right] - tv[left]) > max_gap + 1e-9
    out[in_gap & ~exact] = np.nan
    info.update(resampled=True, max_gap=max_gap, grid_points=n)
    return grid, out, info


# Centred moving average computed with cumulative sums (fast, O(n)):
# sum over [i-half, i+half] = csum[i+half+1] - csum[i-half].  Missing values contribute neither
# to the sum nor to the count, so near gaps and at the ends the mean is over fewer points
# (like pandas rolling(..., center=True, min_periods=1)).
def ts_rolling_mean(y: np.ndarray, window: int) -> np.ndarray:
    """Centred moving average over `window` points (odd), averaging the measured points
    only (min_periods=1); missing values stay missing."""
    # half-width of the window
    n, half = len(y), (window - 1) // 2
    ok = np.isfinite(y)
    # running sum of the measured values (missing values count as 0)
    csum = np.concatenate([[0.0], np.cumsum(np.where(ok, y, 0.0))])
    # running count of measured values
    ccnt = np.concatenate([[0], np.cumsum(ok)])
    i = np.arange(n)
    # window limits for every index, clipped to the array
    lo, hi = np.clip(i - half, 0, n), np.clip(i + half + 1, 0, n)
    count = ccnt[hi] - ccnt[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        # mean = sum / count where there is at least one value
        out = np.where(count > 0, (csum[hi] - csum[lo]) / np.maximum(count, 1), np.nan)
    # a missing input stays missing in the output
    out[~ok] = np.nan
    return out


# Used for the moving-average trend: where the trend is undefined (gaps, both ends), copy the
# next valid value (backward fill), then the previous one (forward fill).
def _fill_both(y: np.ndarray) -> np.ndarray:
    """Missing values filled from the next measured value, then from the previous one."""
    out = y.copy()
    ok = np.isfinite(out)
    if not ok.any():
        return out
    # index of each measured value, a large number elsewhere
    idx = np.where(ok, np.arange(len(out)), len(out))
    # running minimum from the right = index of the next measured value
    nxt = np.minimum.accumulate(idx[::-1])[::-1]          # next measured index (bfill)
    fill = nxt < len(out)
    # fill gaps from the next value
    out[~ok & fill] = out[nxt[~ok & fill]]
    ok = np.isfinite(out)
    idx = np.where(ok, np.arange(len(out)), -1)
    # running maximum from the left = index of the previous measured value
    prv = np.maximum.accumulate(idx)                      # previous measured index (ffill)
    # fill what is left (the end of the series) from the previous value
    out[~ok & (prv >= 0)] = out[prv[~ok & (prv >= 0)]]
    return out


# Design a low-pass FIR filter: the ideal low-pass impulse response is a sinc function;
# truncating it to `numtaps` coefficients and multiplying by a Hamming window reduces ripple.
# `cutoff` is the cut-off frequency as a fraction of the Nyquist frequency (0..1).  The taps are
# normalised to sum to 1, so a constant signal passes unchanged (gain 1 at 0 Hz).
def firwin_lowpass(numtaps: int, cutoff: float) -> np.ndarray:
    """Windowed-sinc low-pass (Hamming window, unit gain at 0 Hz), like scipy.signal.firwin;
    cutoff relative to the Nyquist frequency."""
    # tap positions centred on 0
    m = np.arange(numtaps) - (numtaps - 1) / 2.0
    # ideal low-pass impulse response (np.sinc(x) = sin(pi x)/(pi x))
    h = cutoff * np.sinc(cutoff * m)
    if numtaps > 1:
        # Hamming window
        h *= 0.54 - 0.46 * np.cos(2 * np.pi * np.arange(numtaps) / (numtaps - 1))
    # unit gain at zero frequency
    return h / h.sum()


# Apply the FIR filter with a 'steady-state' start: pretend that all samples before x[0] were
# equal to x[0].  This is what scipy's lfilter does with zi = lfilter_zi(b, 1) * x[0].
def _fir_with_history(b: np.ndarray, x: np.ndarray) -> np.ndarray:
    """FIR filter whose earlier inputs all equal x[0] (= lfilter with lfilter_zi * x[0])."""
    # prepend len(b)-1 copies of the first value
    padded = np.concatenate([np.full(len(b) - 1, x[0]), x])
    # 'valid' convolution returns exactly len(x) outputs
    return np.convolve(padded, b, mode="valid")


# Zero-phase filtering: filter forwards, then backwards, so the phase shifts cancel and the trend
# is not delayed in time.  To reduce edge effects, the signal is first extended at both ends by
# 3*len(b) points of its point-reflection ('odd extension': 2*x[0] - x[k]), as scipy does.
def filtfilt_fir(b: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Zero-phase filtering like scipy.signal.filtfilt(b, [1], x) (odd extension of
    3 x len(b) points at both ends)."""
    pad = 3 * len(b)
    # scipy raises the same error when the data are shorter than the padding
    if len(x) <= pad:
        raise ValueError(f"the data ({len(x)} points) are too short for a filter of {len(b)} taps")
    # odd extension: left mirror, the data, right mirror
    ext = np.concatenate([2 * x[0] - x[pad:0:-1], x, 2 * x[-1] - x[-2:-(pad + 2):-1]])
    # forward pass
    y = _fir_with_history(b, ext)
    # backward pass (reverse, filter, reverse back)
    y = _fir_with_history(b, y[::-1])[::-1]
    # drop the padding again
    return y[pad:-pad]


# Compute the trend.  Returns (trend array, legend text for the plot).
# `dt` = sampling interval (h); `window` (h) for the moving average; `cutoff` (h, the period
# below which changes are removed) and `order` (number of taps) for the sinc filter.
def ts_trend(y: np.ndarray, dt: float, method: str, window: float, cutoff: float, order: int):
    """(trend, legend text) by the chosen method."""
    if method == "Moving Average":
        # window in hours -> number of samples, made odd so the window is centred
        n_points = math.ceil(window / dt)
        if n_points % 2 == 0:
            n_points += 1
        # moving average, with the ends/gaps filled
        return _fill_both(ts_rolling_mean(y, n_points)), f"{n_points}-point moving average, centred"
    n = len(y)
    # the filter must be shorter than a third of the data (padding rule of filtfilt)
    max_order = int(n / 3) - 1
    if order >= max_order:
        order = max(1, max_order)
    # odd number of taps -> symmetric filter with a centre tap
    if order % 2 == 0:
        order += 1
    # cut-off frequency 1/cutoff (cycles per hour) relative to Nyquist 1/(2*dt): 2*dt/cutoff
    taps = firwin_lowpass(order, 2.0 * dt / cutoff)
    ok = np.isfinite(y)
    idx = np.arange(n, dtype=float)
    # bridge gaps by linear interpolation (filtfilt needs a gap-free signal)
    filled = np.interp(idx, idx[ok], y[ok])                 # filtfilt cannot handle gaps
    return filtfilt_fir(taps, filled), f"Sinc Filter C={cutoff:g}h O={order}"


# Find local maxima exactly like scipy's internal _local_maxima_1d: a point is a peak if its
# left neighbour is lower and, after any run of equal values (a flat top), the next value is
# lower too.  For a flat top the middle index is returned.  The first and last samples can
# never be peaks (they have only one neighbour).
def _local_maxima(x: np.ndarray) -> list:
    """Indices of local maxima (the middle of a flat top), as in scipy.signal.find_peaks."""
    # i walks over the inner samples 1 .. n-2
    peaks, i, i_max = [], 1, len(x) - 1
    while i < i_max:
        # rising edge found
        if x[i - 1] < x[i]:
            ahead = i + 1
            # skip over a plateau of equal values
            while ahead < i_max and x[ahead] == x[i]:
                ahead += 1
            # falling after the plateau -> a peak
            if x[ahead] < x[i]:
                # middle of the plateau (rounded down)
                peaks.append((i + ahead - 1) // 2)
                # continue after the plateau
                i = ahead
        i += 1
    return peaks


# Enforce a minimum spacing like scipy's find_peaks(distance=...): visit the peaks from the
# highest to the lowest; each peak still kept removes all neighbours closer than `distance`
# samples on both sides.  The result keeps the original (time) order.
def _by_distance(peaks: list, x: np.ndarray, distance: int) -> list:
    """Keep the highest peaks first, dropping neighbours closer than `distance` points."""
    n = len(peaks)
    keep = [True] * n
    # indices into `peaks`, highest value first
    for j in reversed(sorted(range(n), key=lambda k: x[peaks[k]])):
        if not keep[j]:
            # already removed by a higher neighbour
            continue
        k = j - 1
        # remove lower peaks too close on the left
        while k >= 0 and peaks[j] - peaks[k] < distance:
            keep[k] = False
            k -= 1
        k = j + 1
        # and on the right
        while k < n and peaks[k] - peaks[j] < distance:
            keep[k] = False
            k += 1
    return [p for p, ok in zip(peaks, keep) if ok]


# Peaks = local maxima, troughs = local maxima of the negated series.  The minimum spacing is
# given in hours and converted to samples with the sampling interval dt.  Gaps inside the record
# are bridged by linear interpolation for the search, but a peak may only lie on a measured point.
def find_peaks_and_troughs(series: np.ndarray, min_sep_hours: float, dt: float):
    """Indices of the peaks and of the troughs of `series` (gaps bridged linearly; only
    measured points can be peaks or troughs)."""
    ok = np.isfinite(series)
    if not ok.any():
        return [], []
    # first and last measured sample; leading/trailing gaps are ignored
    first = int(np.argmax(ok))
    last = len(series) - 1 - int(np.argmax(ok[::-1]))
    part, okp = series[first:last + 1], ok[first:last + 1]
    idx = np.arange(len(part), dtype=float)
    # bridge interior gaps linearly
    values = np.interp(idx, idx[okp], part[okp])
    # spacing in samples (scipy needs >= 1); 5 samples if no spacing/interval is known
    distance = max(1, int(min_sep_hours / dt)) if (min_sep_hours and dt) else 5
    # maxima, thinned to the minimum spacing
    peaks = _by_distance(_local_maxima(values), values, distance)
    # minima = maxima of -values
    troughs = _by_distance(_local_maxima(-values), -values, distance)
    # back to indices of the full series; drop extremes that fall on interpolated points
    return ([first + i for i in peaks if okp[i]], [first + i for i in troughs if okp[i]])


def _positive(text, what: str, errors: list):
    """Read a positive number from a settings field; on failure append a message to `errors`."""
    try:
        value = float(str(text).strip())
    except ValueError:
        value = math.nan
    if not (math.isfinite(value) and value > 0):
        errors.append(f"{what} must be a positive number.")
    return value


# The complete time-series analysis, from the settings dictionary to the detected peaks and
# troughs.  Never raises: problems are returned as out['error'] (blocking) or out['trend_error']
# (detrending not possible, but detection on raw data still works).
#
# Returned keys (when ok): t, y = the rows as read (hours); hours, raw = the cleaned/resampled
# series; dt = sampling interval; trend, trend_label; signal = data used for detection (raw or
# raw - trend); smooth = the detection line (moving average of signal); auto_peaks/auto_troughs
# = indices found automatically; peaks/troughs = after the hand edits; info = message text.
def analyze_series(st: dict) -> dict:
    """Everything the time-series plot and the actogram need, from the settings."""
    # default result: not ok, nothing detected
    out = {"ok": False, "error": "", "info": "", "peaks": [], "troughs": [],
           "auto_peaks": [], "auto_troughs": []}
    # 1. read the text of the data box
    t, y, skipped, is_dates = parse_series(st.get("series", ""))
    date_note = ""
    # date/time rows must be converted to hours after 0 h of the data
    if is_dates and len(t):
        try:
            # the zone of the data (UTC if the setting is invalid)
            tz = get_time_zone(st.get("tz", DEFAULT_TIME_ZONE))
        except ValueError:
            tz = timezone.utc
        try:
            # 0 h = the clock time entered under 'Clock time of the data'
            zero = local_to_utc(st.get("t0", ""), tz, "Clock time of 0 h")
            zero_set = True
        except ValueError:
            zero, zero_set = None, False
        # convert; keep only the rows that could be converted
        hrs, ok_rows, bad, zero = series_dates_to_hours(t, zero, tz)
        t, y = hrs[ok_rows], y[ok_rows]
        skipped += bad
        # the first line of the blue message explains which moment is 0 h
        if zero is not None:
            date_note = ("Column 1 = date and time: hours after 0 h = " + format_local(zero, tz)
                         + ("" if zero_set else " (the first time point, as the clock time of 0 h is not set)") + ".")
    # nothing readable
    if not len(t):
        out["error"] = ("No time-series data yet." + (f" ({skipped} line{'s' if skipped != 1 else ''} "
                                                       f"could not be read.)" if skipped else ""))
        return out
    # too few rows for filtering and peak detection
    if len(t) < TS_MIN_POINTS:
        out["error"] = f"Only {len(t)} data rows were read; at least {TS_MIN_POINTS} are needed."
        return out
    # 2. sort, average duplicates, resample if irregular
    hours, raw, info = prepare_series(t, y)
    n = len(hours)
    # the mean sampling interval of the (regular) series
    dt = (hours[-1] - hours[0]) / (n - 1) if n > 1 else math.nan
    if not (dt > 0):
        out["error"] = "The time points must not all be the same."
        return out
    # the blue information lines under the data box
    lines = [f"{info['points_read']} rows read, {g(info['first'])} to {g(info['last'])} h; "
             f"median interval {info['median']:.3f} h"]
    if info["resampled"]:
        lines.append(f"Intervals not equal: resampled onto a regular {info['median']:.3f} h grid "
                     f"({info['grid_points']} points; gaps longer than {info['max_gap']:.2f} h left empty).")
    if skipped:
        info["notes"].append(f"{skipped} line{'s' if skipped != 1 else ''} skipped (not two numbers)")
    if info["notes"]:
        lines.append("; ".join(info["notes"]) + ".")
    if date_note:
        lines.insert(0, date_note)
    out.update(t=t, y=y, hours=hours, raw=raw, dt=dt, info="\n".join(lines))

    # 3. detection settings; `errors` block the detection, `trend_errors` only the trend
    errors = []
    # detect in the raw data or in the detrended data
    source = "raw" if st.get("ts_source") == "raw" else "detrended"
    method = st.get("ts_method") if st.get("ts_method") in TS_METHODS else "Sinc Filter"
    # minimum spacing between two peaks (or two troughs), hours
    min_sep = _positive(st.get("ts_min_sep", 12), "The minimum peak spacing", errors)
    if math.isfinite(min_sep) and min_sep > TS_MAX_HOURS:
        errors.append(f"The minimum peak spacing must not exceed {TS_MAX_HOURS:g} h.")
    trend = label = None
    trend_errors = []                     # the trend is also wanted for drawing detrended data
    # the trend is always computed when possible: it is shown in the plot and needed for drawing
    # detrended data in the actogram, even if the peaks are detected in the raw data
    if True:
        # length of the record (h)
        duration = dt * (n - 1)
        if method == "Moving Average":
            # Moving Average trend: window (h) must cover at least 3 samples and fit into the record
            window = _positive(st.get("ts_ma_window", 24), "The moving-average window", trend_errors)
            if math.isfinite(window) and window > 0:
                if window < 3 * dt:
                    trend_errors.append(f"The moving-average window must be at least 3 sampling intervals "
                                  f"({3 * dt:.2f} h).")
                elif window > TS_MAX_HOURS:
                    trend_errors.append(f"The moving-average window must not exceed {TS_MAX_HOURS:g} h.")
                elif window > duration:
                    trend_errors.append(f"The moving-average window is longer than the recording ({duration:.1f} h).")
            # (sinc values unused in this branch)
            cutoff, order = 48.0, 101
        else:
            # (moving-average window unused in this branch)
            window = 24.0
            # Sinc Filter: cutoff period must be longer than 2 sampling intervals (Nyquist limit)
            cutoff = _positive(st.get("ts_sinc_cutoff", 48), "The cutoff period", trend_errors)
            if math.isfinite(cutoff) and cutoff > 0:
                if not cutoff > 2 * dt:
                    trend_errors.append(f"The cutoff period must be longer than 2 sampling intervals ({2 * dt:.2f} h).")
                elif cutoff > TS_MAX_HOURS:
                    trend_errors.append(f"The cutoff period must not exceed {TS_MAX_HOURS:g} h.")
            # filter order = number of taps (whole number)
            try:
                order = int(float(str(st.get("ts_sinc_order", 101)).strip()))
            except ValueError:
                order = 0
            if order < 3:
                trend_errors.append("The sinc filter order must be a whole number of at least 3.")
        if not np.isfinite(raw).any():
            trend_errors.append("The data have no measured values.")
        # 4. compute the trend
        if not trend_errors:
            try:
                trend, label = ts_trend(raw, dt, method, window, cutoff, order)
            except ValueError as exc:
                trend_errors.append(f"Detrending failed: {exc}. Use a lower filter order or longer data.")
    # trend problems only block the detection when the detrended data are needed
    if source == "detrended":
        errors += trend_errors
    elif trend_errors:
        trend = label = None
        out["trend_error"] = "\n".join(trend_errors)
    if errors:
        out["error"] = "\n".join(errors)
        return out
    # 5. the data used for detection
    signal = raw - trend if source == "detrended" else raw
    # width of the moving average of the detection line (1 = no smoothing)
    try:
        n_smooth = int(float(str(st.get("ts_smooth", 1)).strip()))
    except ValueError:
        n_smooth = 1
    n_smooth = n_smooth if n_smooth in TS_SMOOTH_CHOICES else 1
    # the detection line
    smooth = ts_rolling_mean(signal, n_smooth) if n_smooth > 1 else signal.copy()
    # 6. automatic peaks and troughs
    auto_p, auto_t = find_peaks_and_troughs(smooth, min_sep, dt)
    # 7. apply the hand edits from the settings
    peaks, troughs = apply_edits(hours, smooth, auto_p, auto_t, clean_edits(st.get("ts_edits")), dt)
    out.update(ok=True, source=source, smooth_n=n_smooth, trend=trend, trend_label=label, signal=signal, smooth=smooth,
               auto_peaks=auto_p, auto_troughs=auto_t, peaks=peaks, troughs=troughs)
    return out


# Combine automatic detection and hand edits (all as row indices of the series):
# - a removed time deletes the automatic point closest to it within half an interval;
# - an added time snaps to the nearest sample with a valid detection-line value and is added
#   unless that sample is already a peak or a trough.
def apply_edits(hours, smooth, auto_p, auto_t, edits: dict, dt: float):
    """Automatic peaks/troughs minus the removed ones plus the added ones (row indices)."""
    peaks, troughs = list(auto_p), list(auto_t)
    # matching tolerance: half a sampling interval
    tol = 0.5 * dt + 1e-6
    for key, items in (("del_peaks", peaks), ("del_troughs", troughs)):
        for h in edits[key]:
            # automatic points near the removed time
            hits = [i for i in items if abs(hours[i] - h) <= tol]
            if hits:
                # remove the closest one
                items.remove(min(hits, key=lambda i: abs(hours[i] - h)))
    # samples where a marker can be placed
    valid = np.flatnonzero(np.isfinite(smooth))
    if len(valid):
        for key, items, other in (("add_peaks", peaks, troughs), ("add_troughs", troughs, peaks)):
            for h in edits[key]:
                # nearest valid sample to the added time
                i = int(valid[np.argmin(np.abs(hours[valid] - h))])
                # a sample cannot be both a peak and a trough
                if i not in items and i not in other:
                    items.append(i)
    return sorted(peaks), sorted(troughs)


# Times are rounded to 0.001 h (3.6 s) for display and for the lists.
def series_hour(ts: dict, index: int) -> float:
    """Time (h, rounded to 0.001) of row `index` of the analysed (possibly resampled) series."""
    return round(float(ts["hours"][index]), 3)


def series_text(ts: dict, kind: str) -> str:
    """The detected peak or trough times as one value per line, for the Peaks/Troughs lists."""
    return "\n".join(g(series_hour(ts, i)) for i in ts["peaks" if kind == "peak" else "troughs"])


# Record that the user removed the peak/trough at row `index` (clicked in the plot).
# If that marker had been added by hand, the addition is simply forgotten; otherwise the time
# is stored in the 'del_' list.
def edit_remove(edits: dict, ts: dict, kind: str, index: int) -> dict:
    """Edits after removing the peak/trough at row `index`."""
    e = clean_edits(edits)
    # the two lists that concern this kind
    add, rem = (("add_peaks", "del_peaks") if kind == "peak" else ("add_troughs", "del_troughs"))
    # the time of the clicked marker and the matching tolerance
    h, tol = float(ts["hours"][index]), 0.5 * ts["dt"] + 1e-6
    near = [v for v in e[add] if abs(v - h) <= tol]
    if near:                                              # a hand-added one: just forget it
        e[add] = [v for v in e[add] if v not in near]
    else:
        # an automatic one: remember its time as removed
        e[rem].append(round(h, 4))
    return e


# Record that the user added a peak/trough at row `index`.  If an automatic point at that
# time had been removed before, the removal is undone (it comes back by itself); a new
# addition is only stored when the automatic detection did not already find it.
def edit_add(edits: dict, ts: dict, kind: str, index: int) -> dict:
    """Edits after adding a peak/trough at row `index` (already checked to be free)."""
    e = clean_edits(edits)
    add, rem = (("add_peaks", "del_peaks") if kind == "peak" else ("add_troughs", "del_troughs"))
    # the automatic points of this kind
    auto = ts["auto_peaks"] if kind == "peak" else ts["auto_troughs"]
    h, tol = float(ts["hours"][index]), 0.5 * ts["dt"] + 1e-6
    e[rem] = [v for v in e[rem] if abs(v - h) > tol]       # an automatic one comes back
    # only store additions that the automatic detection does not already contain
    if index not in auto:
        e[add].append(round(h, 4))
    return e


def edit_count(edits: dict) -> int:
    """Number of hand edits (added + removed peaks and troughs)."""
    return sum(len(v) for v in clean_edits(edits).values())


# Draw the light/dark schedule as a horizontal bar on a thin axes above a time-series panel.
# Returns False (and leaves the axes empty) when no schedule is shown.
def draw_ld_bar(ax, res, st: dict, lo: float, hi: float) -> bool:
    """The light/dark schedule as a bar (light / dark colour) on a thin axes."""
    from matplotlib.patches import Rectangle
    # the bar fills the axes vertically; no y ticks, no x labels, no frame
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    if not (st.get("show_ld") and res is not None and res.ld is not None):
        return False
    # same colours as the bands of the actogram
    light = pick_color(st.get("light_color"), LIGHT_COLORS)
    dark = pick_color(st.get("dark_color"), DARK_COLORS)
    # one rectangle per light or dark interval, with a thin grey outline
    for a, b, is_light in res.ld.intervals(lo, hi):
        ax.add_patch(Rectangle((a, 0.08), b - a, 0.84, facecolor=light if is_light else dark,
                               edgecolor="#555555", linewidth=0.6))
    return True


# ---- the time series drawn in the actogram (activity bars or heat map) ----
# Options for drawing the time series in the actogram: (stored value, text in the combobox).
TS_DRAW_MODES = (("none", "None"), ("activity", "Activity bars"), ("heatmap", "Heat map"))
TS_DRAW_SCALES = (("all", "Whole record"), ("row", "Each row"))
# defaults of these display options
TS_DRAW_DEFAULTS = {"ts_draw": "none", "ts_draw_data": "raw", "ts_draw_scale": "all", "show_points": True}
HEAT_HEIGHT = 0.62            # heat-map strip: lower part of the row band, the LD colour stays visible above
ACTIVITY_COLOR = "#90ee90"         # light green, drawn 50 % transparent
# one-entry cache for cached_series(): the key of the last analysis and its result
_TS_CACHE = {"key": None, "val": None}


def cached_series(st: dict) -> dict:
    """analyze_series with a one-entry cache: the actogram and the row range ask for the same
    analysis several times per redraw, and the analysis only changes when these settings change.
    """
    # the cache key is the JSON text of every setting the analysis depends on
    key = json.dumps([st.get(k) for k in ("series", "ts_source", "ts_method", "ts_ma_window", "ts_sinc_cutoff",
                                          "ts_sinc_order", "ts_min_sep", "ts_smooth", "ts_edits", "t0", "tz")],
                     sort_keys=True, default=str)
    if _TS_CACHE["key"] != key:
        _TS_CACHE.update(key=key, val=analyze_series(st))
    return _TS_CACHE["val"]


# Choose the data to draw in the actogram rows.  Returns (hours, values, name, dt) or None
# when the option is off, the input is not a time series, the analysis failed, or detrended
# data are wanted but no trend could be computed.
def series_for_actogram(st: dict):
    """(hours, values, name, dt, note) of the data to draw in the actogram, or None."""
    if st.get("input_mode") != "series" or st.get("ts_draw", "none") not in ("activity", "heatmap"):
        return None
    ts = cached_series(st)
    if not ts.get("ok"):
        return None
    if st.get("ts_draw_data") == "detrended":
        if ts.get("trend") is None:
            return None
        # detrended = raw - trend (the trend is computed even when the peaks are found in raw data)
        return ts["hours"], ts["raw"] - ts["trend"], "Detrended data", ts["dt"]
    return ts["hours"], ts["raw"], "Raw data", ts["dt"]


def _limits(v: np.ndarray, diverging: bool):
    """Colour/height range for drawing the series: 1st-99th percentile (robust against single outliers);
    for detrended data symmetric around 0 so that white/zero is the middle of the colour scale.
    """
    # ignore gaps
    v = v[np.isfinite(v)]
    if not len(v):
        return None
    if diverging:                           # symmetric around 0
        # 99th percentile of |values| (fall back to the maximum if that is 0)
        m = float(np.percentile(np.abs(v), 99)) or float(np.abs(v).max()) or 1.0
        return -m, m
    # robust range: 1st to 99th percentile
    lo, hi = float(np.percentile(v, 1)), float(np.percentile(v, 99))
    # avoid a zero-width range for a constant signal
    return (lo, hi) if hi > lo else (lo, lo + 1.0)


# Draw the time series in the actogram rows, behind the points.
# `data` = (hours, values, name, dt); first_row..last_row = rows shown; o = origin (h);
# T = period; double = double plot (each row shows two periods).
# Row geometry (same as for the points): row r covers data hours [o + r*T, o + r*T + span); a
# sample at hour h is drawn at x = h - o - r*T.  Rows are drawn with y increasing downwards
# (row r is centred at y = r, its band spans r-0.4 .. r+0.4).
# Activity bars: a filled step curve from the bottom of the band (y = r+0.4) upwards with
# height 0.8 * (value - vmin) / (vmax - vmin).  Heat map: one coloured cell per sample in
# the lower HEAT_HEIGHT part of the band, so the LD colour stays visible above it.
def draw_series_rows(ax, fig, st, data, first_row, last_row, o, T, double):
    """Activity bars (height = signal) or a heat map (colour = signal) in every row."""
    from matplotlib.colors import Normalize
    import matplotlib.cm as cm
    hours, vals, name, dt = data
    mode = st.get("ts_draw")
    # detrended data use a diverging colour map centred at 0 (blue - white - red)
    diverging = st.get("ts_draw_data") == "detrended"
    # scale every row on its own, or the whole record at once
    per_row = st.get("ts_draw_scale") == "row"
    # colour map: RdBu_r for detrended data, viridis for raw data
    cmap = matplotlib.colormaps["RdBu_r" if diverging else "viridis"]
    # x extent of one row
    span = 2 * T if double else T
    # the scale of the whole record (also used for the colour bar)
    whole = _limits(vals, diverging)
    if whole is None:
        return
    # the legend entry is added only once (on the first bar series)
    first_label = f"{name} (activity)" if mode == "activity" else None
    # every visible row
    for row in range(first_row, last_row + 1):
        # data hour at the left edge of this row
        lo_row = o + row * T
        # samples in this row (with one interval of margin) for per-row scaling
        sel = (hours >= lo_row - dt) & (hours <= lo_row + span + dt)
        lim = _limits(vals[sel], diverging) if per_row else whole
        if lim is None:
            continue
        vmin, vmax = lim
        # a double plot shows two periods per row: half 0 = this period, half 1 = the next one
        for half in range(2 if double else 1):
            lo = o + (row + half) * T
            # samples that fall into this half
            m = (hours >= lo - 1e-9) & (hours < lo + T - 1e-9)
            if not m.any():
                continue
            # x positions within the row
            x = hours[m] - o - row * T
            v = vals[m]
            # cell edges: half an interval on each side of every sample, clipped to the half
            xe = np.clip(np.concatenate([[x[0] - dt / 2], x + dt / 2]), half * T, (half + 1) * T)
            # close tiny gaps at the half boundaries so no white seam appears
            if xe[0] - half * T < dt:            # no white seam where the two halves (or rows) meet
                xe[0] = half * T
            if (half + 1) * T - xe[-1] < dt:
                xe[-1] = (half + 1) * T
            if mode == "activity":
                # bar heights as a fraction of the band height
                h = np.clip((v - vmin) / (vmax - vmin), 0, 1) * 0.8
                # y of the top of each bar (y grows downwards, so 'up' is minus); missing -> zero height
                yy = np.where(np.isfinite(h), row + 0.4 - h, row + 0.4)
                # a filled step curve = activity bars; 50 % transparent so the LD bands show through
                ax.stairs(yy, xe, baseline=row + 0.4, fill=True, color=ACTIVITY_COLOR, alpha=0.5,
                          linewidth=0, zorder=1.0, label=first_label)
                first_label = None
            else:
                # y edges of the heat-map strip: the lower part of the band
                ye = np.array([row + 0.4 - 0.8 * HEAT_HEIGHT, row + 0.4])
                # one row of cells; missing values are masked (not drawn)
                c = np.ma.masked_invalid(v.reshape(1, -1))
                # rasterized=True keeps SVG/PDF files small (thousands of cells become one image)
                ax.pcolormesh(xe, ye, c, cmap=cmap, vmin=vmin, vmax=vmax, shading="flat", zorder=1.0,
                              rasterized=True)
    # the colour bar explains the heat-map colours (position in figure coordinates)
    if mode == "heatmap":                     # colour bar under the legend
        cax = fig.add_axes([0.795, 0.2, 0.014, 0.2])
        # per-row scaling has no absolute values: label the ends 'low' / 'high'
        norm = Normalize(-1, 1) if (per_row and diverging) else Normalize(0, 1) if per_row else Normalize(*whole)
        cb = fig.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax)
        cb.ax.tick_params(labelsize=6.5)
        if per_row:
            cb.set_ticks([norm.vmin, norm.vmax])
            cb.set_ticklabels(["low", "high"])
        cb.set_label(name + (" (scaled per row)" if per_row else ""), fontsize=7)


# --------------------------------------------------------------------------- #
# Drawing
# --------------------------------------------------------------------------- #

# For 'Connect peaks/troughs': pair each event with the event closest to exactly one period
# later (between 0.5 and 1.5 periods), so the connecting lines show the drift of the rhythm.
def link_pairs(values: list, period: float) -> list:
    """Each event joined to the event about one period later (if any)."""
    # time order
    a = sorted(values)
    out = []
    for i, t1 in enumerate(a):
        best, best_d = None, math.inf
        # candidates after this event
        for t2 in a[i + 1:]:
            dt = t2 - t1
            # too far: the list is sorted, so stop
            if dt > 1.5 * period:
                break
            # too close to be the next cycle
            if dt < 0.5 * period:
                continue
            # keep the candidate nearest to one period later
            if abs(dt - period) < best_d:
                best, best_d = t2, abs(dt - period)
        if best is not None:
            out.append((t1, best))
    return out


# Upper limit of drawn rows (a tiny T on a long record would otherwise create millions).
MAX_ROWS = 1000
# Texts of the x-axis tick options; the stored value is the text itself.
X_MAJOR_CHOICES = ["No major tick (ticks at 0 and T only)"] + [
    f"{n} major tick{'s' if n > 1 else ''} per T ({n + 1} subdivisions)" for n in range(1, 6)]
X_MAJOR_DEFAULT = X_MAJOR_CHOICES[3]          # 3 major ticks per T (4 subdivisions)


# Read the number of major ticks from the stored option text (or a number).
def x_major_count(value) -> int:
    """'3 major ticks per T (4 subdivisions)', 3 or 'No major tick ...' -> 0-5 (default 3)."""
    text = str(value).strip()
    if text.lower().startswith("no"):
        return 0
    match = re.match(r"(\d+)", text)
    return max(0, min(5, int(match.group(1)))) if match else 3


X_MINOR_CHOICES = ["No minor tick"] + [
    f"{n} minor tick{'s' if n > 1 else ''} ({n + 1} subdivisions)" for n in range(1, 12)]


# Read the number of minor ticks from the stored option text (or a number).
def x_minor_count(value) -> int:
    """'3 minor ticks (4 subdivisions)', 3 or 'No minor tick' -> number of minor ticks (0-11)."""
    match = re.match(r"\s*(\d+)", str(value))
    return max(0, min(11, int(match.group(1)))) if match else 0


# Choose the rows automatically: from the row containing 0 h (or an earlier event or the
# sample placement) to the row containing the last event, the placement or the end of the
# drawn time series.  Row of hour h = floor((h - origin) / T).
def auto_rows(st: dict, res: Result) -> tuple[int, int]:
    """Automatic first and last row: from 0 h (or the earliest event) to the last event."""
    T, o = res.period, res.origin.hour
    # all peaks and troughs
    values = parse_list(st["peaks"])[0] + parse_list(st["troughs"])[0]
    # the sample placement must also be visible
    marks = [res.placed_hour] if res.placed_hour is not None else []
    # with a drawn time series, its first and last samples count as well
    data = series_for_actogram(st)
    if data is not None and np.isfinite(data[1]).any():
        hh = data[0][np.isfinite(data[1])]
        values = values + [float(hh[0]), float(hh[-1])]
    # start at 0 h of the data at the latest
    first_hour = min([0.0] + values + marks)
    # no data yet: show six rows
    last_hour = max(values + marks) if values else first_hour + 6 * T
    first_row = math.floor((first_hour - o) / T)
    # at least two rows
    last_row = max(math.floor((last_hour - o) / T), first_row + 1)
    return first_row, min(last_row, first_row + MAX_ROWS - 1)      # a very short T: cap the rows


# Returns the rows actually drawn (automatic, or the typed Min/Max when 'Automatic' is off),
# the automatic range (to prefill Min/Max) and a note for the rows line.
def row_range(st: dict, res: Result) -> tuple[tuple[int, int], tuple[int, int], str]:
    """((first, last) used, (first, last) automatic, note)."""
    auto = auto_rows(st, res)
    # automatic rows
    if st.get("rows_auto", True):
        # warn when the cap of MAX_ROWS was reached
        capped = auto[1] - auto[0] + 1 >= MAX_ROWS
        return auto, auto, (f"Only the first {MAX_ROWS} rows are drawn." if capped else "")
    try:
        # manual rows: Min and Max must be integers (negative = cycles before day 0)
        lo, hi = int(str(st["row_min"]).strip()), int(str(st["row_max"]).strip())
    except (TypeError, ValueError):
        return auto, auto, "Min and Max must be whole numbers; the automatic range is used."
    note = ""
    # tolerate reversed input
    if lo > hi:
        lo, hi, note = hi, lo, "Min is larger than Max, so the two are swapped."
    # enforce the cap
    if hi - lo + 1 > MAX_ROWS:
        hi, note = lo + MAX_ROWS - 1, f"At most {MAX_ROWS} rows are drawn."
    return (lo, hi), auto, note


# --------------------------------------------------------------------------- #
# Phase analysis of the selected peaks and troughs
# --------------------------------------------------------------------------- #

# Choices of the 0-degree reference for LL/DD conditions: (stored value, text in the list).
PHASE_REFS = (("zt0_prev", "Projected light-on (ZT0) of the preceding LD condition"),
              ("start", "Start of the condition"), ("zero", "0 h of the data"),
              ("day0", "Actogram day 0, 0 h"))


def k4(v) -> str:
    """Key for comparing times (4 decimals): selections are matched to peak/trough values by this key."""
    return f"{float(v):.4f}"


def cond_label(s: Segment, i: int) -> str:
    """Label of a condition in the result tables, e.g. 'Condition 2 · LD 15:00/15:00'."""
    kind = f"LD {format_duration(s.light)}/{format_duration(s.dark)}" if s.mode == "LD" else s.mode
    return f"Condition {i + 1} \u00b7 {kind}"


# Circular mean: every angle becomes a unit vector (cos, sin); the vectors are averaged.
# The direction of the mean vector is the mean angle, its length r (0..1) measures how well the
# angles agree (1 = identical).  The circular standard deviation is sqrt(-2 ln r) (radians,
# converted to degrees).  r is returned through the attribute circular_mean.last_r so the
# existing two-value interface stays unchanged.
def circular_mean(degrees: list) -> tuple:
    """Circular statistics of angles in degrees: (mean direction 0-360, mean resultant length r,
    circular SD = sqrt(-2 ln r) in degrees).  Used for LD phases, where 359° and 1° are close.
    """
    # sum of the x components
    c = sum(math.cos(math.radians(d)) for d in degrees)
    # sum of the y components
    s_ = sum(math.sin(math.radians(d)) for d in degrees)
    # length of the mean vector
    r = math.hypot(c, s_) / len(degrees)
    # direction of the mean vector, 0-360 degrees
    mean = (math.degrees(math.atan2(s_, c)) + 360) % 360
    # circular SD; undefined when r = 0 (angles cancel out completely)
    sd = math.degrees(math.sqrt(-2 * math.log(min(1.0, r)))) if r > 0 else math.nan
    circular_mean.last_r = r
    return mean, sd


# Phase analysis of the selected peaks/troughs, condition by condition.
#
# Returns {'groups': [...], 'events': [...], 'note': text}.  Each group is one condition and one
# kind (peaks or troughs) with: n, period, phase_deg, phase_h, sd (LD) or se/r2/b/se_b/phase_se/ct
# (LL/DD), the reference used, and its events.  Each event is {'kind', 'h'} plus, after the
# analysis, 'seg' (condition index), 'cycle', and 'zt'/'phase' (LD) or 't'/'fit'/'resid' (LL/DD).
def analyze(st: dict, res: Result) -> dict:
    """Phase of the selected peaks/troughs in each condition.
    LD: ZT relative to light-on (circular mean).  LL/DD: t = b + tau*n regression of the
    event time t (h after the 0-degree reference) on the cycle number n."""
    out = {"groups": [], "events": [], "note": ""}
    # 1. the selected points (selections are matched to the list values by their 4-decimal key)
    sel = {"Peak": {k4(v) for v in st.get("sel_peaks", [])}, "Trough": {k4(v) for v in st.get("sel_troughs", [])}}
    events = []
    # collect every selected value from the lists
    for kind, key in (("Peak", "peaks"), ("Trough", "troughs")):
        for h in parse_list(st[key])[0]:
            if k4(h) in sel[kind]:
                events.append({"kind": kind, "h": h})
    # time order
    events.sort(key=lambda e: e["h"])
    out["events"] = events
    if not events:
        out["note"] = "Select peaks or troughs in the actogram to analyse their phase."
        return out
    if res.ld is None:
        out["note"] = "Set valid light/dark conditions (and the clock time of 0 h) to analyse phases."
        return out
    # the conditions of the light/dark schedule
    segs = res.ld.segments
    # 2. which condition each point falls in (a condition lasts until the next one starts)
    for e in events:
        # -1 = before the first condition
        e["seg"] = -1
        for i, s in enumerate(segs):
            a = -math.inf if (i == 0 and res.ld.extend_before) else s.start_hour
            b = segs[i + 1].start_hour if i + 1 < len(segs) else math.inf
            # the point lies in condition i
            if a <= e["h"] < b:
                e["seg"] = i
    notes = []
    if any(e["seg"] < 0 for e in events):
        notes.append("Points before the first condition are not analysed.")
    # one group per condition and kind
    for i, s in enumerate(segs):
        for kind in ("Peak", "Trough"):
            ev = [e for e in events if e["seg"] == i and e["kind"] == kind]
            if not ev:
                continue
            # group record with defaults (NaN = not computed)
            g = {"seg": i, "label": cond_label(s, i), "kind": kind, "mode": s.mode, "n": len(ev), "events": ev,
                 "period": math.nan, "se": math.nan, "r2": math.nan, "phase_deg": math.nan, "phase_h": math.nan,
                 "sd": math.nan, "fit_note": ""}
            if s.mode == "LD":
                # 3a. LD: zeitgeber time = hours after the last light-on, modulo the cycle length;
                #     phase in degrees = ZT / (L + D) * 360; mean and spread by circular statistics.
                # cycle length
                P = s.light + s.dark
                # the first light-on: the start itself, or after the first dark part
                on = s.start_hour if s.starts_with_light else s.start_hour + s.dark
                for e in ev:
                    # ZT = hours since the last light-on (modulo the cycle length)
                    e["zt"] = (e["h"] - on) % P
                    # phase angle 0-360 degrees
                    e["phase"] = e["zt"] / P * 360
                    # which cycle after the first light-on
                    e["cycle"] = math.floor((e["h"] - on) / P + 1e-9)
                # circular mean phase and its spread
                mean, sd = circular_mean([e["phase"] for e in ev])
                # phase_h = mean phase converted back to hours (the 'Mean ZT')
                g.update(period=P, phase_deg=mean, phase_h=mean / 360 * P, sd=sd, ref="light-on (ZT0)", on=on,
                         r=circular_mean.last_r,
                         start=-math.inf if (i == 0 and res.ld.extend_before) else s.start_hour,
                         end=segs[i + 1].start_hour if i + 1 < len(segs) else math.inf)
            else:
                # 3b. LL/DD: no light-on to measure from.  Choose a 0-degree reference R, number the
                #     cycles n, and fit the straight line t = b + tau*n by least squares, where t is
                #     the time of each point after R.  tau = free-running period, b = intercept,
                #     phase = (b mod tau) / tau * 360.  P0 (the previous LD period, or 24 h) is only
                #     used to count cycles.
                R, ref, P0 = s.start_hour, "start of the condition", 24.0
                # the nearest preceding LD condition with light (its period and light-on are used as reference)
                prev = next((segs[j] for j in range(i - 1, -1, -1) if segs[j].mode == "LD" and segs[j].light > 0), None)
                if prev is not None:
                    # cycle length used only to number the cycles
                    P0 = prev.light + prev.dark
                choice = st.get("phase_ref", "zt0_prev")
                # default: the light-on times of the preceding LD continued into this condition (projected ZT0);
                # R = the last projected light-on at or before the start of this condition
                if choice == "zt0_prev":
                    if prev is not None:
                        on0 = prev.start_hour if prev.starts_with_light else prev.start_hour + prev.dark
                        R = on0 + math.floor((s.start_hour - on0) / P0 + 1e-9) * P0
                        ref = "projected ZT0 of the preceding LD"
                        g["ref_seg"] = segs.index(prev)
                    else:
                        notes.append(f"{g['label']}: no preceding LD condition, so its start is used as 0\u00b0.")
                # or simply 0 h of the data / actogram day 0, 0 h
                elif choice == "zero":
                    R, ref = 0.0, "0 h of the data"
                elif choice == "day0":
                    R, ref = res.origin.hour, "actogram day 0, 0 h"
                # cycle number of the first point: whole periods between R and the point
                n = math.floor((ev[0]["h"] - R) / P0 + 1e-9)
                # following points: +1 per cycle, more if a cycle was skipped (no point selected in it)
                for k, e in enumerate(ev):          # a gap of about one period adds one cycle
                    if k:
                        n += max(1, round((e["h"] - ev[k - 1]["h"]) / P0))
                    # t = time after the reference
                    e["cycle"], e["t"] = n, e["h"] - R
                g.update(ref=ref, R=R)
                if len(ev) >= 2:
                    # ordinary least squares with standard errors of slope (tau) and intercept (b)
                    xs = [e["cycle"] for e in ev]
                    ys = [e["t"] for e in ev]
                    N = len(ev)
                    # means of x = cycle number and y = t
                    mx, my = sum(xs) / N, sum(ys) / N
                    # sums of squares / cross products around the means
                    sxx = sum((x - mx) ** 2 for x in xs)
                    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
                    syy = sum((y - my) ** 2 for y in ys)
                    if sxx > 0:
                        # slope = free-running period tau
                        tau = sxy / sxx
                        # intercept b = fitted time of cycle 0 after R
                        b = my - tau * mx
                        # residual sum of squares
                        ssr = sum((y - (b + tau * x)) ** 2 for x, y in zip(xs, ys))
                        # phase in hours within one cycle (whole cycles removed)
                        ph = b % tau
                        for e in ev:
                            # fitted value and residual of every point (for the tables and the plot)
                            e["fit"] = b + tau * e["cycle"]
                            e["resid"] = e["t"] - e["fit"]
                        # standard error of the intercept (needs at least 3 points)
                        se_b = math.sqrt(ssr / (N - 2) * (1 / N + mx * mx / sxx)) if N > 2 else math.nan
                        # SE of the slope, R^2, phase in degrees and its SE, and circadian time CT = phase scaled to 24 h
                        g.update(period=tau, se=math.sqrt(ssr / (N - 2) / sxx) if N > 2 else math.nan,
                                 r2=1 - ssr / syy if syy > 0 else 1.0, b=b, phase_h=ph, phase_deg=ph / tau * 360,
                                 se_b=se_b, phase_se=se_b / tau * 360, ct=ph * 24 / tau)
                    else:
                        # all points share one cycle number: the slope is undefined
                        g["fit_note"] = "all points in one cycle"
                else:
                    g["fit_note"] = "needs at least 2 points"
            out["groups"].append(g)
    out["note"] = " ".join(notes)
    return out


def _f(v, digits: int) -> str:
    """Format a number with `digits` decimals, or an en dash when it is missing/not finite."""
    return f"{v:.{digits}f}" if isinstance(v, (int, float)) and math.isfinite(v) else "\u2013"


# Rows of the summary table: one per group.  LD rows leave the LL/DD columns empty and the other
# way round; numbers are formatted for display and CSV.
def result_rows(ana: dict) -> list:
    """Summary table (header + one row per condition and peak/trough type) for export and display."""
    head = ["Condition", "Type", "n", "Period (h)", "Period SE (h)", "R\u00b2", "Phase (\u00b0)", "Phase (h)",
            "Phase SD (\u00b0)", "0\u00b0 reference"]
    rows = [head]
    for g in ana["groups"]:
        ld = g["mode"] == "LD"
        rows.append([g["label"], g["kind"] + "s", g["n"], _f(g["period"], 2), "" if ld else _f(g["se"], 2),
                     "" if ld else _f(g["r2"], 3), _f(g["phase_deg"], 1), _f(g["phase_h"], 2),
                     _f(g["sd"], 1) if ld else "", g["ref"] + (f" ({g['fit_note']})" if g["fit_note"] else "")])
    return rows


# Rows of the per-point table ('Each selected point').
def event_rows(ana: dict, res: Result) -> list:
    """Table of every selected point: time, local clock time, condition, cycle, ZT or t, phase, residual."""
    head = ["Type", "Time (h)", "Local date/time", "Condition", "Cycle", "ZT or t from 0\u00b0 (h)", "Phase (\u00b0)",
            "Residual (h)"]
    rows = [head]
    for e in ana["events"]:
        # the group that contains this event (identity comparison, the same dict objects)
        g = next((x for x in ana["groups"] if any(y is e for y in x["events"])), None)
        # the local clock time of the point (rounded to the minute)
        when = format_local(res.zero + timedelta(minutes=round(e["h"] * 60)), res.tz) if res.zero is not None else ""
        # LD: ZT and its phase; LL/DD: t and t mod period
        if "zt" in e:
            rel, ph = e["zt"], e["phase"]
        else:
            rel = e.get("t", math.nan)
            ph = ((rel % g["period"]) / g["period"] * 360) if g and math.isfinite(g["period"]) else math.nan
        rows.append([e["kind"], f"{e['h']:.2f}", when, g["label"] if g else "no condition", e.get("cycle", ""),
                     _f(rel, 2), _f(ph, 1), _f(e["resid"], 2) if "resid" in e else ""])
    return rows


# Used by the phase dial: every point's own angle.
def event_phase(e: dict, g: dict) -> float:
    """Phase (°) of one point: from its ZT in LD, or t mod period in LL/DD."""
    if "zt" in e:
        return e["phase"]
    # LL/DD: position of t within one fitted period
    if math.isfinite(g["period"]):
        return (e["t"] % g["period"]) / g["period"] * 360
    return math.nan


# The 'Phase results' window: for each condition a block with a dial and text/tables.
# The dial is a clock face: 0 deg at the top, angles increase clockwise; its ring shows light
# (yellow) and dark (dark grey) for LD, all light for LL, all dark for DD.  Dots = the selected
# points at their phase; lines from the centre = mean phases (LD: length = r).
def draw_phase_results(fig: Figure, ana: dict, res: Result) -> float:
    """One block per condition: a dial (0 deg at the top, clockwise) and the results.
    Returns the figure height (inches) it needs."""
    from matplotlib.patches import Circle, Wedge
    fig.clear()
    # nothing to show: a one-line message
    if res.ld is None or not ana["events"]:
        fig.set_size_inches(9.6, 1.0)
        fig.text(0.02, 0.5, ana["note"] or "Select peaks or troughs to see the phase results.", va="center",
                 fontsize=10, color="#555555")
        return 1.0
    segs = res.ld.segments
    # height of one condition block (inches)
    block = 2.35
    height = block * len(segs) + 0.2
    # the figure grows with the number of conditions
    fig.set_size_inches(9.6, height)
    # helper: an hour of the data as local clock time plus the hour itself
    at = lambda h: f"{format_local(res.zero + timedelta(minutes=round(h * 60)), res.tz)} ({h:.2f} h)"
    for i, s in enumerate(segs):
        # top of block i as a fraction of the figure height (0 = bottom, 1 = top)
        top = 1 - (0.1 + i * block) / height            # figure fraction at the top of this block
        gs = [g for g in ana["groups"] if g["seg"] == i]
        # dial
        dial_h = 1.75 / height
        # a square axes for the dial at the left of the block
        ax = fig.add_axes([0.01, top - dial_h - 0.1 / height, 1.75 / 9.6, dial_h])
        ax.set_xlim(-1.1, 1.1); ax.set_ylim(-1.1, 1.1); ax.set_aspect("equal"); ax.axis("off")
        light, dark = "#f5d77e", "#3b4252"
        # the ring: all dark (or all light for LL)
        ax.add_patch(Wedge((0, 0), 1.0, 0, 360, width=0.17, color=light if s.mode == "LL" else dark))
        if s.mode == "LD" and s.light > 0 and s.dark > 0:
            # LD: the light part as a wedge starting at 12 o'clock (matplotlib angles count anticlockwise
            # from 3 o'clock, hence 90 - frac .. 90)
            frac = s.light / (s.light + s.dark) * 360
            ax.add_patch(Wedge((0, 0), 1.0, 90 - frac, 90, width=0.17, color=light))
        # white centre
        ax.add_patch(Circle((0, 0), 0.83, color="white"))
        # angle labels inside the ring
        for txt, a in (("0\u00b0", 0), ("90\u00b0", 90), ("180\u00b0", 180), ("270\u00b0", 270)):
            ax.text(0.6 * math.sin(math.radians(a)), 0.6 * math.cos(math.radians(a)), txt, fontsize=6,
                    ha="center", va="center", color="#555555")
        for g in gs:
            color = PEAK_COLOR if g["kind"] == "Peak" else TROUGH_COLOR
            # points at nearly the same phase (6-degree bins) are stacked inwards so they stay visible
            stack = {}
            for e in g["events"]:
                ph = event_phase(e, g)
                if not math.isfinite(ph):
                    continue
                k = round(ph / 6)
                stack[k] = stack.get(k, 0) + 1
                rr = 0.76 - (stack[k] - 1) * 0.08
                # x = r sin(angle), y = r cos(angle): 0 deg at the top, clockwise
                ax.plot(rr * math.sin(math.radians(ph)), rr * math.cos(math.radians(ph)), "o", ms=2.6, color=color)
            if math.isfinite(g["phase_deg"]):
                # the mean-phase hand; for LD its length shows r (agreement of the points)
                length = (g.get("r", 1.0) if g["mode"] == "LD" else 1.0) * 0.8
                ax.plot([0, length * math.sin(math.radians(g["phase_deg"]))],
                        [0, length * math.cos(math.radians(g["phase_deg"]))], color=color, lw=2.2, solid_capstyle="round")
        ax.plot(0, 0, "o", ms=3, color="#111111")
        # text
        # text starts to the right of the dial
        x0 = 2.05 / 9.6
        name = f"LD {format_duration(s.light).zfill(5)}/{format_duration(s.dark).zfill(5)}" if s.mode == "LD" else s.mode
        # block title, e.g. '#2 LD 11:30/11:30'
        fig.text(x0, top - 0.12 / height, f"#{i + 1} {name}", fontsize=11, fontweight="bold", family="monospace", va="top")
        sub = f"Starts {at(s.start_hour)}"
        if s.mode == "LD":
            sub += (f", begins with {'light' if s.starts_with_light else 'dark'}. ZT0 = light-on; "
                    f"cycle length {s.light + s.dark:.2f} h.")
        # LL/DD: say which 0-degree reference was used
        elif gs:
            g0 = gs[0]
            sub += (f". 0\u00b0 = projected light-on (ZT0) of LD #{g0['ref_seg'] + 1}: {at(g0['R'])}." if "ref_seg" in g0
                    else f". 0\u00b0 = {g0['ref']}: {at(g0['R'])}.")
        fig.text(x0, top - 0.42 / height, sub, fontsize=7.5, color="#555555", va="top")
        if not gs:
            fig.text(x0, top - 0.75 / height, "No points selected in this condition.", fontsize=8.5, color="#777777", va="top")
            continue
        # big coloured phase numbers, one per kind
        for k, g in enumerate(gs):
            color = PEAK_COLOR if g["kind"] == "Peak" else TROUGH_COLOR
            xk = x0 + k * 0.3
            fig.text(xk, top - 0.62 / height, _f(g["phase_deg"], 1) + "\u00b0", fontsize=17, fontweight="bold",
                     color=color, va="top")
            if g["mode"] == "LD":
                line = f"{g['kind']}s: mean ZT {_f(g['phase_h'], 2)} h, n = {g['n']}"
            elif math.isfinite(g["period"]):
                line = f"{g['kind']}s: \u03c4 = {g['period']:.2f} h ({format_duration(g['period'])}), n = {g['n']}"
            else:
                line = f"{g['kind']}s: n = {g['n']} ({g['fit_note']})"
            fig.text(xk, top - 1.0 / height, line, fontsize=7.5, color="#555555", va="top")
        # the table of the block: LD columns or LL/DD columns
        if s.mode == "LD":
            head = ["Kind", "N", "Mean phase (\u00b0)", "Mean ZT (h)", "r", "Circular SD (\u00b0)"]
            rows = [[g["kind"] + "s", g["n"], _f(g["phase_deg"], 1), _f(g["phase_h"], 2), _f(g.get("r", math.nan), 3),
                     _f(g["sd"], 1)] for g in gs]
        else:
            head = ["Kind", "N", "Period \u03c4 (h)", "\u00b1 SE", "Intercept b (h)", "Phase (\u00b0)", "\u00b1 SE (\u00b0)",
                    "Phase (h)", "Phase (CT)", "R\u00b2"]
            rows = [[g["kind"] + "s", g["n"], _f(g["period"], 3), _f(g["se"], 3), _f(g.get("b", math.nan), 2),
                     _f(g["phase_deg"], 1), _f(g.get("phase_se", math.nan), 1), _f(g["phase_h"], 2),
                     _f(g.get("ct", math.nan), 2), _f(g["r2"], 4)] for g in gs]
        tab_h = 0.22 * (len(rows) + 1) / height
        # an invisible axes that holds the matplotlib table
        tax = fig.add_axes([x0, top - 1.3 / height - tab_h, 1 - x0 - 0.02, tab_h])
        tax.axis("off")
        widths = ([0.14, 0.08, 0.2, 0.18, 0.14, 0.2] if s.mode == "LD"
                  else [0.1, 0.05, 0.12, 0.08, 0.13, 0.1, 0.1, 0.1, 0.11, 0.09])
        table = tax.table(cellText=[[str(c) for c in r] for r in rows], colLabels=head, loc="upper left",
                          cellLoc="right", colLoc="right", edges="horizontal",
                          colWidths=[w / sum(widths) for w in widths])
        table.auto_set_font_size(False)
        table.set_fontsize(7.5)
        # style the table: thin grey lines, bold grey header, coloured first column
        for (r, c), cell in table.get_celld().items():
            cell.set_edgecolor("#d3d9e0")
            if r == 0:
                cell.get_text().set_color("#5f6b78"); cell.get_text().set_fontweight("bold")
            elif c == 0:
                cell.get_text().set_color(PEAK_COLOR if rows[r - 1][0] == "Peaks" else TROUGH_COLOR)
                cell.get_text().set_fontweight("bold")
            if c == 0:
                cell.set_text_props(ha="left")
        # explanation of the phase in hours under the table
        note = (f"Mean ZT (h) is the phase in hours: the time after light-on (ZT0) within the {s.light + s.dark:.2f}-h "
                f"cycle, = phase (\u00b0) \u00f7 360 \u00d7 (L + D)." if s.mode == "LD" else
                "Phase (h): hours from the 0\u00b0 reference to the fitted event within one cycle, b mod \u03c4 "
                "(= phase \u00b0 \u00f7 360 \u00d7 \u03c4).  Phase (CT): the same in circadian hours (\u03c4 scaled to "
                "24 h), Phase (h) \u00d7 24 \u00f7 \u03c4.")
        import textwrap
        fig.text(x0, top - 1.3 / height - tab_h - 0.08 / height, textwrap.fill(note, 150), fontsize=6.8,
                 color="#666666", va="top", linespacing=1.3)
        # a thin separator line between blocks
        if i + 1 < len(segs):
            line_y = top - (block - 0.05) / height
            fig.add_artist(matplotlib.lines.Line2D([0.01, 0.99], [line_y, line_y], color="#d3d9e0", lw=0.8))
    return height


def draw_actogram(fig: Figure, st: dict, res: Result) -> list:
    """Draw the actogram on `fig` and return the hit targets for clicking points.

    Layout: row r covers [origin + r*T, origin + (r+1)*T) (single plot) or two periods (double
    plot), drawn top to bottom.  A data time h appears in row floor((h - origin)/T) at
    x = h - origin - r*T (and, in a double plot, also one row higher at x + T).  Drawing order:
    LD bands -> optional time series (activity/heat map) -> connecting lines -> fitted lines ->
    points and selection rings -> asterisks, labels, legend and the list of conditions.
    """
    # start from an empty figure with one axes
    fig.clear()
    ax = fig.add_subplot(111)
    # with row start stamps on the y axis, more room is needed on the left
    stamps = bool(st.get("label_row_starts")) and res.zero is not None and res.tz is not None
    # the right quarter of the figure is kept for the legend and the list of conditions
    fig.subplots_adjust(left=0.17 if stamps else 0.09, right=0.76, top=0.92, bottom=0.17)
    T = res.period
    double = st["plot"] == "double"
    span = 2 * T if double else T          # width of one row on the x axis
    o = res.origin.hour                    # actogram day 0, 0 h in hours after 0 h of the data
    # the values to plot (the detected or typed lists)
    peaks, _ = parse_list(st["peaks"])
    troughs, _ = parse_list(st["troughs"])
    values = peaks + troughs
    # the rows to draw (automatic or manual)
    (first_row, last_row), _auto, _note = row_range(st, res)
    # draw bands only if the schedule is shown and valid
    ld = res.ld if st["show_ld"] else None

    # LD bands behind each row (both halves of the double plot)
    light_color = pick_color(st.get("light_color"), LIGHT_COLORS)
    dark_color = pick_color(st.get("dark_color"), DARK_COLORS)
    if ld is not None:
        # with a single LD condition the legend can show the actual L and D lengths
        single_ld = len(ld.segments) == 1 and ld.segments[0].mode == "LD"
        light_label = f"Light (L {format_duration(ld.segments[0].light)})" if single_ld else "Light (L)"
        dark_label = f"Dark (D {format_duration(ld.segments[0].dark)})" if single_ld else "Dark (D)"
        # for every row: collect the light and dark intervals inside the row's time window
        for row in range(first_row, last_row + 1):
            lights, darks = [], []
            for half in range(2 if double else 1):
                # data hour at the start of this half of the row
                lo = o + (row + half) * T
                for a, b, is_light in ld.intervals(lo, lo + T):
                    # convert to (x start, width) within the row, as broken_barh expects
                    (lights if is_light else darks).append((a - o - row * T, b - a))
            if lights:
                # light bands (a thin outline if the colour is white, otherwise they would be invisible)
                ax.broken_barh(lights, (row - 0.4, 0.8), facecolors=light_color,
                               linewidth=0.4 if light_color == "#ffffff" else 0, edgecolor="#d0d0d0",
                               zorder=0.5, label=light_label)
                # the legend entry only once
                light_label = None
            if darks:
                ax.broken_barh(darks, (row - 0.4, 0.8), facecolors=dark_color,
                               edgecolor="none", zorder=0.5, label=dark_label)
                dark_label = None

        # optional labels: clock time at which each light / dark period begins
        # labels such as 'L 08:00  Oct. 5' at the start of each light and dark period
        if st.get("label_onsets") and res.zero is not None and res.tz is not None:
            # look one cycle earlier so the first onset in view is recognised as a real onset
            lo_all = o + (first_row - 1) * T            # one cycle earlier, to find true onsets
            hi_all = o + (last_row + (2 if double else 1)) * T
            merged = []
            # merge neighbouring intervals of the same kind (e.g. the dark of an LD that runs on into DD)
            for a, b, is_light in sorted(ld.intervals(lo_all, hi_all)):
                if merged and merged[-1][2] == is_light and abs(merged[-1][1] - a) < 1e-9:
                    merged[-1][1] = b                    # e.g. dark of LD running on into DD
                else:
                    merged.append([a, b, is_light])
            for a, _b, is_light in merged:
                # intervals that start before the window are not true onsets
                if a <= lo_all + 1e-9:
                    continue
                # the row in which this onset lies
                row = math.floor((a - o) / T + 1e-9)
                x = a - o - row * T
                if row < first_row:
                    continue
                # onsets after the last row appear only in the right half of the last row (double plot)
                if row > last_row:                       # only in the right half of the last row
                    if not (double and row - 1 == last_row):
                        continue
                    row, x = row - 1, x + T
                # the onset as local clock time
                when = (res.zero + timedelta(minutes=round(a * 60))).astimezone(res.tz)
                stamp = f"{when:%H:%M}  {when:%b}. {when.day}"          # e.g. 'D 04:00  Oct. 6'
                ax.text(x + 0.006 * span, row - 0.42, f"{'L' if is_light else 'D'} {stamp}",
                        fontsize=6, ha="left", va="bottom", zorder=4, clip_on=True,
                        color="#7a5c00" if is_light else "#333333")

    # optional: the time series itself (activity bars or heat map)
    series_data = series_for_actogram(st)
    if series_data is not None:
        draw_series_rows(ax, fig, st, series_data, first_row, last_row, o, T, double)

    # connecting lines
    # 'Connect peaks / troughs': a line from each event to the event one period later; in the
    # actogram this runs from row r to row r+1, so its slant shows the drift of the rhythm
    for vals, on, color in ((peaks, st["link_peak"], PEAK_COLOR),
                            (troughs, st["link_trough"], TROUGH_COLOR)):
        if not on:
            continue
        for t1, t2 in link_pairs(vals, T):
            for row in range(first_row, last_row):
                # x of the first event in this row
                x1 = t1 - o - row * T
                if 0 <= x1 < span:
                    # the second event is one row lower, at x + (t2 - t1) - T
                    ax.plot([x1, x1 + (t2 - t1) - T], [row, row + 1], color=color,
                            linewidth=1.1, alpha=0.6, zorder=2)

    # asterisks: 0 h of the data (green) and the sample placement (orange)
    # the two asterisks (both optional through 'Mark 0 h ... and the sample placement')
    if st.get("mark_times", True):
        marks = []
        if res.placed_hour is not None:
            marks.append((res.placed_hour, PLACED_COLOR, "Sample placed"))
        if res.zero is not None:
            marks.append((0.0, ZERO_COLOR, "0 h of the data"))
        for h, color, label in marks:
            # row in which the moment lies, and its x within the row
            day = math.floor((h - o) / T + 1e-9)
            x = h - o - day * T
            spots = []
            if first_row <= day <= last_row:
                spots.append((x, day))
            # double plot: also one row higher, in the right half
            if double and first_row <= day - 1 <= last_row:
                spots.append((x + T, day - 1))
            for k, (xx, yy) in enumerate(spots):
                ax.plot([xx], [yy], linestyle="none", marker=ASTERISK, markersize=7, markeredgewidth=1.1,
                        color=color, zorder=3.5, label=label if k == 0 else None)

    # condition changes: thin light-purple line at each start of LD, LL or DD
    # a short vertical line where each condition starts
    if ld is not None and st.get("mark_changes", True):
        first_label = "Condition change"
        for sg in ld.segments:
            day = math.floor((sg.start_hour - o) / T + 1e-9)
            x = sg.start_hour - o - day * T
            spots = [(x, day)] if first_row <= day <= last_row else []
            if double and first_row <= day - 1 <= last_row:
                spots.append((x + T, day - 1))
            for xx, yy in spots:
                ax.plot([xx, xx], [yy - 0.5, yy + 0.5], color=CHANGE_COLOR, linewidth=1.4, zorder=1.5,
                        solid_capstyle="butt", label=first_label)
                first_label = None

    def fitted_segment(h1, h2, **style):
        """Draw a fitted line from (h1) to (h2 = h1 + one period) in the double-plot geometry:
        it starts in its own row and ends one row lower.
        """
        for row in range(first_row, last_row + 1):
            x1 = h1 - o - row * T
            if 0 <= x1 < span:
                ax.plot([x1, x1 + (h2 - h1) - T], [row, row + 1], **style)

    # fitted lines: mean phase in LD (thin black dotted), regression in LL/DD (dashed)
    # 'Draw fitted lines' (results of the phase analysis)
    if st.get("draw_fit", True):
        # run the analysis to get the fitted phases/periods
        groups = analyze(st, res)["groups"]
        # the time window covered by the visible rows (with one cycle margin)
        lo, hi = o + (first_row - 1) * T, o + (last_row + 2) * T
        for grp in groups:
            # LD: a dotted line at the mean phase in every cycle of the condition
            if grp["mode"] != "LD" or not math.isfinite(grp["phase_h"]):
                continue
            # time of the mean phase in the first cycle
            P, base = grp["period"], grp["on"] + grp["phase_h"]
            a, b = max(grp["start"], lo), min(grp["end"], hi)
            # first cycle inside the window
            nn = math.ceil((a - base) / P - 1e-9)
            while base + (nn + 1) * P < b + 1e-9:
                fitted_segment(base + nn * P, base + (nn + 1) * P, color="#111111", linewidth=0.8,
                               linestyle=(0, (1, 2)), zorder=2)
                nn += 1
        # LL/DD: the regression line t = b + tau*n, drawn cycle by cycle between the first and last
        # selected cycle
        for grp in groups:
            if grp["mode"] == "LD" or not math.isfinite(grp["period"]):
                continue
            color = PEAK_COLOR if grp["kind"] == "Peak" else TROUGH_COLOR
            cycles = [e["cycle"] for e in grp["events"]]
            for nn in range(min(cycles), max(cycles)):
                # fitted time of cycle nn, as hours after 0 h of the data
                h1 = grp["R"] + grp["b"] + grp["period"] * nn
                h2 = h1 + grp["period"]
                for row in range(first_row, last_row + 1):
                    x1 = h1 - o - row * T
                    if 0 <= x1 < span:
                        ax.plot([x1, x1 + (h2 - h1) - T], [row, row + 1], color=color, linewidth=1.2,
                                linestyle=(0, (5, 3)), alpha=0.85, zorder=2)

    # points (double plot: each event also drawn at x + T in the row above); selected ones ringed
    # `hits` collects every drawn point (x, y, kind, value) so mouse clicks can find them
    hits = []
    # keys of the selected values
    selected = {"p": {k4(v) for v in st.get("sel_peaks", [])}, "t": {k4(v) for v in st.get("sel_troughs", [])}}
    for vals, color, label in ((peaks, PEAK_COLOR, "Peaks"), (troughs, TROUGH_COLOR, "Troughs")):
        if not st.get("show_points", True):
            break
        # short key used in `hits` and in the selection: 'p' peak, 't' trough
        kk = "p" if label == "Peaks" else "t"
        xs, ys, hs = [], [], []
        # place every value in its row
        for h in vals:
            # row (cycle) of this time
            day = math.floor((h - o) / T)
            # x within the row
            x = h - o - day * T
            if first_row <= day <= last_row:
                xs.append(x), ys.append(day), hs.append(h)
            # double plot: the same point again in the right half of the row above
            if double and first_row <= day - 1 <= last_row:
                xs.append(x + T), ys.append(day - 1), hs.append(h)
        hits += [(x, y, kk, h) for x, y, h in zip(xs, ys, hs)]
        # selected points get a black ring
        ring = [(x, y) for x, y, h in zip(xs, ys, hs) if k4(h) in selected[kk]]
        if ring:
            ax.scatter([r[0] for r in ring], [r[1] for r in ring], s=70, facecolors="none", edgecolors="#111111",
                       linewidths=1.0, zorder=3.2)
        if xs:
            # the points themselves
            ax.scatter(xs, ys, marker="o", s=20, color=color, label=label, zorder=3)
            # 'Show times': the value (h) next to each point
            if st["show_values"]:
                for x, y, h in zip(xs, ys, hs):
                    ax.text(x + 0.02 * T, y - 0.12, f"{h:.1f}", fontsize=5.5, color=color, zorder=4)
    # empty plot: a hint in the middle
    if not values and series_data is None:
        ax.text(0.5, 0.5, "Paste peak and trough times to plot them", transform=ax.transAxes,
                ha="center", va="center", color="#666666")

    # axes
    # x axis: one row width
    ax.set_xlim(0, span)
    # number of subdivisions of one period by the major ticks
    parts = x_major_count(st.get("x_major", X_MAJOR_DEFAULT)) + 1     # subdivisions per period T
    # major tick positions over the whole row
    majors = [k * T / parts for k in range(0, parts * (2 if double else 1) + 1)]
    ax.set_xticks(majors)
    # as few decimals as are needed to show the tick values exactly
    decimals = next((d for d in (0, 1, 2, 3) if all(abs(round(v, d) - v) < 1e-9 for v in majors)), None)
    if decimals is None:       # enough decimals to tell neighbouring ticks apart (very short T too)
        step = majors[1] - majors[0] if len(majors) > 1 else T
        decimals = max(2, min(4, math.ceil(-math.log10(step)) + 1 if step < 1 else 2))
    ax.xaxis.set_major_formatter(FormatStrFormatter(f"%.{decimals}f"))
    minor = x_minor_count(st.get("x_minor", 0))
    # optional unlabelled minor ticks between the major ones
    if minor:          # optional minor ticks between the major ticks, without labels
        ax.xaxis.set_minor_locator(AutoMinorLocator(minor + 1))
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.tick_params(axis="x", which="minor", length=3, width=0.6)
    # leave room above the first row for the onset labels
    top_pad = 0.85 if (st.get("label_onsets") and ld is not None) else 0.6   # room for the top labels
    # y axis: one unit per row
    ax.set_ylim(first_row - top_pad, last_row + 0.6)
    rows = list(range(first_row, last_row + 1))
    ax.set_yticks(rows)
    # 'Day' when T is exactly 24 h, otherwise 'Cycle'
    unit = "Day" if abs(T - 24) < 1e-9 else "Cycle"
    # 'Row labels: Date' shows the calendar date of each row start
    date_labels = st["rowlab"] == "date" and res.zero is not None and res.tz is not None

    def row_start(r):
        """Local clock time at which row r starts (for the 'date' row labels)."""
        return (res.zero + timedelta(minutes=round((o + r * T) * 60))).astimezone(res.tz)

    # 'Label the start date/time of each cycle': date and time of each row start on the y axis
    if stamps:      # optional: start date/time of each cycle (row)
        if date_labels:
            ax.set_yticklabels([f"{row_start(r):%b %d %H:%M} {row_start(r).tzname()}" for r in rows],
                               fontsize=7)
        else:
            ax.set_yticklabels([f"{r}   {row_start(r):%b %d %H:%M} {row_start(r).tzname()}" for r in rows],
                               fontsize=7)
    if date_labels:
        if not stamps:
            ax.set_yticklabels([row_start(r).strftime("%b %d") for r in rows])
        ax.set_ylabel("Date (row start)")
    else:
        extra = f"; {res.origin.y_text}" if res.origin.y_text else ""
        ax.set_ylabel(f"{unit} (T = {g(T)} h{extra})")
    # with many rows, show only about 30 labels
    if len(rows) > 40:
        for k, lab in enumerate(ax.get_yticklabels()):
            lab.set_visible(k % max(1, len(rows) // 30) == 0)
    # row 0 at the top, later rows below (like an actogram on paper)
    ax.invert_yaxis()
    ax.grid(True, linestyle="--", alpha=0.7)
    # x-axis title explains what 0 means, e.g. '0 = lights-on, 14:37'
    ax.set_xlabel(f"Time within cycle (h; {res.origin.x_text})" if res.origin.x_text
                  else "Time within cycle (h)")
    # default title when none was entered
    title = st["title"].strip() or (f"Actogram of peaks and troughs "
                                    f"({'double' if double else 'single'}-plotted, T = {g(T)} h)")
    ax.set_title(title, fontsize=10)
    # under the x axis: the clock time of day 0, 0 h
    if res.zero is not None and res.tz is not None:
        note = (f"{unit} 0, 0 h = {format_local(res.zero + timedelta(hours=o), res.tz)} "
                f"(local, {zone_name(res.tz)})")
        ax.xaxis.label.set_va("top")
        ax.annotate(note, xy=(0.5, 0), xycoords=ax.xaxis.label, xytext=(0, -2),
                    textcoords="offset points", ha="center", va="top", fontsize=7,
                    color="#555555", annotation_clip=False)

    # legend to the right of the plot
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=8,
                  frameon=True, borderaxespad=0)
    # below the legend: the list of conditions with their starts in hours
    if ld is not None:
        lines = ["Conditions"]
        for s in ld.segments:
            name = (f"L{format_duration(s.light)} D{format_duration(s.dark)}" if s.mode == "LD"
                    else s.mode)
            lines.append(f"{name} from {g(s.start_hour)} h")
        ax.text(1.02, 0.62, "\n".join(lines), transform=ax.transAxes, va="top", ha="left",
                fontsize=7.5, color="#333333", linespacing=1.5)
    return hits


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #

# ---- example 1 ------------------------------------------------------------------------
# The peak and trough times of the 'Load example' data (hours after 0 h = 2026-10-05 10:15 CDT).
# Example: the samples are put into LD 12:12 (lights on 08:00) at 13:27 on Sun 4 Oct 2026;
# the light/dark schedule starts at 08:00 that day and 0 h of the data is 10:15 on 5 Oct.
#   from 4 Oct 08:00 : LD 12:12
#   from 10 Oct 08:00: LD 15:15 (T = 30 h)
#   from 16 Oct 14:00: LL (168 h), from the end of the last D
# Peak and trough values are hours after 0 h; troughs lie about half a cycle before the peaks.
EXAMPLE_PEAKS = (8.47, 32.75, 56.50, 80.31, 104.58, 128.26, 156.25, 187.62, 218.79, 249.09, 273.59, 298.62, 323.21, 347.92, 372.96, 397.81, 422.60)
EXAMPLE_TROUGHS = (20.48, 44.55, 68.51, 92.68, 116.69, 143.75, 172.13, 203.87, 234.09, 263.51, 287.85, 310.79, 335.77, 360.87, 385.51, 410.33)


EXAMPLE_TITLE = "Example Data"
# Example 1 as a time series: 396 pairs 'time(h) signal' written as one long string (split
# over many source lines), turned into rows by example_series_text().  The values are synthetic:
# an oscillation with damping whose peaks/troughs match EXAMPLE_PEAKS/EXAMPLE_TROUGHS within one
# sampling interval.
EXAMPLE_SERIES_DATA = (  # example bioluminescence record: time (h), signal; pairs
    "0.00 846 0.82 1116 1.65 1447 2.46 1794 3.29 2121 4.13 2392 4.98 2710 5.82 2921 6.65 3086 7.47 "
    "3196 8.29 3188 9.13 3172 9.93 3078 10.75 2952 11.61 2680 12.42 2419 13.29 2100 14.09 1859 14.95 "
    "1485 15.79 1160 16.61 867 17.47 669 18.29 443 19.12 326 19.97 291 20.79 221 21.65 239 22.45 398 "
    "23.30 568 24.11 769 24.96 1044 25.76 1266 26.60 1530 27.45 1807 28.25 2043 29.07 2281 29.91 2454 "
    "30.73 2628 31.57 2716 32.43 2782 33.25 2688 34.06 2646 34.90 2506 35.72 2323 36.55 2105 37.39 "
    "1878 38.24 1586 39.08 1289 39.93 1039 40.74 789 41.59 596 42.41 395 43.21 317 44.02 285 44.85 "
    "237 45.70 311 46.52 373 47.35 550 48.18 744 49.00 917 49.81 1123 50.66 1407 51.48 1600 52.33 "
    "1856 53.19 2030 54.00 2192 54.86 2302 55.70 2344 56.50 2395 57.37 2337 58.24 2284 59.06 2122 "
    "59.92 1929 60.72 1786 61.52 1544 62.35 1315 63.16 1107 63.98 882 64.78 711 65.64 503 66.44 386 "
    "67.25 285 68.10 275 68.94 270 69.77 325 70.63 410 71.44 528 72.27 722 73.09 874 73.92 1063 74.78 "
    "1300 75.61 1488 76.42 1652 77.29 1838 78.14 1928 79.00 2011 79.83 2085 80.66 2084 81.52 2027 "
    "82.35 1972 83.22 1795 84.07 1683 84.92 1470 85.74 1304 86.61 1103 87.46 912 88.27 781 89.10 584 "
    "89.94 471 90.76 379 91.57 305 92.39 264 93.26 253 94.10 349 94.96 392 95.80 543 96.66 687 97.48 "
    "850 98.34 1038 99.16 1157 100.02 1357 100.86 1506 101.67 1635 102.50 1700 103.32 1798 104.17 "
    "1786 105.00 1774 105.83 1743 106.67 1656 107.48 1580 108.29 1425 109.16 1310 110.00 1131 110.82 "
    "1012 111.69 820 112.55 671 113.42 522 114.25 435 115.08 316 115.88 273 116.74 280 117.54 303 "
    "118.40 352 119.22 411 120.03 512 120.84 696 121.66 816 122.51 1000 123.35 1102 124.18 1227 "
    "124.98 1406 125.78 1488 126.60 1545 127.44 1635 128.28 1610 129.11 1595 129.93 1584 130.77 1526 "
    "131.62 1442 132.47 1366 133.31 1288 134.16 1161 135.00 1058 135.84 944 136.71 825 137.56 704 "
    "138.36 603 139.22 533 140.08 435 140.88 379 141.75 311 142.58 312 143.44 307 144.31 295 145.17 "
    "322 146.02 368 146.85 485 147.72 528 148.54 672 149.37 765 150.21 895 151.03 994 151.87 1138 "
    "152.69 1253 153.55 1331 154.37 1393 155.24 1401 156.06 1410 156.88 1387 157.71 1433 158.57 1310 "
    "159.42 1318 160.28 1233 161.08 1163 161.90 1131 162.74 973 163.56 910 164.38 802 165.25 705 "
    "166.09 662 166.92 526 167.72 486 168.57 414 169.39 322 170.22 307 171.06 311 171.90 283 172.75 "
    "290 173.57 300 174.42 317 175.27 361 176.13 473 176.95 514 177.76 593 178.59 656 179.44 735 "
    "180.30 832 181.16 907 182.00 1001 182.87 1066 183.68 1129 184.54 1192 185.37 1253 186.21 1244 "
    "187.06 1289 187.87 1266 188.68 1260 189.55 1225 190.36 1167 191.23 1148 192.04 1086 192.88 1040 "
    "193.69 953 194.52 872 195.37 790 196.18 678 196.98 612 197.82 575 198.65 513 199.47 421 200.28 "
    "382 201.14 335 202.00 317 202.85 273 203.67 274 204.50 267 205.33 290 206.17 351 207.01 358 "
    "207.87 436 208.72 504 209.55 563 210.42 643 211.28 728 212.13 778 212.98 855 213.81 916 214.62 "
    "1012 215.46 1047 216.27 1077 217.09 1127 217.94 1139 218.77 1139 219.63 1124 220.44 1100 221.31 "
    "1060 222.15 1051 222.98 1003 223.83 897 224.66 855 225.51 774 226.36 710 227.22 613 228.06 544 "
    "228.91 509 229.75 409 230.62 378 231.44 333 232.28 306 233.09 293 233.95 272 234.82 272 235.66 "
    "323 236.48 322 237.32 362 238.14 412 238.97 490 239.77 530 240.61 590 241.42 659 242.22 709 "
    "243.07 780 243.88 840 244.75 880 245.56 966 246.37 1006 247.17 1045 247.97 1057 248.80 1007 "
    "249.65 1063 250.50 1040 251.33 1000 252.17 949 253.00 919 253.82 858 254.67 795 255.52 731 "
    "256.37 654 257.21 590 258.06 509 258.91 450 259.75 417 260.56 340 261.43 319 262.28 272 263.15 "
    "255 263.96 271 264.80 323 265.64 368 266.51 405 267.33 514 268.17 598 268.97 687 269.82 777 "
    "270.65 863 271.50 935 272.36 947 273.22 1036 274.06 983 274.89 991 275.70 947 276.50 911 277.31 "
    "888 278.15 820 278.98 715 279.79 699 280.66 594 281.51 565 282.35 490 283.20 433 284.02 415 "
    "284.88 347 285.74 296 286.60 257 287.46 258 288.33 288 289.15 277 290.01 360 290.83 407 291.68 "
    "439 292.48 531 293.35 608 294.19 688 295.02 770 295.84 831 296.70 915 297.51 927 298.37 950 "
    "299.18 920 299.98 894 300.80 870 301.61 865 302.44 776 303.25 687 304.12 617 304.97 598 305.81 "
    "512 306.65 416 307.48 420 308.33 316 309.15 284 309.98 285 310.80 275 311.67 274 312.54 308 "
    "313.35 353 314.20 396 315.02 438 315.85 505 316.71 588 317.51 617 318.35 701 319.16 747 319.99 "
    "818 320.85 863 321.69 885 322.55 927 323.41 919 324.24 923 325.07 861 325.92 852 326.76 766 "
    "327.58 742 328.44 641 329.31 601 330.14 551 330.96 483 331.82 455 332.64 353 333.47 304 334.28 "
    "285 335.08 266 335.92 251 336.77 269 337.62 279 338.48 329 339.30 379 340.13 461 340.98 513 "
    "341.85 557 342.72 638 343.52 719 344.39 775 345.25 789 346.08 842 346.95 885 347.81 851 348.61 "
    "857 349.42 864 350.24 840 351.09 813 351.90 782 352.71 695 353.56 622 354.41 557 355.24 496 "
    "356.05 454 356.91 393 357.71 350 358.58 310 359.40 279 360.25 254 361.07 258 361.93 250 362.78 "
    "332 363.58 339 364.43 368 365.30 410 366.15 516 367.00 548 367.86 620 368.69 704 369.55 738 "
    "370.40 810 371.26 839 372.08 828 372.94 863 373.76 854 374.62 833 375.45 783 376.28 754 377.10 "
    "693 377.93 655 378.74 579 379.58 500 380.40 490 381.23 388 382.09 380 382.91 344 383.72 284 "
    "384.55 281 385.35 263 386.18 236 387.03 311 387.87 322 388.69 349 389.49 416 390.32 474 391.14 "
    "524 391.98 586 392.84 641 393.66 676 394.52 760 395.35 785 396.15 809 396.98 831 397.84 870 "
    "398.65 811 399.48 806 400.33 730 401.15 756 401.98 709 402.79 660 403.60 576 404.41 510 405.24 "
    "482 406.08 403 406.88 371 407.70 339 408.55 297 409.42 264 410.29 280 411.15 262 411.98 292 "
    "412.79 340 413.61 371 414.47 394 415.33 474 416.16 523 417.01 579 417.82 630 418.64 694 419.46 "
    "758 420.33 786 421.17 792 421.97 819 422.83 812 423.70 825 424.57 779 425.42 745 426.27 698 "
    "427.08 677 427.89 589 428.69 528 429.56 511 430.37 439 431.17 347 "
)


# ---- example 2 ------------------------------------------------------------------------
# A synthetic record every 8 minutes with its own schedule (see example2_settings).  Only the
# signal values are stored; the times are generated: row i = start + 8 min * i, written in
# local clock time with the UTC offset (-0500 until daylight time ends, then -0600).
EXAMPLE2_START_UTC = "2026-10-28T19:37:00+0000"  # example 2: 0 h = 2026-10-28 14:37 CDT; one row every 8 minutes
EXAMPLE2_STEP_MIN = 8
EXAMPLE2_DST_END_UTC = "2026-11-01T07:00:00+0000"  # US Central: CDT (UTC-05:00) -> CST (UTC-06:00)
# 8-minute sampling: 101 taps would span only 13.5 h, too short for a 48-h cutoff
EXAMPLE2_ORDER = "301"                            # sinc filter order suited to 8-min sampling
# 3825 signal values separated by spaces (split over many source lines)
EXAMPLE2_DATA = (  # signal of each row
    "4579 4703 4839 5000 5145 5345 5535 5719 5924 6153 6357 6617 6868 7107 7394 7673 7965 8278 8564 "
    "8863 9193 9518 9873 10189 10544 10865 11244 11598 11949 12333 12698 13057 13429 13794 14178 "
    "14558 14927 15304 15670 16053 16407 16793 17162 17513 17867 18210 18587 18943 19283 19623 19937 "
    "20268 20606 20883 21205 21480 21780 22042 22327 22553 22820 23053 23279 23527 23721 23893 24058 "
    "24267 24405 24561 24724 24843 24951 25023 25127 25211 25244 25291 25326 25361 25403 25366 25366 "
    "25323 25289 25221 25118 25077 24950 24848 24724 24642 24478 24298 24125 23943 23752 23543 23354 "
    "23113 22879 22634 22349 22093 21853 21564 21254 20937 20662 20341 20008 19673 19345 19009 18659 "
    "18298 17926 17574 17229 16854 16482 16108 15732 15344 14977 14593 14195 13846 13461 13096 12715 "
    "12357 11978 11606 11234 10888 10521 10167 9834 9485 9168 8817 8487 8197 7901 7586 7301 7011 6728 "
    "6484 6231 5989 5747 5532 5314 5113 4931 4750 4577 4422 4274 4161 4028 3923 3830 3746 3673 3620 "
    "3578 3537 3538 3528 3531 3551 3588 3632 3695 3770 3863 3956 4051 4178 4309 4452 4617 4781 4964 "
    "5153 5346 5572 5781 6031 6252 6514 6779 7051 7325 7604 7901 8207 8498 8809 9114 9452 9790 10124 "
    "10454 10803 11156 11499 11858 12217 12574 12940 13294 13656 14032 14385 14746 15109 15455 15769 "
    "16153 16539 16846 17213 17545 17864 18186 18539 18825 19163 19459 19754 20060 20306 20585 20864 "
    "21126 21378 21591 21842 22054 22267 22452 22674 22827 22975 23175 23311 23435 23538 23663 23773 "
    "23812 23889 23913 24018 24043 24064 24059 24067 24062 24006 23989 23901 23825 23753 23680 23554 "
    "23455 23332 23206 23051 22886 22703 22513 22305 22092 21885 21661 21399 21181 20920 20673 20390 "
    "20095 19833 19508 19217 18898 18595 18255 17933 17589 17271 16946 16584 16229 15899 15531 15154 "
    "14794 14446 14087 13739 13358 13003 12639 12287 11926 11559 11201 10856 10517 10165 9807 9481 "
    "9147 8832 8499 8184 7886 7566 7283 7001 6721 6447 6182 5938 5693 5452 5237 5019 4814 4624 4454 "
    "4271 4110 3962 3830 3697 3590 3477 3385 3305 3239 3193 3146 3130 3111 3111 3112 3126 3163 3209 "
    "3270 3350 3419 3504 3610 3721 3863 3998 4139 4313 4480 4665 4862 5075 5290 5502 5729 5968 6218 "
    "6474 6761 7014 7310 7594 7893 8200 8495 8830 9151 9474 9778 10106 10427 10766 11125 11460 11809 "
    "12157 12511 12834 13195 13535 13891 14235 14585 14931 15257 15619 15916 16244 16576 16926 17226 "
    "17528 17821 18127 18426 18704 18992 19260 19572 19784 20029 20290 20497 20714 20933 21140 21313 "
    "21490 21674 21817 21980 22085 22235 22369 22460 22572 22638 22720 22766 22806 22838 22843 22884 "
    "22866 22840 22825 22786 22726 22670 22574 22483 22395 22315 22154 22037 21879 21697 21558 21368 "
    "21174 20977 20793 20562 20353 20101 19889 19622 19321 19081 18772 18534 18229 17933 17623 17309 "
    "16992 16667 16358 16009 15693 15344 15048 14672 14324 13988 13636 13273 12950 12606 12265 11883 "
    "11566 11196 10862 10528 10190 9861 9504 9198 8877 8547 8231 7922 7635 7321 7052 6762 6501 6214 "
    "5947 5721 5457 5245 5006 4797 4589 4397 4214 4027 3870 3719 3567 3442 3326 3209 3115 3029 2953 "
    "2892 2838 2795 2774 2754 2761 2757 2785 2801 2856 2912 2975 3051 3139 3236 3359 3487 3613 3753 "
    "3922 4084 4261 4456 4636 4847 5055 5291 5515 5760 6006 6264 6522 6813 7069 7354 7646 7938 8248 "
    "8548 8851 9161 9477 9816 10136 10448 10798 11123 11460 11809 12123 12454 12785 13140 13458 13790 "
    "14106 14443 14740 15096 15401 15719 16009 16305 16614 16923 17210 17526 17763 18056 18293 18550 "
    "18791 19043 19263 19491 19704 19873 20081 20255 20440 20605 20758 20885 21055 21182 21285 21374 "
    "21461 21506 21594 21689 21712 21742 21737 21776 21755 21755 21703 21690 21592 21554 21472 21415 "
    "21307 21206 21071 20972 20821 20689 20516 20340 20152 19967 19776 19544 19332 19121 18899 18628 "
    "18398 18135 17878 17627 17311 17006 16727 16432 16128 15817 15488 15211 14868 14544 14218 13910 "
    "13572 13251 12920 12584 12253 11889 11562 11234 10913 10576 10242 9919 9600 9258 8936 8632 8327 "
    "8018 7720 7429 7124 6844 6585 6310 6039 5791 5552 5294 5061 4840 4627 4417 4218 4047 3853 3694 "
    "3535 3389 3245 3115 3012 2902 2793 2716 2646 2592 2541 2515 2477 2464 2464 2472 2491 2511 2552 "
    "2613 2676 2758 2836 2938 3043 3168 3297 3424 3579 3743 3908 4093 4282 4473 4679 4891 5128 5370 "
    "5598 5834 6105 6346 6633 6890 7170 7471 7755 8033 8341 8640 8950 9232 9568 9879 10198 10506 "
    "10832 11146 11470 11804 12129 12426 12769 13085 13395 13713 14013 14327 14623 14930 15217 15513 "
    "15815 16087 16388 16643 16890 17134 17406 17679 17887 18135 18320 18563 18761 18959 19150 19343 "
    "19477 19653 19798 19915 20035 20179 20264 20367 20468 20517 20594 20655 20709 20722 20746 20765 "
    "20775 20719 20673 20689 20612 20560 20488 20408 20324 20221 20094 19985 19843 19707 19551 19386 "
    "19220 18996 18810 18621 18448 18219 18001 17743 17479 17260 17039 16762 16452 16212 15923 15624 "
    "15333 15053 14761 14448 14124 13827 13542 13203 12885 12589 12250 11941 11610 11284 10956 10652 "
    "10321 10010 9690 9379 9091 8747 8449 8146 7848 7575 7273 6995 6709 6445 6172 5925 5664 5408 5176 "
    "4947 4718 4513 4292 4100 3912 3735 3563 3400 3251 3116 2971 2859 2749 2649 2553 2484 2400 2349 "
    "2300 2261 2236 2223 2219 2224 2244 2279 2315 2374 2430 2505 2584 2688 2790 2906 3047 3179 3323 "
    "3478 3649 3820 3994 4187 4377 4583 4792 5014 5237 5460 5708 5935 6176 6440 6696 6952 7231 7489 "
    "7755 8040 8288 8592 8868 9159 9461 9733 10017 10318 10611 10877 11181 11472 11756 12035 12331 "
    "12602 12895 13169 13445 13705 13973 14230 14495 14729 15002 15238 15478 15690 15920 16142 16378 "
    "16584 16773 16965 17136 17332 17501 17671 17832 17962 18102 18225 18381 18468 18565 18654 18726 "
    "18823 18898 18987 18995 19008 19073 19068 19098 19078 19101 19089 19058 18993 18974 18915 18843 "
    "18778 18706 18592 18506 18392 18278 18180 18043 17899 17735 17579 17413 17268 17097 16893 16691 "
    "16512 16325 16105 15916 15674 15452 15229 15000 14749 14528 14274 14009 13785 13540 13268 13022 "
    "12763 12495 12234 11973 11700 11450 11177 10907 10624 10393 10118 9848 9616 9370 9110 8857 8602 "
    "8352 8109 7875 7629 7404 7177 6968 6739 6528 6321 6139 5919 5740 5552 5376 5213 5047 4899 4744 "
    "4604 4478 4352 4217 4124 4011 3921 3837 3735 3696 3620 3565 3518 3480 3455 3438 3415 3414 3407 "
    "3425 3450 3484 3523 3580 3626 3685 3753 3826 3909 3997 4112 4221 4334 4467 4574 4709 4849 5004 "
    "5153 5309 5477 5653 5838 6016 6198 6391 6577 6782 6983 7195 7397 7608 7822 8067 8268 8502 8713 "
    "8942 9175 9410 9647 9868 10106 10320 10554 10805 11015 11258 11470 11704 11939 12149 12378 12599 "
    "12803 13010 13235 13444 13632 13840 14010 14210 14380 14576 14737 14929 15091 15228 15365 15509 "
    "15658 15803 15915 16044 16120 16251 16344 16430 16557 16604 16675 16735 16785 16848 16887 16910 "
    "16937 16963 16975 16967 16978 16945 16950 16910 16895 16843 16788 16734 16683 16615 16534 16451 "
    "16326 16285 16155 16042 15934 15786 15672 15541 15391 15269 15097 14971 14787 14607 14450 14276 "
    "14088 13910 13738 13557 13337 13153 12957 12744 12540 12341 12141 11917 11715 11506 11290 11081 "
    "10863 10661 10438 10210 10010 9815 9585 9396 9177 8972 8757 8556 8366 8158 7965 7760 7573 7404 "
    "7232 7055 6887 6707 6547 6367 6217 6068 5936 5801 5670 5528 5416 5295 5177 5071 4979 4893 4805 "
    "4720 4649 4583 4536 4475 4419 4382 4344 4326 4310 4291 4278 4273 4289 4311 4325 4355 4406 4427 "
    "4495 4534 4599 4653 4742 4824 4905 4989 5091 5199 5307 5425 5524 5651 5791 5919 6038 6191 6348 "
    "6487 6637 6791 6968 7128 7291 7457 7622 7822 7980 8171 8358 8537 8736 8917 9094 9295 9456 9664 "
    "9828 10033 10224 10418 10607 10785 10967 11169 11340 11525 11698 11850 12043 12218 12378 12531 "
    "12712 12860 13005 13148 13290 13454 13580 13732 13853 13995 14104 14212 14304 14418 14521 14631 "
    "14704 14782 14830 14936 15001 15059 15120 15156 15204 15231 15270 15305 15316 15308 15339 15311 "
    "15313 15279 15292 15268 15227 15171 15138 15095 15056 14979 14910 14844 14738 14658 14576 14501 "
    "14389 14255 14197 14068 13936 13798 13694 13574 13402 13276 13161 12985 12848 12704 12570 12383 "
    "12238 12067 11909 11730 11556 11387 11224 11048 10885 10701 10525 10349 10190 10011 9829 9658 "
    "9493 9303 9112 8953 8797 8609 8461 8284 8129 7957 7791 7639 7502 7330 7202 7036 6916 6801 6652 "
    "6516 6395 6279 6147 6036 5945 5824 5747 5643 5555 5462 5388 5327 5255 5190 5135 5081 5042 4985 "
    "4960 4931 4905 4879 4876 4876 4866 4885 4887 4901 4923 4933 4985 5014 5052 5101 5145 5214 5273 "
    "5344 5411 5500 5570 5672 5766 5860 5959 6063 6174 6280 6395 6518 6644 6772 6894 7035 7165 7307 "
    "7442 7586 7715 7871 8033 8179 8332 8493 8642 8798 8967 9099 9258 9421 9557 9705 9878 10028 10182 "
    "10346 10506 10643 10814 10947 11107 11234 11386 11528 11657 11778 11913 12049 12188 12300 12417 "
    "12535 12630 12753 12864 12964 13058 13148 13225 13326 13399 13455 13534 13619 13664 13729 13774 "
    "13810 13853 13905 13941 13936 13982 14000 13987 14016 14025 13999 14011 13989 13970 13930 13915 "
    "13880 13838 13791 13756 13692 13622 13579 13488 13430 13344 13248 13167 13086 12976 12891 12802 "
    "12665 12586 12472 12341 12242 12129 11974 11860 11741 11606 11472 11318 11174 11078 10921 10763 "
    "10613 10485 10338 10204 10052 9901 9773 9605 9466 9327 9157 9008 8875 8717 8577 8454 8295 8162 "
    "8031 7873 7757 7616 7494 7364 7241 7119 7000 6893 6782 6667 6558 6459 6370 6258 6176 6081 5999 "
    "5921 5836 5761 5698 5643 5588 5532 5487 5437 5394 5366 5324 5304 5281 5265 5251 5231 5235 5241 "
    "5255 5255 5277 5307 5330 5348 5388 5433 5460 5524 5559 5628 5678 5741 5813 5887 5972 6043 6128 "
    "6221 6304 6388 6489 6594 6698 6802 6915 7020 7126 7253 7369 7481 7610 7733 7861 7992 8119 8239 "
    "8373 8492 8635 8762 8900 9033 9180 9296 9417 9544 9692 9835 9949 10089 10216 10333 10446 10582 "
    "10698 10811 10925 11037 11167 11256 11368 11478 11596 11667 11770 11863 11985 12056 12117 12211 "
    "12285 12369 12438 12483 12548 12618 12673 12705 12745 12808 12823 12840 12896 12936 12917 12950 "
    "12936 12968 12961 12939 12953 12955 12940 12911 12884 12860 12841 12779 12758 12704 12667 12607 "
    "12527 12488 12405 12343 12279 12179 12117 12039 11946 11859 11768 11696 11579 11488 11380 11269 "
    "11173 11061 10953 10821 10708 10601 10463 10356 10249 10144 10003 9896 9767 9624 9503 9376 9237 "
    "9123 8986 8858 8733 8610 8497 8379 8255 8128 8006 7889 7774 7674 7540 7422 7340 7225 7113 7007 "
    "6916 6810 6721 6631 6531 6446 6365 6282 6212 6147 6068 6003 5949 5885 5829 5767 5726 5691 5646 "
    "5609 5575 5552 5524 5512 5484 5490 5466 5463 5474 5472 5482 5501 5505 5518 5555 5584 5621 5649 "
    "5675 5726 5786 5848 5879 5943 6000 6066 6133 6207 6281 6361 6446 6506 6592 6693 6775 6865 6962 "
    "7061 7155 7257 7368 7461 7567 7675 7787 7899 8012 8133 8237 8340 8464 8587 8681 8802 8904 9013 "
    "9130 9259 9382 9479 9571 9683 9803 9910 10012 10112 10222 10318 10422 10516 10622 10725 10793 "
    "10895 10991 11069 11133 11218 11297 11380 11448 11518 11591 11666 11728 11822 11877 11937 12010 "
    "12045 12093 12121 12172 12210 12239 12263 12267 12286 12290 12300 12306 12302 12298 12261 12246 "
    "12220 12179 12124 12080 12053 12005 11938 11884 11804 11735 11646 11601 11478 11393 11305 11213 "
    "11097 10990 10878 10748 10650 10537 10421 10270 10141 10002 9888 9742 9597 9470 9328 9168 9022 "
    "8894 8738 8596 8444 8312 8178 8019 7867 7732 7588 7442 7288 7168 7030 6877 6773 6631 6507 6374 "
    "6270 6130 6025 5902 5809 5701 5602 5519 5420 5343 5246 5179 5114 5034 4977 4915 4871 4825 4799 "
    "4746 4738 4709 4694 4687 4679 4676 4701 4698 4719 4745 4768 4801 4855 4894 4953 5012 5087 5146 "
    "5216 5293 5386 5473 5575 5677 5789 5892 5998 6115 6237 6371 6492 6631 6771 6914 7055 7194 7337 "
    "7493 7645 7794 7942 8114 8258 8422 8581 8742 8893 9070 9219 9371 9541 9687 9850 10002 10160 "
    "10306 10462 10612 10738 10874 11031 11191 11283 11404 11556 11669 11783 11898 12019 12093 12202 "
    "12288 12367 12442 12547 12614 12679 12740 12803 12841 12903 12915 12954 12975 12990 12998 13013 "
    "13019 12999 12989 12967 12945 12901 12854 12832 12764 12710 12649 12579 12494 12435 12339 12221 "
    "12141 12062 11926 11813 11691 11590 11460 11311 11196 11039 10888 10740 10588 10436 10296 10124 "
    "9958 9805 9627 9456 9289 9115 8940 8762 8594 8430 8247 8066 7889 7729 7559 7380 7208 7042 6870 "
    "6717 6539 6368 6210 6068 5908 5776 5616 5474 5338 5197 5086 4946 4835 4714 4607 4499 4414 4312 "
    "4223 4142 4075 3997 3934 3879 3827 3787 3755 3709 3695 3662 3666 3652 3648 3663 3692 3694 3733 "
    "3773 3805 3864 3920 3974 4044 4114 4190 4284 4379 4479 4578 4678 4794 4907 5046 5176 5315 5452 "
    "5579 5729 5887 6042 6206 6360 6525 6690 6853 7031 7218 7381 7566 7737 7928 8100 8285 8463 8635 "
    "8831 8996 9177 9370 9550 9722 9890 10066 10246 10412 10578 10737 10898 11058 11200 11366 11512 "
    "11654 11766 11902 12030 12147 12292 12390 12476 12602 12697 12769 12869 12942 13028 13084 13135 "
    "13192 13244 13269 13303 13324 13351 13353 13332 13351 13320 13297 13287 13255 13224 13164 13118 "
    "13052 13008 12931 12838 12753 12685 12583 12445 12356 12235 12120 12001 11850 11721 11605 11448 "
    "11289 11144 10968 10828 10649 10497 10309 10135 9967 9788 9597 9413 9219 9040 8843 8670 8472 "
    "8272 8080 7897 7698 7519 7329 7136 6942 6771 6580 6398 6227 6046 5864 5688 5526 5376 5211 5046 "
    "4910 4753 4619 4474 4340 4220 4091 3980 3868 3753 3666 3576 3493 3415 3332 3262 3210 3152 3109 "
    "3064 3031 3023 2998 2993 2985 2986 2999 3014 3036 3081 3113 3149 3201 3269 3318 3412 3479 3574 "
    "3665 3763 3877 3963 4095 4211 4343 4473 4622 4762 4909 5054 5208 5377 5541 5702 5878 6056 6235 "
    "6416 6589 6777 6948 7138 7348 7534 7725 7920 8097 8301 8494 8697 8884 9078 9273 9458 9642 9834 "
    "10015 10201 10365 10545 10726 10884 11038 11211 11368 11523 11665 11800 11965 12080 12219 12339 "
    "12450 12554 12659 12773 12861 12907 12996 13096 13153 13237 13265 13321 13351 13382 13404 13418 "
    "13442 13423 13438 13421 13402 13361 13333 13301 13242 13183 13135 13038 12998 12901 12836 12727 "
    "12608 12517 12409 12272 12147 12013 11865 11749 11624 11440 11281 11119 10966 10801 10603 10456 "
    "10275 10100 9892 9707 9527 9319 9134 8937 8739 8534 8328 8131 7953 7760 7555 7347 7152 6961 6764 "
    "6569 6388 6192 5994 5817 5632 5455 5284 5104 4923 4788 4613 4458 4322 4183 4027 3902 3770 3655 "
    "3530 3414 3311 3221 3121 3027 2966 2885 2822 2759 2712 2668 2632 2601 2585 2550 2560 2562 2552 "
    "2576 2596 2624 2657 2697 2747 2816 2873 2950 3027 3114 3188 3293 3396 3507 3622 3735 3870 4011 "
    "4146 4285 4437 4578 4743 4922 5073 5251 5411 5591 5762 5956 6143 6336 6530 6710 6901 7100 7302 "
    "7484 7692 7906 8087 8290 8477 8690 8873 9078 9271 9460 9646 9841 10038 10211 10393 10569 10743 "
    "10908 11071 11230 11406 11541 11673 11835 11967 12112 12232 12343 12451 12563 12658 12759 12860 "
    "12929 13001 13076 13121 13183 13232 13262 13318 13303 13350 13361 13377 13356 13369 13312 13300 "
    "13285 13243 13157 13147 13052 12993 12903 12847 12767 12660 12549 12447 12339 12216 12080 11966 "
    "11807 11672 11494 11376 11221 11039 10885 10726 10551 10345 10189 9998 9815 9620 9429 9241 9050 "
    "8832 8640 8441 8241 8040 7839 7626 7434 7238 7026 6832 6635 6431 6241 6057 5871 5681 5491 5312 "
    "5140 4951 4782 4616 4445 4306 4148 3990 3857 3713 3589 3465 3322 3215 3109 3008 2922 2822 2732 "
    "2658 2596 2531 2477 2429 2395 2353 2335 2309 2291 2294 2285 2295 2321 2333 2370 2412 2464 2528 "
    "2569 2643 2717 2801 2881 2970 3079 3187 3307 3412 3539 3675 3803 3951 4109 4254 4412 4568 4722 "
    "4889 5067 5239 5427 5613 5795 5970 6172 6354 6562 6745 6945 7150 7334 7545 7752 7970 8141 8350 "
    "8547 8746 8931 9124 9338 9519 9686 9886 10053 10229 10412 10596 10761 10921 11085 11216 11394 "
    "11521 11680 11814 11946 12077 12210 12282 12402 12510 12594 12692 12769 12831 12932 12964 13029 "
    "13058 13111 13142 13182 13181 13198 13198 13177 13179 13142 13130 13086 13065 12996 12945 12885 "
    "12795 12736 12663 12582 12461 12371 12258 12138 12010 11895 11765 11624 11481 11343 11191 11024 "
    "10874 10715 10532 10372 10194 9995 9815 9629 9444 9236 9062 8856 8656 8473 8272 8065 7870 7661 "
    "7444 7265 7046 6865 6664 6457 6269 6067 5878 5687 5502 5325 5147 4972 4793 4628 4453 4298 4137 "
    "3992 3843 3696 3558 3434 3301 3175 3065 2944 2860 2756 2670 2594 2518 2445 2381 2319 2279 2231 "
    "2206 2186 2146 2150 2143 2147 2155 2168 2193 2218 2255 2314 2362 2419 2489 2549 2640 2720 2816 "
    "2921 3032 3142 3259 3373 3512 3633 3779 3936 4069 4244 4379 4559 4715 4897 5067 5242 5411 5609 "
    "5780 5970 6168 6368 6559 6752 6950 7148 7348 7546 7740 7933 8126 8332 8546 8724 8904 9105 9301 "
    "9479 9668 9848 10021 10181 10367 10538 10696 10859 11008 11162 11291 11418 11562 11713 11837 "
    "11958 12062 12155 12259 12349 12442 12523 12598 12660 12728 12786 12840 12856 12920 12920 12949 "
    "12952 12961 12958 12937 12921 12869 12830 12802 12764 12688 12652 12583 12507 12447 12364 12278 "
    "12199 12082 11977 11868 11756 11658 11546 11431 11305 11180 11033 10905 10766 10618 10469 10324 "
    "10172 10017 9859 9694 9537 9375 9209 9056 8878 8715 8536 8378 8202 8038 7868 7701 7525 7352 7190 "
    "7018 6849 6669 6522 6358 6186 6041 5871 5721 5575 5423 5274 5125 4990 4850 4724 4576 4452 4339 "
    "4213 4094 3984 3875 3777 3669 3580 3497 3419 3326 3270 3192 3124 3062 3006 2958 2911 2876 2837 "
    "2816 2791 2765 2762 2754 2744 2737 2753 2764 2794 2807 2835 2863 2915 2958 3005 3045 3110 3176 "
    "3249 3317 3408 3477 3562 3642 3740 3826 3932 4041 4155 4248 4385 4482 4597 4723 4860 4973 5117 "
    "5245 5384 5524 5660 5781 5926 6084 6213 6361 6509 6647 6793 6960 7094 7246 7381 7534 7664 7822 "
    "7951 8098 8245 8377 8514 8652 8789 8920 9052 9187 9311 9447 9556 9683 9792 9901 10011 10125 "
    "10226 10313 10404 10514 10585 10680 10768 10840 10906 10981 11022 11071 11168 11205 11239 11295 "
    "11327 11353 11379 11409 11442 11455 11443 11473 11462 11449 11444 11438 11428 11395 11371 11333 "
    "11323 11269 11218 11166 11115 11089 11013 10935 10865 10813 10751 10655 10571 10481 10405 10310 "
    "10221 10107 10026 9908 9799 9681 9574 9470 9345 9220 9103 8986 8868 8743 8621 8488 8362 8262 "
    "8119 7990 7847 7720 7599 7450 7334 7207 7061 6956 6818 6694 6582 6442 6326 6209 6084 5960 5854 "
    "5736 5622 5514 5398 5301 5193 5098 5006 4912 4811 4732 4640 4560 4491 4407 4321 4274 4188 4142 "
    "4089 4016 3972 3934 3885 3854 3815 3786 3760 3740 3717 3701 3690 3684 3696 3697 3695 3696 3718 "
    "3737 3758 3781 3805 3848 3886 3924 3974 4011 4065 4112 4167 4244 4305 4379 4443 4524 4604 4667 "
    "4761 4848 4919 5020 5116 5214 5306 5402 5496 5598 5715 5816 5907 6026 6152 6248 6359 6469 6588 "
    "6684 6799 6922 7021 7136 7252 7372 7468 7570 7696 7802 7926 8032 8135 8230 8359 8444 8552 8636 "
    "8746 8839 8939 9010 9096 9205 9265 9374 9451 9521 9587 9660 9744 9802 9860 9912 9981 10035 10077 "
    "10137 10178 10201 10251 10280 10314 10342 10352 10376 10378 10395 10412 10405 10424 10410 10405 "
    "10381 10372 10375 10349 10325 10296 10270 10240 10201 10159 10092 10051 10017 9951 9891 9849 "
    "9800 9706 9628 9574 9506 9416 9358 9264 9180 9120 9024 8916 8843 8774 8666 8580 8483 8380 8289 "
    "8187 8081 7981 7898 7792 7687 7605 7482 7377 7289 7191 7077 6965 6883 6772 6687 6575 6470 6386 "
    "6282 6204 6102 6005 5908 5843 5737 5657 5571 5488 5428 5344 5255 5188 5131 5047 4990 4920 4870 "
    "4812 4752 4707 4658 4610 4575 4527 4494 4457 4422 4395 4376 4357 4338 4325 4317 4296 4284 4291 "
    "4297 4295 4301 4330 4325 4358 4362 4410 4414 4436 4478 4500 4536 4590 4632 4679 4726 4784 4834 "
    "4886 4941 5018 5081 5139 5203 5271 5346 5418 5493 5564 5650 5728 5820 5883 5981 6064 6150 6233 "
    "6319 6427 6497 6584 6663 6762 6870 6952 7031 7141 7215 7309 7388 7506 7574 7640 7758 7826 7917 "
    "7989 8091 8167 8253 8315 8404 8481 8545 8627 8687 8756 8824 8888 8951 9019 9061 9118 9180 9238 "
    "9265 9328 9372 9403 9430 9484 9500 9531 9582 9573 9601 9621 9636 9647 9662 9669 9654 9649 9672 "
    "9661 9662 9651 9647 9625 9585 9581 9540 9518 9490 9451 9431 9373 9336 9304 9255 9203 9155 9105 "
    "9059 8992 8928 8867 8811 8741 8684 8609 8550 8465 8408 8342 8244 8176 8081 8020 7937 7854 7787 "
    "7713 7644 7547 7456 7371 7280 7195 7141 7028 6959 6874 6804 6717 6628 6547 6472 6385 6319 6228 "
    "6152 6084 6013 5943 5866 5802 5712 5679 5601 5528 5469 5437 5349 5295 5245 5202 5155 5113 5061 "
    "5027 4984 4946 4901 4875 4843 4821 4784 4765 4746 4731 4718 4695 4696 4686 4682 4674 4673 4684 "
    "4685 4691 4706 4714 4739 4759 4782 4802 4832 4851 4893 4916 4951 4978 5036 5075 5134 5155 5210 "
    "5260 5332 5378 5435 5476 5554 5598 5667 5742 5791 5861 5916 5995 6070 6142 6205 6273 6341 6428 "
    "6497 6570 6633 6723 6795 6865 6945 7006 7085 7170 7240 7304 7380 7469 7537 7598 7674 7751 7817 "
    "7868 7932 8002 8066 8136 8192 8253 8320 8379 8430 8465 8533 8589 8604 8681 8722 8743 8795 8838 "
    "8875 8892 8926 8958 8983 8996 9040 9058 9065 9077 9097 9102 9116 9111 9124 9116 9119 9118 9113 "
    "9095 9100 9081 9049 9068 9024 8997 8978 8957 8928 8886 8847 8835 8764 8742 8698 8652 8605 8574 "
    "8509 8463 8417 8360 8312 8243 8184 8124 8086 8013 7953 7873 7812 7742 7676 7607 7548 7480 7413 "
    "7341 7271 7220 7139 7047 6992 6926 6860 6788 6719 6646 6580 6501 6435 6388 6297 6217 6173 6123 "
    "6053 6003 5946 5892 5815 5759 5705 5665 5599 5546 5500 5464 5420 5364 5325 5298 5246 5218 5179 "
    "5159 5121 5089 5061 5037 5010 4990 4974 4965 4946 4948 4929 4924 4930 4916 4935 4929 4931 4932 "
    "4946 4958 4968 4982 5003 5031 5038 5073 5102 5123 5159 5198 5230 5261 5290 5341 5360 5410 5475 "
    "5507 5548 5596 5661 5691 5761 5819 5874 5916 5983 6050 6093 6160 6217 6280 6331 6405 6449 6526 "
    "6596 6655 6721 6789 6845 6918 6980 7055 7089 7175 7233 7302 "
)


def example2_series_text() -> str:
    """Example 2 as ISO 8601 rows; the UTC offset changes from -0500 to -0600 when
    daylight saving time ends on 1 Nov 2026."""
    # parse the fixed start and the end of daylight time
    start = datetime.strptime(EXAMPLE2_START_UTC, "%Y-%m-%dT%H:%M:%S%z")
    dst_end = datetime.strptime(EXAMPLE2_DST_END_UTC, "%Y-%m-%dT%H:%M:%S%z")
    rows = []
    for i, v in enumerate(EXAMPLE2_DATA.split()):
        # time of row i
        utc = start + timedelta(minutes=EXAMPLE2_STEP_MIN * i)
        # the offset that the wall clock in Chicago had at that moment
        local = utc.astimezone(timezone(timedelta(hours=-5 if utc < dst_end else -6)))
        # ISO 8601 with offset, e.g. 2026-10-28T14:37:00-0500, a tab, the signal
        rows.append(f"{local:%Y-%m-%dT%H:%M:%S%z}\t{v}")
    return "\n".join(rows)


# Settings of example 2: 0 h = 2026-10-28 14:37; the conditions follow each other at the end
# of a cycle (5 x 24 h = 120 h, 6 x 23 h = 138 h).  Starts after 1 Nov are in CST (UTC-6).
def example2_settings() -> dict:
    """Clock time and light/dark schedule of example 2: LD 12:12 for 5 days, LL for 5.5 days,
    LD 11.5:11.5 (T = 23 h, dark first) for 6 days, DD for 5 days."""
    # the unused condition cards
    blank = {"mode": "LD", "L": "12:00", "D": "12:00", "start": "", "phase": "Light"}
    return {
        "t0": "2026-10-28 14:37", "tz": DEFAULT_TIME_ZONE, "peaks": "", "troughs": "",
        "show_ld": True, "extend_before": False, "n_changes": 3,
        "cycles": [{"mode": "LD", "L": "12:00", "D": "12:00", "start": "2026-10-28 14:37", "phase": "Light"},
                   {"mode": "LL", "L": "12:00", "D": "12:00", "start": "2026-11-02 13:37", "phase": "Light"},
                   {"mode": "LD", "L": "11:30", "D": "11:30", "start": "2026-11-08 01:37", "phase": "Dark"},
                   {"mode": "DD", "L": "12:00", "D": "12:00", "start": "2026-11-13 19:37", "phase": "Light"}]
                  + [dict(blank) for _ in range(MAX_CHANGES - 3)],
        "placed": "2026-10-28 13:50",
        "origin": "lights_on", "origin_time": "", "period": DEFAULT_PERIOD, "rows_auto": True,
        "title": "Example 2", "sel_peaks": [], "sel_troughs": [], "input_mode": "series",
    }


# the stored pairs: even positions = time (h), odd positions = signal
def example_series_text() -> str:
    """Example 1 as text: EXAMPLE_SERIES_DATA holds 'time value' pairs; one tab-separated row per pair."""
    v = EXAMPLE_SERIES_DATA.split()
    return "\n".join(f"{v[i]}\t{v[i + 1]}" for i in range(0, len(v) - 1, 2))



# Settings of example 1 (the original example of the typed-times mode).  'input_mode' is
# 'times' here; App.__init__ switches to the time-series input at start-up.
def example_settings() -> dict:
    """Data and conditions of the example (display options are not included)."""
    return {
        "t0": "2026-10-05 10:15", "tz": DEFAULT_TIME_ZONE,
        # the typed lists: one value per line with two decimals
        "peaks": "\n".join(f"{v:.2f}" for v in EXAMPLE_PEAKS),
        "troughs": "\n".join(f"{v:.2f}" for v in EXAMPLE_TROUGHS),
        "show_ld": True, "extend_before": False, "n_changes": 2,
        # LD 12:12 from 4 Oct 08:00, LD 15:15 from 10 Oct 08:00, LL from 16 Oct 14:00, three unused cards
        "cycles": [{"mode": "LD", "L": "12:00", "D": "12:00", "start": "2026-10-04 08:00", "phase": "Light"},
                   {"mode": "LD", "L": "15:00", "D": "15:00", "start": "2026-10-10 08:00", "phase": "Light"},
                   {"mode": "LL", "L": "12:00", "D": "12:00", "start": "2026-10-16 14:00", "phase": "Light"}]
                  + [{"mode": "LD", "L": "12:00", "D": "12:00", "start": "", "phase": "Light"}
                     for _ in range(MAX_CHANGES - 2)],
        "placed": "2026-10-04 13:27",
        "origin": "lights_on", "origin_time": "", "period": DEFAULT_PERIOD, "rows_auto": True,
        "title": EXAMPLE_TITLE,
        # all example points selected for the phase analysis
        "sel_peaks": list(EXAMPLE_PEAKS), "sel_troughs": list(EXAMPLE_TROUGHS),
        "input_mode": "times",
    }


def default_settings() -> dict:
    """All settings with their defaults: the example data plus every display option.  The keys are
    the same as in the web version, so settings files can be exchanged.
    """
    return {
        # start from the example and add every display option
        **example_settings(),
        # double plot, rows labelled by number
        "plot": "double", "rowlab": "number",
        "show_values": False, "link_peak": False, "link_trough": False,
        "rows_auto": True, "row_min": 0, "row_max": 5,
        # optional labels and marks
        "label_onsets": False, "label_row_starts": False, "mark_times": True, "mark_changes": True,
        # x-axis ticks
        "x_major": X_MAJOR_DEFAULT, "x_minor": X_MINOR_CHOICES[0],
        # band colours
        "light_color": LIGHT_COLORS[0][1], "dark_color": DARK_COLORS[0][1],
        # phase analysis options
        "phase_ref": "zt0_prev", "draw_fit": True, "drag_mode": "select", "sel_target": "both",
        # time-series input and its drawing options
        "series": "", "ts_edits": empty_edits(), **TS_DEFAULTS, **TS_DRAW_DEFAULTS,
    }


class TimeField:
    """Length input 'hh:mm' (00:00-99:59): typed, changed with the Up/Down keys (hour or
    minute, depending on the cursor position), or picked with the mouse from a
    wheel-style drop-down (clock button, Alt+Down or F4): an hour and a minute column
    that wrap around, scrolled with the mouse wheel, dragged, or clicked; the value in
    the grey band is the selected one."""

    ROW_H = 26                   # height of one row of the wheel (px)
    VISIBLE = 5                  # rows shown: 2 above, the selected one, 2 below
    COL_W = 46                   # width of one column (px)
    BAND = "#ececec"
    _active = None               # the TimeField whose picker is open
    _wheel_bound = False
    INK = (0x22, 0x22, 0x22)     # colour of the selected value
    FADE = (0xd2, 0xd2, 0xd2)    # colour of the farthest values

    # Create the field.  Parameters: parent widget; var = the StringVar holding 'hh:mm'; hours =
    # number of hour values (100 -> 00..99); width = entry width in characters; min_hour = lowest
    # hour; max_minutes/min_minutes = limits in minutes; default = value used when the text is
    # invalid; button = show the clock button (otherwise a click on the field opens the wheels).
    def __init__(self, parent, var, hours: int = 100, width: int = 6, min_hour: int = 0,
                 max_minutes=None, default=(12, 0), min_minutes=None, button: bool = True) -> None:
        """hours: the hour column runs from min_hour to hours - 1 (and wraps around);
        max_minutes / min_minutes: optional limits of the value in minutes
        (e.g. Period T: 0:01 - 240:00)."""
        self.var = var
        self.hours = int(hours)
        self.min_hour = int(min_hour)
        self.max_minutes = max_minutes
        self.min_minutes = min_minutes
        self.default = default
        # the field = a frame with the entry and (optionally) the clock button
        self.frame = ttk.Frame(parent)
        self.entry = ttk.Entry(self.frame, textvariable=var, width=width, justify="center")
        self.entry.pack(side="left")
        # U+25F7 = a clock symbol
        self.button = ttk.Button(self.frame, text="\u25f7", width=3, command=self.toggle)
        if button:
            self.button.pack(side="left", padx=(2, 0))
        else:                                   # no button: a click on the field opens the wheels
            self.entry.configure(cursor="hand2")
            self.entry.bind("<ButtonRelease-1>", lambda _e: None if self._popup is not None else self.open(), add="+")
        # state of the pop-up: its frame, its canvas, the current (animated) and target wheel
        # positions, the animation timer, the drag in progress, and the column for keyboard steps
        self._popup = None
        self._canvas = None
        self._pos = {"hour": 0.0, "minute": 0.0}
        self._target = {"hour": 0, "minute": 0}
        self._anim = None
        self._drag = None
        self._root_bound = False
        self._key_key = "hour"
        # keyboard: Up/Down step the value; Alt+Down or F4 open the wheels; leaving the field or
        # pressing Return rewrites it as hh:mm
        self.entry.bind("<Up>", lambda _e: self._step(+1))
        self.entry.bind("<Down>", lambda _e: self._step(-1))
        self.entry.bind("<Alt-Down>", lambda _e: (self.open(), "break")[1])
        self.entry.bind("<F4>", lambda _e: (self.open(), "break")[1])
        self.entry.bind("<FocusOut>", lambda _e: self._normalise())
        self.entry.bind("<Return>", lambda _e: self._normalise())

    # --- layout / state ---
    def grid(self, **kwargs) -> None:
        """Place the field with grid (the field is a frame with an entry and a button)."""
        self.frame.grid(**kwargs)

    def grid_remove(self) -> None:
        """Hide the field (closing its wheel pop-up first)."""
        self.close()
        self.frame.grid_remove()

    def pack(self, **kwargs) -> None:
        """Place the field with pack."""
        self.frame.pack(**kwargs)

    def state(self, spec) -> None:
        """Enable/disable the entry and the button, like ttk's state()."""
        for widget in (self.entry, self.button):
            widget.state(spec)
        if "disabled" in spec:
            self.close()

    # --- value ---
    def _value(self):
        """Current (hour, minute) if the text is a valid hh:mm in range, else None."""
        # accept 'hh:mm', 'hhmm' or 'h:mm' with optional spaces
        match = re.fullmatch(r"\s*(\d{1,3})\s*:?\s*(\d{2})\s*", str(self.var.get()))
        if not match:
            return None
        hour, minute = int(match.group(1)), int(match.group(2))
        # check the ranges
        ok = self.min_hour <= hour < self.hours and minute < 60
        if ok and self.max_minutes is not None and hour * 60 + minute > self.max_minutes:
            ok = False
        if ok and self.min_minutes is not None and hour * 60 + minute < self.min_minutes:
            ok = False
        return (hour, minute) if ok else None

    def _set(self, hour: int, minute: int) -> None:
        """Write hour:minute into the field, wrapping hours and clamping to the allowed minimum/maximum."""
        # wrap the hour into the allowed range (the wheel is circular)
        hour = self.min_hour + (hour - self.min_hour) % (self.hours - self.min_hour)
        minute %= 60
        # clamp to the maximum, then the minimum, in minutes
        if self.max_minutes is not None and hour * 60 + minute > self.max_minutes:
            minute = max(0, self.max_minutes - hour * 60)
        if self.min_minutes is not None and hour * 60 + minute < self.min_minutes:
            minute = min(59, self.min_minutes - hour * 60)
        text = f"{hour:02d}:{minute:02d}"
        # only write when the text changes (avoids needless redraws)
        if str(self.var.get()) != text:
            self.var.set(text)

    def _normalise(self) -> None:
        """Rewrite the typed value in the canonical hh:mm form."""
        value = self._value()
        if value is not None:
            self._set(*value)

    def _step(self, delta: int) -> str:
        """Arrow keys in the entry: step the hours or the minutes, depending on the cursor position."""
        if self.entry.instate(["disabled"]):
            return "break"
        # current value (or the default if the text is invalid)
        hour, minute = self._value() or self.default
        # the cursor position decides which part is stepped
        colon = str(self.var.get()).find(":")
        on_minutes = colon >= 0 and int(self.entry.index("insert")) > colon
        if on_minutes:
            minute = (minute + delta) % 60
        else:
            hour = self.min_hour + (hour - self.min_hour + delta) % (self.hours - self.min_hour)
        self._set(hour, minute)
        colon = str(self.var.get()).find(":")
        # select the changed part again so repeated key presses keep working on it
        start, end = (colon + 1, colon + 3) if on_minutes else (0, colon)
        self.entry.icursor(start)
        self.entry.selection_range(start, end)
        self._sync_wheels()
        return "break"

    # --- drop-down ---
    def toggle(self) -> None:
        """Open or close the wheel pop-up."""
        if self._popup is not None:
            self.close()
        else:
            self.open()

    def close(self) -> None:
        """Close the pop-up and stop its animation and global bindings."""
        # stop the animation timer, destroy the pop-up and reset the state
        if self._popup is not None:
            if self._anim is not None:
                with contextlib.suppress(tk.TclError):
                    self._popup.after_cancel(self._anim)
                self._anim = None
            with contextlib.suppress(tk.TclError):
                self._popup.destroy()
            self._popup = None
            self._canvas = None
            if TimeField._active is self:
                TimeField._active = None
            # tidy the text
            self._normalise()

    def open(self) -> None:
        """Show the wheels just below the field (a frame placed inside the main window:
        borderless pop-up windows do not reliably get mouse/wheel events everywhere)."""
        # already open, or disabled
        if self._popup is not None or self.button.instate(["disabled"]):
            return
        # only one pop-up at a time
        if TimeField._active is not None and TimeField._active is not self:
            TimeField._active.close()
        if self._value() is None:
            self._set(*self.default)
        # the pop-up is a frame placed inside the top-level window
        top = self.frame.winfo_toplevel()
        # a click anywhere else closes it (bound once per window)
        if not self._root_bound:
            top.bind("<Button-1>", self._on_outside_click, add="+")
            self._root_bound = True
        # the mouse wheel is captured globally while a pop-up is open (bound once for the class)
        if not TimeField._wheel_bound:
            top.bind_all("<MouseWheel>", TimeField._global_wheel, add="+")
            top.bind_all("<Button-4>", lambda e: TimeField._global_wheel(e, -1), add="+")
            top.bind_all("<Button-5>", lambda e: TimeField._global_wheel(e, +1), add="+")
            TimeField._wheel_bound = True

        # size of the canvas: two columns, VISIBLE rows
        width, height = 2 * self.COL_W + 16, self.VISIBLE * self.ROW_H + 8
        popup = tk.Frame(top, background="#c8c8c8", padx=1, pady=1)
        canvas = tk.Canvas(popup, width=width, height=height, background="white",
                           highlightthickness=0, borderwidth=0, cursor="hand2")
        canvas.pack()
        self._popup, self._canvas = popup, canvas
        TimeField._active = self

        # position below the entry (or above it if there is no room), inside the window
        top.update_idletasks()
        x = self.entry.winfo_rootx() - top.winfo_rootx()
        y = self.entry.winfo_rooty() - top.winfo_rooty() + self.entry.winfo_height() + 2
        if y + height + 2 > top.winfo_height():
            y = self.entry.winfo_rooty() - top.winfo_rooty() - height - 4
        x = max(0, min(x, top.winfo_width() - width - 2))
        popup.place(x=x, y=max(0, y))
        popup.lift()

        # start the wheels at the current value
        hour, minute = self._value()
        self._pos = {"hour": float(hour - self.min_hour), "minute": float(minute)}
        self._target = {"hour": hour - self.min_hour, "minute": minute}
        # mouse: wheel, click, drag; keyboard: Esc/Return close, arrows step/choose the column
        canvas.bind("<MouseWheel>", self._on_wheel)
        canvas.bind("<Button-4>", lambda e: self._on_wheel(e, -1))
        canvas.bind("<Button-5>", lambda e: self._on_wheel(e, +1))
        canvas.bind("<ButtonPress-1>", self._on_press)
        canvas.bind("<B1-Motion>", self._on_drag)
        canvas.bind("<ButtonRelease-1>", self._on_release)
        canvas.bind("<Escape>", lambda _e: self.close())
        canvas.bind("<Return>", lambda _e: self.close())
        canvas.bind("<Up>", lambda _e: self._key_step(-1))
        canvas.bind("<Down>", lambda _e: self._key_step(+1))
        canvas.bind("<Left>", lambda _e: self._key_column("hour"))
        canvas.bind("<Right>", lambda _e: self._key_column("minute"))
        self._key_key = "hour"
        self._draw()
        canvas.focus_set()

    def _on_outside_click(self, event) -> None:
        """Close the pop-up when the user clicks anywhere else."""
        if self._popup is None:
            return
        widget = str(getattr(event, "widget", ""))
        # clicks on the field itself or inside the pop-up do not close it
        if widget in (str(self.entry), str(self.button)) or widget.startswith(str(self._popup)):
            return
        self.close()

    @staticmethod
    def _global_wheel(event, direction: int = 0):
        """Mouse wheel anywhere while a pop-up is open: forward it to the wheel column under the pointer."""
        field_ = TimeField._active
        if field_ is None or field_._canvas is None:
            return None
        canvas = field_._canvas
        try:
            # only react when the pointer is over this pop-up
            px, py = canvas.winfo_pointerxy()
            over = canvas.winfo_containing(px, py)
        except (tk.TclError, KeyError):
            return None
        if over is None or str(over) != str(canvas):
            return None
        # events on the canvas itself are handled by its own binding
        if str(getattr(event, "widget", "")) == str(canvas):
            return "break"

        class _At:
            """Minimal event object with the pointer position relative to the pop-up canvas."""
            x = px - canvas.winfo_rootx()
            delta = getattr(event, "delta", 0)
        return field_._on_wheel(_At, direction)

    def _key_column(self, key: str) -> str:
        """Up/Down keys in the pop-up act on this column ('hour' or 'minute')."""
        self._key_key = key
        return "break"

    def _key_step(self, delta: int) -> str:
        """Move the active column one step with the keyboard."""
        self._move_to(self._key_key, self._target[self._key_key] + delta)
        return "break"

    # --- the wheels ---
    def _column_at(self, x: float) -> str:
        """Which wheel column ('hour' or 'minute') is at x (pixels) in the pop-up."""
        return "hour" if x < 8 + self.COL_W else "minute"

    def _count(self, key: str) -> int:
        """Number of values on a wheel (hours in the allowed range, or 60 minutes)."""
        return self.hours - self.min_hour if key == "hour" else 60

    def _draw(self) -> None:
        """Redraw both wheels: the values around the current position, faded towards the edges, with the selected value in the grey band."""
        canvas = self._canvas
        if canvas is None:
            return
        canvas.delete("all")
        width = 2 * self.COL_W + 16
        # vertical centre of the canvas = position of the selected value
        mid = 4 + self.VISIBLE * self.ROW_H / 2
        # the grey band behind the selected value
        canvas.create_rectangle(4, mid - self.ROW_H / 2, width - 4, mid + self.ROW_H / 2,
                                fill=self.BAND, outline=self.BAND)
        # how many rows fit above/below the centre
        half = self.VISIBLE / 2 + 0.5
        for column, key in enumerate(("hour", "minute")):
            # number of values on this wheel and its (fractional) position
            count, pos = self._count(key), self._pos[key]
            x = 8 + self.COL_W * column + self.COL_W / 2
            # the integer value at or just above the centre
            base = math.floor(pos)
            for offset in range(-math.ceil(half), math.ceil(half) + 1):
                value = base + offset
                distance = value - pos
                if abs(distance) > half:
                    continue
                # y of this value (positions between integers animate smoothly)
                y = mid + distance * self.ROW_H
                # t = 0 at the centre, 1 at the edge: used to fade the colour and shrink the font
                t = min(abs(distance) / (self.VISIBLE / 2), 1.0)
                rgb = tuple(round(a + (b - a) * t) for a, b in zip(self.INK, self.FADE))
                size = round(13 - 3 * t)
                # the value text (wrapping around with % count)
                canvas.create_text(x, y, text=f"{value % count + (self.min_hour if key == 'hour' else 0):02d}", fill="#%02x%02x%02x" % rgb,
                                   font=("TkDefaultFont", size))
        # white strips hide text that scrolls into the top and bottom margins
        canvas.create_rectangle(0, 0, width, 4, fill="white", outline="white")
        canvas.create_rectangle(0, 4 + self.VISIBLE * self.ROW_H, width,
                                8 + self.VISIBLE * self.ROW_H, fill="white", outline="white")

    def _sync_wheels(self) -> None:
        """Move the wheels to the value in the entry (after typing)."""
        value = self._value()
        if value is None or self._canvas is None:
            return
        # move each wheel by the shortest way round to the new value
        for key, current in zip(("hour", "minute"), (value[0] - self.min_hour, value[1])):
            count = self._count(key)
            delta = (current - self._target[key]) % count
            if delta > count / 2:
                delta -= count
            self._target[key] += delta
        self._animate()

    def _move_to(self, key: str, target: int) -> None:
        """Set a wheel's target position, write the value into the field and start the animation."""
        self._target[key] = target
        hour, minute = self._value() or (0, 0)
        if key == "hour":
            hour = self.min_hour + target % (self.hours - self.min_hour)
        else:
            minute = target % 60
        self._set(hour, minute)
        self._animate()

    def _animate(self) -> None:
        """Ease the wheels towards their targets, one small step per frame."""
        if self._canvas is None:
            return
        done = True
        for key in ("hour", "minute"):
            gap = self._target[key] - self._pos[key]
            # close enough: snap
            if abs(gap) < 0.02:
                self._pos[key] = float(self._target[key])
            else:
                # move 35 % of the remaining distance per frame (an ease-out animation)
                self._pos[key] += gap * 0.35
                done = False
        self._draw()
        if self._anim is not None:
            with contextlib.suppress(tk.TclError):
                self._canvas.after_cancel(self._anim)
            self._anim = None
        if not done:
            # about 60 frames per second until the targets are reached
            self._anim = self._canvas.after(16, self._animate)

    def _on_wheel(self, event, direction: int = 0) -> str:
        """Mouse wheel over a column: one step per notch."""
        if direction == 0:
            delta = getattr(event, "delta", 0)
            if not delta:
                return "break"
            # Windows/macOS: delta > 0 means wheel up = previous value
            direction = -1 if delta > 0 else 1
        key = self._column_at(event.x)
        self._move_to(key, self._target[key] + direction)
        return "break"

    def _on_press(self, event) -> str:
        """Start of a click or a drag on a wheel column."""
        key = self._column_at(event.x)
        self._drag = {"key": key, "y": event.y, "pos": self._pos[key], "moved": False}
        return "break"

    def _on_drag(self, event) -> str:
        """Dragging a column scrolls it with the pointer."""
        drag = self._drag
        if drag is None:
            return "break"
        # vertical movement since the press
        dy = event.y - drag["y"]
        # a few pixels of movement turn a click into a drag
        if abs(dy) > 3:
            drag["moved"] = True
        if drag["moved"]:
            # the column follows the pointer (one row per ROW_H pixels)
            self._pos[drag["key"]] = drag["pos"] - dy / self.ROW_H
            self._target[drag["key"]] = round(self._pos[drag["key"]])
            self._draw()
        return "break"

    def _on_release(self, event) -> str:
        """End of a drag (snap to the nearest value) or a click (jump to the clicked value)."""
        drag, self._drag = self._drag, None
        if drag is None:
            return "break"
        key = drag["key"]
        if drag["moved"]:
            # a drag: settle on the nearest whole value
            self._move_to(key, round(self._pos[key]))
        else:
            # a click: jump by the number of rows between the click and the centre
            mid = 4 + self.VISIBLE * self.ROW_H / 2
            rows = round((event.y - mid) / self.ROW_H)
            self._move_to(key, round(self._pos[key]) + rows)
        return "break"


# Years offered by the date picker: from 1990 to five years after today.
PICKER_EARLIEST_YEAR = 1990
PICKER_YEARS_AHEAD = 5


class DateTimeField:
    """Date-and-time field: a read-only 'YYYY-MM-DD hh:mm' box; clicking it (or the
    calendar button) opens a DateTimePicker in which the day is clicked in a calendar
    and the time chosen from hour and minute lists.  The value is the local clock time
    of the zone given by zone_getter(); for a time that occurs twice (clocks set back)
    the zone abbreviation chosen in the picker is appended ('2026-11-01 01:30 CST')."""

    def __init__(self, parent, var, zone_getter, compact: bool = False,
                 title: str = "Date and time", clearable: bool = False,
                 suggestions=None) -> None:
        """Build the read-only date/time entry plus 'Pick…' (and optional 'Clear') buttons.

        `zone_getter` returns the current time zone; `suggestions` may return times to offer in the
        picker (e.g. the ends of the previous LD cycles).
        """
        # the StringVar that holds the local date/time text
        self.var = var
        self.suggestions = suggestions      # callable -> None or (title, [(text, label)], note)
        self.zone_getter = zone_getter
        self.title = title
        # the field = read-only entry + calendar button (+ optional Clear button)
        self.frame = ttk.Frame(parent)
        # read-only: the value can only be chosen in the picker, so it is always valid
        self.entry = ttk.Entry(self.frame, textvariable=var, width=19 if compact else 21,
                               font="TkFixedFont", state="readonly", cursor="hand2")
        self.entry.pack(side="left")
        # a click on the text also opens the picker
        self.entry.bind("<Button-1>", lambda _e: self.open())
        # U+1F4C5 = calendar emoji
        self.button = ttk.Button(self.frame, text="\U0001f4c5" if compact else "\U0001f4c5 Pick\u2026",
                                 width=3 if compact else None, command=self.open)
        self.button.pack(side="left", padx=(4, 0))
        self.clear_button = None
        if clearable:
            self.clear_button = ttk.Button(self.frame, text="Clear", width=6,
                                           command=lambda: self.var.set(""))
            self.clear_button.pack(side="left", padx=(4, 0))
        # the open picker, if any
        self._picker = None

    def grid(self, **kwargs) -> None:
        """Place the field with grid."""
        self.frame.grid(**kwargs)

    def grid_remove(self) -> None:
        """Hide the field."""
        self.frame.grid_remove()

    def pack(self, **kwargs) -> None:
        """Place the field with pack."""
        self.frame.pack(**kwargs)

    def state(self, spec) -> None:
        """Enable/disable the field and its buttons."""
        on = "disabled" not in spec
        self.entry.state(["!disabled", "readonly"] if on else ["disabled"])
        for button in (self.button, self.clear_button):
            if button is not None:
                button.state(["!disabled"] if on else ["disabled"])

    def open(self) -> str:
        """Open the date/time picker dialog (only one per field at a time)."""
        if self.entry.instate(["disabled"]):
            return "break"
        # a picker for this field is already open: bring it to the front
        if self._picker is not None:
            with contextlib.suppress(tk.TclError):
                if self._picker.win.winfo_exists():
                    self._picker.win.lift()
                    return "break"
        try:
            # the picker needs the zone of the data (for clock changes and the UTC check line)
            tz = get_time_zone(self.zone_getter())
        except ValueError as error:
            messagebox.showerror("Time zone", str(error))
            return "break"

        def accept(text: str) -> None:
            """The picker's OK: store the chosen text."""
            self.var.set(text)
            self._picker = None

        def closed() -> None:
            """The picker was closed without a choice."""
            self._picker = None

        # optional suggested times (e.g. the ends of the previous LD cycle)
        offer = None
        if self.suggestions is not None:
            try:
                offer = self.suggestions()
            except Exception:
                offer = None
        # open the dialog; it calls accept() on OK or closed() on Cancel
        self._picker = DateTimePicker(self.frame.winfo_toplevel(), self.var.get(), tz,
                                      zone_name(tz), accept, closed, self.title, offer)
        return "break"


class DateTimePicker:
    """Mouse-driven picker for a date and time (local clock time of a time zone).

    Click a day in the calendar, choose the hour and minute from the lists (the mouse
    wheel also changes them) and click OK.  On the days the clocks change (shaded), a
    skipped time is rejected and for a repeated time the first or the second one must
    be chosen.  OK is only enabled for a valid date and time."""

    # colours of the selected day / days with a clock change / disabled days
    SELECTED_BG, SELECTED_FG = "#1f6fd1", "white"
    CHANGE_BG = "#fff1cc"          # days with a clock change
    DISABLED_FG = "#b0b0b0"

    def __init__(self, parent, initial_text: str, tz, zone_label: str, on_ok, on_close=None,
                 title: str = "Date and time", suggestions=None) -> None:
        """Build the dialog: month/year navigation, the month grid (days with clock changes shaded),
        hour/minute lists, the choice for an ambiguous hour, an optional list of suggested times and
        a check line that shows the result in local time and UTC.
        """
        # remember the zone and the callbacks
        self.tz, self.zone_label = tz, zone_label
        self.on_ok, self.on_close = on_ok, on_close
        # 'now' in the zone of the data, without seconds
        now = datetime.now(timezone.utc).astimezone(tz).replace(tzinfo=None, second=0, microsecond=0)
        self.today = now.date()
        # the year list ends five years from now
        self.latest_year = max(self.today.year + PICKER_YEARS_AHEAD, PICKER_EARLIEST_YEAR)
        initial_choice = ""
        # start at the current value of the field (with its CDT/CST choice), or at 'now'
        try:
            moment = local_to_utc(initial_text, tz)
            selected = moment.astimezone(tz).replace(tzinfo=None)
            if is_ambiguous_local(initial_text, tz):
                initial_choice = moment.astimezone(tz).tzname()
        except ValueError:
            selected = now
        self.selected = selected.date()
        self.view = (selected.year, selected.month)

        # a dialog window on top of the main window
        win = self.win = tk.Toplevel(parent)
        win.title(f"{title} \u2013 {zone_label}")
        win.transient(parent)
        win.resizable(False, False)

        # header: previous month, month list, year list, next month, Today
        head = ttk.Frame(win, padding=(10, 10, 10, 4))
        head.pack(fill="x")
        self.prev_button = ttk.Button(head, text="\u25c0", width=3, command=lambda: self._shift(-1))
        self.prev_button.pack(side="left")
        self.month_var, self.year_var = tk.StringVar(), tk.StringVar()
        month_box = ttk.Combobox(head, textvariable=self.month_var, state="readonly", width=10,
                                 values=list(calendar.month_name)[1:])
        month_box.pack(side="left", padx=(6, 2))
        year_box = ttk.Combobox(head, textvariable=self.year_var, state="readonly", width=6,
                                values=[str(y) for y in range(self.latest_year, PICKER_EARLIEST_YEAR - 1, -1)])
        year_box.pack(side="left", padx=(2, 6))
        for box in (month_box, year_box):
            box.bind("<<ComboboxSelected>>", lambda _e: self._from_lists())
        self.next_button = ttk.Button(head, text="\u25b6", width=3, command=lambda: self._shift(1))
        self.next_button.pack(side="left")
        ttk.Button(head, text="Today", command=self._go_today).pack(side="right")

        # the month grid: weekday names and 6 x 7 day buttons
        grid = ttk.Frame(win, padding=(10, 2, 10, 2))
        grid.pack()
        for column, name in enumerate(("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")):
            ttk.Label(grid, text=name, width=4, anchor="center", foreground="#666666").grid(row=0, column=column)
        self.day_buttons = []
        for row in range(6):
            line = []
            for column in range(7):
                button = tk.Button(grid, width=3, relief="flat", borderwidth=1, cursor="hand2")
                button.grid(row=row + 1, column=column, padx=1, pady=1)
                line.append(button)
            self.day_buttons.append(line)
        # remember the normal button colour to restore it
        self.default_bg = self.day_buttons[0][0].cget("background")
        # note under the grid (explains shaded days or the change on the selected day)
        self.day_note_var = tk.StringVar(value="")
        ttk.Label(win, textvariable=self.day_note_var, foreground="#8a5a00", wraplength=330,
                  justify="left", padding=(10, 0)).pack(fill="x")

        # time: hour and minute lists (mouse wheel works on them), 'Now'
        time_row = ttk.Frame(win, padding=(10, 8, 10, 2))
        time_row.pack(fill="x")
        ttk.Label(time_row, text="Time (24-hour clock)").pack(side="left")
        self.hour_var = tk.StringVar(value=f"{selected.hour:02d}")
        self.minute_var = tk.StringVar(value=f"{selected.minute:02d}")
        self.hour_box = ttk.Combobox(time_row, textvariable=self.hour_var, state="readonly", width=4,
                                     values=[f"{h:02d}" for h in range(24)])
        self.hour_box.pack(side="left", padx=(10, 2))
        ttk.Label(time_row, text=":").pack(side="left")
        self.minute_box = ttk.Combobox(time_row, textvariable=self.minute_var, state="readonly", width=4,
                                       values=[f"{m:02d}" for m in range(60)])
        self.minute_box.pack(side="left", padx=(2, 0))
        ttk.Button(time_row, text="Now", width=6, command=self._go_now).pack(side="right")
        for box, var, size in ((self.hour_box, self.hour_var, 24), (self.minute_box, self.minute_var, 60)):
            box.bind("<<ComboboxSelected>>", lambda _e: self._update())
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                box.bind(sequence, lambda e, v=var, n=size: self._wheel(e, v, n))

        # the CDT/CST choice, shown only for an ambiguous time
        self.choice_var = tk.StringVar(value=initial_choice)
        self.choice_row = ttk.Frame(win, padding=(10, 4, 10, 0))
        ttk.Label(self.choice_row, text="This time occurs twice:").pack(side="left")
        self.choice_buttons = []
        for _ in range(2):
            button = ttk.Radiobutton(self.choice_row, variable=self.choice_var, command=self._update)
            button.pack(side="left", padx=(8, 0))
            self.choice_buttons.append(button)

        # the check line: the result in local time and UTC (green) or the error (red)
        self.preview_var = tk.StringVar(value="")
        self.preview = tk.Label(win, textvariable=self.preview_var, wraplength=340, justify="left",
                                anchor="w", padx=10, pady=6)
        self.preview.pack(fill="x")

        # suggested times (e.g. the ends of D or L of the previous LD cycle)
        # optional list of suggested times
        self.suggest_items = []
        if suggestions:
            s_title, items, s_note = suggestions
            box = ttk.LabelFrame(win, text=s_title, padding=(8, 4, 8, 6))
            box.pack(fill="x", padx=10, pady=(0, 4))
            if items:
                inner = ttk.Frame(box)
                inner.pack(fill="x")
                # a list box with the suggested times; a click copies one, a double click also confirms
                self.suggest_list = tk.Listbox(inner, height=6, activestyle="dotbox", exportselection=False,
                                               font="TkFixedFont")
                bar = ttk.Scrollbar(inner, orient="vertical", command=self.suggest_list.yview)
                self.suggest_list.configure(yscrollcommand=bar.set)
                self.suggest_list.pack(side="left", fill="x", expand=True)
                bar.pack(side="right", fill="y")
                for text, label in items:
                    self.suggest_list.insert("end", label)
                self.suggest_items = list(items)
                self.suggest_list.bind("<<ListboxSelect>>", lambda _e: self._use_suggestion())
                self.suggest_list.bind("<Double-Button-1>", lambda _e: (self._use_suggestion(), self._ok()))
                # scroll to the suggestion closest to the current value
                nearest = self._nearest_suggestion(initial_text)
                if nearest is not None:
                    self.suggest_list.see(nearest)
                    if items[nearest][0] == str(initial_text).strip():
                        self.suggest_list.selection_set(nearest)
                ttk.Label(box, text="Click one to use it (double-click: use it and close).",
                          foreground="#666666").pack(anchor="w", pady=(3, 0))
            if s_note:
                ttk.Label(box, text=s_note, foreground="#8a5a00", wraplength=330,
                          justify="left").pack(anchor="w", pady=(3, 0))
        # OK / Cancel
        buttons = ttk.Frame(win, padding=(10, 4, 10, 10))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(side="right")
        self.ok_button = ttk.Button(buttons, text="OK", command=self._ok)
        self.ok_button.pack(side="right", padx=(0, 6))

        # keyboard: Esc = cancel, Return = OK; closing the window = cancel
        win.bind("<Escape>", lambda _e: self._cancel())
        win.bind("<Return>", lambda _e: self._ok())
        win.protocol("WM_DELETE_WINDOW", self._cancel)
        # draw the month and validate the initial value
        self._draw_month()
        self._update()
        # open near the mouse pointer but fully on screen; make it modal (grab_set)
        try:
            win.update_idletasks()
            x = parent.winfo_pointerx() - 40
            y = parent.winfo_pointery() + 10
            x = min(x, win.winfo_screenwidth() - win.winfo_reqwidth() - 10)
            y = min(y, win.winfo_screenheight() - win.winfo_reqheight() - 60)
            win.geometry(f"+{max(0, x)}+{max(0, y)}")
            win.grab_set()
            win.focus_set()
        except (tk.TclError, TypeError):
            pass

    # --- suggestions ---
    def _nearest_suggestion(self, text: str):
        """Index of the suggested time closest to `text`, to highlight it in the list."""
        if not self.suggest_items:
            return None
        try:
            target = local_to_utc(text, self.tz)
        except ValueError:
            return 0
        # linear search for the smallest time difference
        best, best_d = 0, None
        for k, (item, _label) in enumerate(self.suggest_items):
            try:
                d = abs((local_to_utc(item, self.tz) - target).total_seconds())
            except ValueError:
                continue
            if best_d is None or d < best_d:
                best, best_d = k, d
        return best

    def _use_suggestion(self) -> None:
        """Copy the selected suggestion into the date and time controls."""
        picked = self.suggest_list.curselection()
        if not picked:
            return
        text = self.suggest_items[picked[0]][0]
        # the suggestion text is 'YYYY-MM-DD hh:mm[ abbreviation]'
        local = parse_local(text[:16], "Suggested time")
        self.hour_var.set(f"{local.hour:02d}")
        self.minute_var.set(f"{local.minute:02d}")
        # the abbreviation (if any) chooses between the two occurrences of a repeated hour
        self.choice_var.set(text[17:].strip())
        self.view = (local.year, local.month)
        self._select(local.date())

    # --- calendar ---
    def _shift(self, months: int) -> None:
        """Show the month `months` before/after the current one (within the allowed years)."""
        year, month = self.view
        # month arithmetic with year carry
        month += months
        year += (month - 1) // 12
        month = (month - 1) % 12 + 1
        # stay within the year range of the list
        if year > self.latest_year or year < PICKER_EARLIEST_YEAR:
            return
        self.view = (year, month)
        self._draw_month()

    def _from_lists(self) -> None:
        """The month or year list changed: show that month."""
        try:
            month = list(calendar.month_name).index(self.month_var.get())
            year = int(self.year_var.get())
        except ValueError:
            return
        self.view = (year, month)
        self._draw_month()

    def _go_today(self) -> None:
        """Show and select today."""
        self.view = (self.today.year, self.today.month)
        self._select(self.today)

    def _go_now(self) -> None:
        """Select the current date and time."""
        now = datetime.now(timezone.utc).astimezone(self.tz)
        self.hour_var.set(f"{now.hour:02d}")
        self.minute_var.set(f"{now.minute:02d}")
        self.view = (now.year, now.month)
        self._select(now.date())

    def _select(self, day) -> None:
        """Select a day and redraw."""
        self.selected = day
        self._draw_month()
        self._update()

    def _draw_month(self) -> None:
        """Draw the day buttons of the shown month (selected day highlighted, today outlined, clock-change days shaded)."""
        year, month = self.view
        self.month_var.set(calendar.month_name[month])
        self.year_var.set(str(year))
        # disable the arrows at the ends of the year range
        self.next_button.state(["disabled"] if (year, month) >= (self.latest_year, 12) else ["!disabled"])
        self.prev_button.state(["disabled"] if (year, month) <= (PICKER_EARLIEST_YEAR, 1) else ["!disabled"])
        # fill the 6 x 7 buttons from the calendar of the shown month
        for week, buttons in zip(month_weeks(year, month), self.day_buttons):
            for number, button in zip(week, buttons):
                # cells outside the month are blank and disabled
                if number == 0:
                    button.configure(text="", state="disabled", relief="flat",
                                     background=self.default_bg, command="")
                    continue
                day = datetime(year, month, number).date()
                selected = day == self.selected
                # selected day blue, clock-change days shaded yellow, others normal
                background = (self.SELECTED_BG if selected
                              else self.CHANGE_BG if clock_change_on(day, self.tz)
                              else self.default_bg)
                button.configure(
                    text=str(number), state="normal", background=background,
                    foreground=self.SELECTED_FG if selected else "black",
                    disabledforeground=self.DISABLED_FG,
                    activebackground="#cfe0f7" if not selected else self.SELECTED_BG,
                    # today gets a solid outline
                    relief="solid" if day == self.today else "flat",
                    # a click selects that day (d=day binds the current value in the lambda)
                    command=lambda d=day: self._select(d))

    # --- time and validation ---
    def _wheel(self, event, var, size: int) -> str:
        """Mouse wheel over the hour/minute list: step the value with wrap-around."""
        # wheel up = earlier value; X11 uses button 4/5 instead of delta
        step = -1 if (getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4) else 1
        try:
            value = (int(var.get()) + step) % size
        except ValueError:
            value = 0
        var.set(f"{value:02d}")
        self._update()
        return "break"

    def base_text(self) -> str:
        """The chosen 'YYYY-MM-DD hh:mm' (without the CDT/CST choice)."""
        return f"{self.selected:%Y-%m-%d} {self.hour_var.get()}:{self.minute_var.get()}"

    def text(self) -> str:
        """The chosen text, with 'CDT'/'CST' appended when the hour occurs twice (end of daylight time)."""
        base = self.base_text()
        choice = self.choice_var.get()
        return f"{base} {choice}" if choice and is_ambiguous_local(base, self.tz) else base

    def _update(self) -> None:
        """Validate the choice and refresh the check line: non-existent (spring-forward) times are refused, repeated (fall-back) times need a choice."""
        # explain the selected day if its clocks change
        change = clock_change_on(self.selected, self.tz)
        if change:
            self.day_note_var.set(f"{self.selected:%a %d %b %Y}: {change[1]}")
        else:
            self.day_note_var.set(f"Shaded days: clock changes ({self.zone_label}).  "
                                  "Enter the local clock time of that day.")
        base = self.base_text()
        # a repeated hour: label the two radio buttons with the abbreviation and the offset
        if is_ambiguous_local(base, self.tz):
            local = parse_local(base, "Date/time")
            first = local.replace(tzinfo=self.tz, fold=0)
            second = local.replace(tzinfo=self.tz, fold=1)
            for button, moment, word in ((self.choice_buttons[0], first, "first"),
                                         (self.choice_buttons[1], second, "second")):
                button.configure(text=f"{moment.tzname()} \u2013 {word} "
                                      f"({utc_offset_label(moment.utcoffset())})",
                                 value=moment.tzname())
            # show the choice row above the check line
            self.choice_row.pack(fill="x", before=self.preview)
            if self.choice_var.get() not in (first.tzname(), second.tzname()):
                self.choice_var.set("")
        else:
            # no ambiguity: hide the choice row
            self.choice_row.pack_forget()
            self.choice_var.set("")
        # validate: an ambiguous time needs a choice; local_to_utc rejects skipped times
        try:
            if is_ambiguous_local(base, self.tz) and not self.choice_var.get():
                raise ValueError(f"{base} happens twice in {self.zone_label}: the clocks go "
                                 "back on this day.  Choose the first or the second one.")
            display = describe_local_time(self.text(), self.tz)
        except ValueError as error:
            # invalid: red message, OK disabled
            self.valid = False
            self.preview_var.set("\u2716 " + str(error))
            self.preview.configure(foreground="#b00020")
            self.ok_button.state(["disabled"])
            return
        # valid: green check line, OK enabled
        self.valid = True
        self.preview_var.set("\u2714 " + display)
        self.preview.configure(foreground="#1b7a1b")
        self.ok_button.state(["!disabled"])

    def _ok(self) -> None:
        """OK: return the text if it is valid."""
        self._update()
        if not getattr(self, "valid", False):
            return
        text = self.text()
        # close first, then hand the text to the field
        self._close()
        self.on_ok(text)

    def _cancel(self) -> None:
        """Cancel: close without a choice."""
        self._close()
        if self.on_close is not None:
            self.on_close()

    def _close(self) -> None:
        """Release the modal grab and destroy the dialog."""
        with contextlib.suppress(tk.TclError):
            self.win.grab_release()
        self.win.destroy()


class Tooltip:
    """A small tooltip shown while the pointer rests on a widget."""

    def __init__(self, widget, text: str) -> None:
        """Show `text` in a small window while the pointer is over `widget`."""
        # show/hide on pointer enter/leave
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _event=None) -> None:
        """Create the tooltip window below the widget."""
        if self.tip is not None:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        # a borderless window at the computed position
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, background="#ffffe0", relief="solid", borderwidth=1,
                 padx=4, pady=1).pack()

    def hide(self, _event=None) -> None:
        """Remove the tooltip window."""
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


class ScrollFrame(ttk.Frame):
    """A vertically scrollable frame (the left control panel)."""

    def __init__(self, parent, **kw):
        """A frame with a vertical scrollbar: put the content into self.inner."""
        super().__init__(parent, **kw)
        # a canvas that scrolls; the content frame lives inside it as a canvas window
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, padding=(10, 8))
        # the scroll region follows the size of the content
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        # the content is as wide as the canvas
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        # mouse wheel (bound for the whole application, filtered in _wheel/_scroll)
        self.bind_all("<MouseWheel>", self._wheel, add="+")
        self.bind_all("<Button-4>", lambda e: self._scroll(e, -1), add="+")
        self.bind_all("<Button-5>", lambda e: self._scroll(e, 1), add="+")

    def _inside(self, event) -> bool:
        """True if the event happened over this frame (or a child of it)."""
        # walk up the widget hierarchy
        w = event.widget
        while w is not None:
            if w is self:
                return True
            w = getattr(w, "master", None)
        return False

    def _wheel(self, event):
        """Mouse wheel (Windows/macOS) scrolls the frame, except over text boxes that scroll themselves."""
        if self._inside(event) and not isinstance(event.widget, tk.Text):
            step = -1 if event.delta > 0 else 1
            # macOS sends small deltas that are used directly
            if sys.platform == "darwin":
                step = -event.delta
            self.canvas.yview_scroll(int(step), "units")

    def _scroll(self, event, step):
        """Mouse wheel on X11 (buttons 4/5)."""
        if self._inside(event) and not isinstance(event.widget, tk.Text):
            self.canvas.yview_scroll(step, "units")


class SeriesWindow:
    """Time-series plot: raw data with the trend line, the data used for detection with the
    line (moving average, if chosen) and the peaks/troughs (click to remove or add them), and the
    light/dark schedule as a bar above each plot."""

    # maximum distance between a click and a marker for 'Remove'
    HIT_RADIUS_PX = 25          # how close (in pixels) a click must be to grab a marker
    # help text shown at the bottom of the window
    HELP = ("Choose 'Remove' and click a marker to delete it; choose 'Add peak' / 'Add trough' and "
            "click near the line to add one (it snaps to the nearest sample of the line). "
            "Hand edits are kept when the data or the detection settings change; 'Reset manual edits' "
            "returns to the automatic detection. While a zoom/pan tool of the toolbar is active, clicks "
            "do not edit anything. Bars above the plots: light (light colour) and dark (dark colour) "
            "periods of the light/dark conditions, when they are shown.")

    def __init__(self, app):
        """Build the window: click-mode buttons, matplotlib figure with toolbar, help text; clicks are
        handled by _on_click.
        """
        # the App (to report edits back) and the window itself
        self.app = app
        self.win = tk.Toplevel(app)
        self.win.title(f"{APP_NAME} \u2013 time series, peaks and troughs")
        # window width adapted to the screen
        w = max(900, min(1250, app.winfo_screenwidth() - 80))
        self.win.geometry(f"{w}x660+30+40")
        # closing the window only hides the plot; the App is told via close()
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        # top bar: click mode, Reset, Full view and a status line
        bar = ttk.Frame(self.win, padding=(8, 6, 8, 2))
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Click in the lower plot to").pack(side="left")
        # what a click in the lower plot does
        self.mode_var = tk.StringVar(value="remove")
        for text, value in (("Remove", "remove"), ("Add peak", "add_peak"), ("Add trough", "add_trough")):
            ttk.Radiobutton(bar, text=text, value=value, variable=self.mode_var).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Reset manual edits", command=app.reset_ts_edits).pack(side="left", padx=(14, 0))
        ttk.Button(bar, text="Full view", command=self.full_view).pack(side="left", padx=(6, 0))
        self.status = tk.StringVar()
        ttk.Label(bar, textvariable=self.status, foreground="#1f5fa8").pack(side="left", padx=(12, 0))
        # matplotlib figure + canvas + navigation toolbar (zoom, pan, home)
        tb = ttk.Frame(self.win)
        tb.pack(side="top", fill="x")
        self.fig = Figure(figsize=(11, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.win)
        self.toolbar = NavigationToolbar2Tk(self.canvas, tb)
        self.toolbar.update()
        ttk.Button(tb, text="Save plot\u2026", command=self.save).pack(side="right", padx=4)
        ttk.Label(self.win, text=self.HELP, foreground="#666666", wraplength=w - 30, justify="left",
                  padding=(8, 2, 8, 6)).pack(side="bottom", fill="x")
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
        # mouse clicks go to _on_click
        self.canvas.mpl_connect("button_press_event", self._on_click)
        # state: the detection axes, the analysis shown, the data key (to keep a zoom) and the full x range
        self.ax_det = None
        self.ts = None
        self._key = None
        self._full = None

    def close(self):
        """Close the window and tell the app (it reopens with 'Show plot')."""
        with contextlib.suppress(tk.TclError):
            self.win.destroy()
        self.app.series_win = None

    def show(self):
        """Bring the window to the front."""
        with contextlib.suppress(tk.TclError):
            self.win.deiconify()
            self.win.lift()

    def save(self):
        """Save the plot as PNG, SVG or PDF."""
        path = filedialog.asksaveasfilename(
            parent=self.win, title="Save plot", initialfile="time_series.png", defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("SVG image", "*.svg"), ("PDF", "*.pdf")])
        if path:
            try:
                # 300 dpi for print quality
                self.fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Could not save the plot:\n{exc}", parent=self.win)

    def full_view(self):
        """Show the whole record again (after zooming)."""
        if self.ax_det is not None and self._full is not None:
            self.ax_det.set_xlim(*self._full)
            self._fit_y()
            self.canvas.draw_idle()

    def _fit_y(self):
        """y range of every data plot fitted to the points in view."""
        ts = self.ts
        if ts is None or not ts.get("ok"):
            return
        # the visible x range
        x0, x1 = self.ax_det.get_xlim()
        # each panel: all its series, restricted to the visible range
        for ax, series in self._panels:
            vals = []
            for hx, hy in series:
                m = (hx >= x0) & (hx <= x1) & np.isfinite(hy)
                vals.append(hy[m])
            v = np.concatenate(vals) if vals else np.array([])
            if not len(v):
                continue
            lo, hi = float(v.min()), float(v.max())
            # 12 % margin above and below
            pad = (hi - lo) * 0.12 or abs(hi) * 0.1 or 1.0
            ax.set_ylim(lo - pad, hi + pad)

    def update(self, ts: dict, st: dict, res):
        """Redraw from a new analysis `ts`.

        Panels (top to bottom): LD bar, raw data + trend (detrended mode only), LD bar, the line used
        for detection with the markers.  All share the x axis; a zoom is kept while the data are the
        same, and the y ranges are fitted to the points in view.
        """
        # keep the zoom only if the data are the same as before
        key = st.get("series", "")
        view = None
        if self.ax_det is not None and key == self._key and self._full is not None:
            xl = tuple(self.ax_det.get_xlim())
            if any(abs(a - b) > 1e-9 for a, b in zip(xl, self._full)):
                view = xl
        self._key = key
        self.ts = ts
        # start from an empty figure
        self.fig.clear()
        self.ax_det = None
        self._panels = []
        # analysis failed: show its message in the middle
        if not ts.get("ok"):
            msg = ts.get("error") or "No time-series data yet."
            self.fig.text(0.5, 0.5, msg, ha="center", va="center", wrap=True, color="#b8323f")
            self.canvas.draw_idle()
            return
        hours = ts["hours"]
        # x range: whole days (multiples of 24 h) around the record, starting at 0 h at the latest
        x_min = min(0.0, math.floor(float(np.nanmin(hours)) / 24.0) * 24.0)
        x_max = math.ceil(float(np.nanmax(hours)) / 24.0) * 24.0
        if x_max <= x_min:
            x_max = x_min + 24.0
        # is there a schedule to show as bars?
        has_ld = bool(st.get("show_ld") and res is not None and res.ld is not None)
        # detrended mode: an extra upper panel with the raw data and the trend
        two = ts["source"] == "detrended"
        # the panels from top to bottom ('bar' = LD bar, 'raw', 'det' = detection panel)
        rows = (["bar"] if has_ld else []) + (["raw"] if two else []) + (["bar"] if has_ld and two else []) + ["det"]
        # relative heights
        heights = [0.13 if r == "bar" else (1.0 if r == "raw" else 1.35) for r in rows]
        grid = self.fig.add_gridspec(len(rows), 1, height_ratios=heights, hspace=0.12)
        self.fig.subplots_adjust(left=0.07, right=0.83, top=0.94, bottom=0.09)
        # the detection panel is the main axes; all others share its x axis (zoom together)
        main = self.fig.add_subplot(grid[rows.index("det")])
        axes = {}
        for i, r in enumerate(rows):
            axes[i] = main if r == "det" else self.fig.add_subplot(grid[i], sharex=main)
        self.ax_det = main
        light_on = dark_on = False
        for i, r in enumerate(rows):
            ax = axes[i]
            # LD bar over a wide range so panning still shows bars
            if r == "bar":
                draw_ld_bar(ax, res, st, x_min - 48, x_max + 48)
                ax.set_ylabel("L/D", rotation=0, fontsize=7, ha="right", va="center", labelpad=6)
                continue
            ax.grid(True, linewidth=0.5, color="lightgray", linestyle="--")
            if r == "raw":
                # upper panel: the rows as entered (violet points) and the trend line (red)
                ax.scatter(ts["t"], ts["y"], s=3, c="violet", label="Data (as entered)")
                ax.plot(hours, ts["trend"], "-r", linewidth=1.0, label=f"Trend line\n({ts['trend_label']})")
                ax.set_ylabel("Signal")
                ax.tick_params(labelbottom=False)
                self._panels.append((ax, [(ts["t"], ts["y"]), (hours, ts["trend"])]))
            else:
                name = "Detrended data" if two else "Data"
                # lower panel: the data used for detection and the detection line (green)
                ax.scatter(hours, ts["signal"], s=3, c="violet", label=name)
                ax.plot(hours, ts["smooth"], "-", color="limegreen", linewidth=1.0,
                        label=(f"{ts['smooth_n']}-point moving average" if ts["smooth_n"] > 1
                               else "Line (no moving average)"))
                if two:
                    # the zero line of detrended data
                    ax.axhline(0, color="#999999", linewidth=0.6)
                ax.set_ylabel("Detrended signal" if two else "Signal")
                ax.set_xlabel("Hours after 0 h of the data")
                self._panels.append((ax, [(hours, ts["signal"])]))
                # the peak/trough markers
                self._draw_markers(ax, ts)
            ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=7, frameon=False)
        main.set_xlim(x_min, x_max)
        # x ticks at 'nice' multiples (1, 1.2, 2.4, 3, 6 x 10^k: 12 h, 24 h, 60 h, ...)
        main.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=16, steps=[1, 1.2, 2.4, 3, 6]))
        self._full = (x_min, x_max)
        title = st.get("title", "").strip()
        source = "detrended data" if two else "raw data"
        self.fig.suptitle((title + "   \u2013   " if title else "") + f"peaks and troughs of the {source}",
                          fontsize=10)
        # legend for the LD bars
        if has_ld:
            from matplotlib.patches import Patch
            light = pick_color(st.get("light_color"), LIGHT_COLORS)
            dark = pick_color(st.get("dark_color"), DARK_COLORS)
            axes[0].legend(handles=[Patch(facecolor=light, edgecolor="#555555", label="Light"),
                                    Patch(facecolor=dark, edgecolor="#555555", label="Dark")],
                           loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=7, frameon=False, ncol=2)
        # restore the previous zoom
        if view is not None:
            main.set_xlim(*view)
        self._fit_y()
        self.canvas.draw_idle()

    def _draw_markers(self, ax, ts):
        """Peaks (red) and troughs (blue) on the detection line, with their times; hand-added ones get a black ring."""
        hours, smooth = ts["hours"], ts["smooth"]
        # same drawing for peaks (labels above) and troughs (labels below)
        for kind, color, sign, va in (("peaks", PEAK_COLOR, 1, "bottom"), ("troughs", TROUGH_COLOR, -1, "top")):
            idx = ts[kind]
            if not idx:
                continue
            # automatic indices; the others were added by hand
            auto = set(ts["auto_" + kind])
            hand = [i for i in idx if i not in auto]
            # filled markers
            ax.scatter(hours[idx], smooth[idx], marker="o", s=40, color=color, zorder=5,
                       label=kind.capitalize())
            if hand:
                # a black ring around hand-added markers
                ax.scatter(hours[hand], smooth[hand], marker="o", s=90, facecolors="none",
                           edgecolors="black", linewidths=1.2, zorder=6,
                           label=f"{kind.capitalize()} added by hand")
            # the time next to every marker
            for i in idx:
                ax.annotate(f"{hours[i]:.2f} h", (hours[i], smooth[i]), xytext=(0, sign * 6),
                            textcoords="offset points", fontsize=7, color=color, ha="center", va=va,
                            annotation_clip=True, clip_on=True)

    def _toolbar_active(self) -> bool:
        """True while the zoom or pan tool of the matplotlib toolbar is on (then clicks do not edit)."""
        # the toolbar's mode is '' when no tool is active (an enum in newer matplotlib)
        mode = getattr(self.toolbar, "mode", "")
        return bool(getattr(mode, "value", mode))

    def _on_click(self, event):
        """Edit by clicking: 'Remove' deletes the nearest marker within HIT_RADIUS_PX; 'Add peak/trough'
        adds one at the sample nearest to the click (refused if that sample is already marked).
        """
        ts = self.ts
        # only left clicks in the detection panel, with no toolbar tool active
        if (ts is None or not ts.get("ok") or event.inaxes is not self.ax_det or event.button != 1
                or event.xdata is None or self._toolbar_active()):
            return
        mode = self.mode_var.get()
        hours, smooth = ts["hours"], ts["smooth"]
        if mode == "remove":
            # every marker as (kind, row index)
            candidates = [("peak", i) for i in ts["peaks"]] + [("trough", i) for i in ts["troughs"]]
            if not candidates:
                self.status.set("There are no markers to remove.")
                return
            # marker positions in data coordinates -> screen pixels
            pts = np.array([(hours[i], smooth[i]) for _, i in candidates], dtype=float)
            px = self.ax_det.transData.transform(pts)
            # pixel distance from the click to each marker
            d = np.hypot(px[:, 0] - event.x, px[:, 1] - event.y)
            k = int(np.argmin(d))
            if d[k] > self.HIT_RADIUS_PX:
                self.status.set("No marker near the click.")
                return
            kind, index = candidates[k]
            # remember the removal; the App redraws
            self.app.ts_remove(kind, index)
            self.status.set(f"Removed {kind} at {hours[index]:.2f} h.")
            return
        kind = "peak" if mode == "add_peak" else "trough"
        # add: the nearest sample of the detection line to the clicked time
        valid = np.flatnonzero(np.isfinite(smooth))
        if not len(valid):
            return
        index = int(valid[np.argmin(np.abs(hours[valid] - event.xdata))])
        same, other = (ts["peaks"], ts["troughs"]) if kind == "peak" else (ts["troughs"], ts["peaks"])
        # a sample can be only one peak or one trough
        if index in same:
            self.status.set(f"There is already a {kind} at {hours[index]:.2f} h.")
            return
        if index in other:
            self.status.set(f"{hours[index]:.2f} h is already marked as the opposite type; remove it first.")
            return
        self.app.ts_add(kind, index)
        self.status.set(f"Added {kind} at {hours[index]:.2f} h.")


class App(tk.Tk):
    """The main window: settings column on the left, actogram, fine-tune panel and phase analysis on
    the right.

    Data flow: every control is bound to a Tk variable; any change calls schedule(), which runs
    redraw() once after a short delay.  redraw() reads all controls into one settings dict
    (get_settings), detects peaks/troughs if time-series input is used, runs compute() and
    analyze(), draws the actogram and updates every message.  apply_settings() does the reverse
    (settings dict -> controls), e.g. when a settings file is loaded.
    """
    def __init__(self):
        """Create the window, its variables, menus and panels; restore the display options of the last
        session; start with the example data (time-series input) and draw.
        """
        # initialise Tk (this object *is* the main window)
        super().__init__()
        self.title(APP_NAME)
        # window size adapted to the screen, centred horizontally
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        self._win_w = max(1000, min(1700, screen_w - 40))
        win_h = max(640, min(940, screen_h - 80))
        self.geometry(f"{self._win_w}x{win_h}+{max(0, (screen_w - self._win_w) // 2)}+10")
        self.minsize(1000, 640)
        # window icon (if the icon files are present)
        self._set_icon()
        # _pending: the scheduled redraw; _loading: suppress redraws while settings are applied
        self._pending = None
        self._loading = False
        # anchors of the day-0 slider (it moves relative to where a drag started)
        self._anchor = {"t0": None, "origin": None}
        self._last_scale = {"t0": 0.0, "origin": 0.0}

        # start from the defaults, overlay the remembered display options of the last session
        s = default_settings()
        try:
            if SETTINGS_FILE.exists():
                s.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
        # every session starts with the example data (title 'Example Data'), T = 24:00 and
        # US Central Time, with the example time series detected (the default input);
        # only the display options of the last session are kept
        s.update(example_settings())
        s.update(input_mode="series", series=example_series_text(), ts_edits=empty_edits())

        # Tk variables, menu, the two panes (settings column | plots), their contents
        self._make_vars()
        self._build_menu()
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True)
        # left: scrollable settings column
        left = ScrollFrame(panes, width=460)
        self._panes, self._left = panes, left
        # right: fine-tune panel, actogram, phase analysis
        right = ttk.Frame(panes, padding=(6, 6))
        panes.add(left, weight=0)
        panes.add(right, weight=1)
        # size the left column once the window exists
        self.after(150, self._fit_left_panel)
        self._build_controls(left.inner)
        self._build_plot(right)
        # put the settings into the controls
        self.apply_settings(s)
        ex = example_settings()          # 'Enter the times' then shows the example's typed lists
        self._times_backup = {"peaks": ex["peaks"], "troughs": ex["troughs"],
                              "selection": {"sel_peaks": list(ex["sel_peaks"]), "sel_troughs": list(ex["sel_troughs"])}}
        # remember display options when the window is closed
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        # first drawing
        self.redraw()
        if self.input_mode_var.get() == "series":       # the default input: show its plot as well
            self.after(400, self.show_series_window)

    def _fit_left_panel(self, tries: int = 0):
        """Open the settings column wide enough to show the whole LD-cycle table
        (at most 60 % of the window; the divider can still be dragged)."""
        try:
            self.update_idletasks()
            # the width the content asks for, plus the scrollbar
            need = self._left.inner.winfo_reqwidth() + 30          # + scrollbar
            # make the column ask for that width (so it is never collapsed) ...
            self._left.canvas.configure(width=need)
            total = self._panes.winfo_width()
            if total < need + 300:                 # window not laid out yet: try again
                if tries < 40:
                    self.after(50, lambda: self._fit_left_panel(tries + 1))
                return
            # ... and place the divider there once the window has its real size
            # the divider: at most 36 % of the window, at least 420 px
            self._panes.sashpos(0, max(420, min(need, int(total * 0.36))))
        except tk.TclError:
            pass

    def _set_icon(self):
        """Window icon: Actogram_Plotter.ico (Windows) or .png, next to the script or
        bundled by PyInstaller (--add-data)."""
        # PyInstaller unpacks bundled files to sys._MEIPASS; otherwise look next to the script
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        ico, png = base / "Actogram_Plotter.ico", base / "Actogram_Plotter.png"
        with contextlib.suppress(Exception):
            if sys.platform.startswith("win") and ico.exists():
                self.iconbitmap(default=str(ico))      # also used by the picker windows
                return
            if png.exists():
                self._icon_image = tk.PhotoImage(file=str(png))
                self.iconphoto(True, self._icon_image)

    # ---------------- variables ----------------
    def _make_vars(self):
        """Create the Tk variables behind every control (one per setting) and the selection state."""
        # Clock time of the data
        self.t0_var, self.tz_var = tk.StringVar(), tk.StringVar()
        # light/dark conditions: shown?, extend the first one before its start?, number of changes
        self.show_ld_var, self.extend_var = tk.BooleanVar(), tk.BooleanVar()
        self.n_changes_var = tk.IntVar(value=1)
        # one dict of variables per condition card: mode, L, D, start, Light/Dark first
        self.cycle_vars = [{k: tk.StringVar() for k in ("mode", "L", "D", "start", "phase")}
                           for _ in range(1 + MAX_CHANGES)]
        # actogram day 0 (option and custom time); title; period T
        self.origin_var, self.origin_time_var = tk.StringVar(), tk.StringVar()
        self.title_var, self.period_var = tk.StringVar(), tk.StringVar()
        # plot options: double/single, row labels, show times, connecting lines, rows, labels, marks
        self.plot_var, self.rowlab_var = tk.StringVar(), tk.StringVar()
        self.show_values_var = tk.BooleanVar()
        self.link_peak_var, self.link_trough_var = tk.BooleanVar(), tk.BooleanVar()
        self.rows_auto_var = tk.BooleanVar(value=True)
        self.label_onsets_var, self.label_row_starts_var = tk.BooleanVar(), tk.BooleanVar()
        self.placed_var = tk.StringVar()
        self.mark_times_var = tk.BooleanVar(value=True)
        self.mark_changes_var = tk.BooleanVar(value=True)
        # ticks and band colours
        self.x_minor_var = tk.StringVar(value=X_MINOR_CHOICES[0])
        self.x_major_var = tk.StringVar(value=X_MAJOR_DEFAULT)
        self.light_color_var = tk.StringVar(value=LIGHT_COLORS[0][1])
        # the selected peak/trough values for the phase analysis (lists of floats)
        self.selection = {"sel_peaks": [], "sel_troughs": []}
        # phase-analysis options
        self.phase_ref_var = tk.StringVar(value=PHASE_REFS[0][1])
        self.draw_fit_var = tk.BooleanVar(value=True)
        self.drag_mode_var = tk.StringVar(value="select")
        self.sel_target_var = tk.StringVar(value="both")
        self.dark_color_var = tk.StringVar(value=DARK_COLORS[0][1])
        self.row_min_var, self.row_max_var = tk.StringVar(value="0"), tk.StringVar(value="5")
        # time-series input: mode, drawing options, detection settings, hand edits, the analysis result,
        # the series window, the typed lists kept while the series mode is on, and helper flags
        # time-series input
        self.input_mode_var = tk.StringVar(value="times")
        self.ts_draw_var = tk.StringVar(value=dict(TS_DRAW_MODES)["none"])
        self.ts_draw_data_var = tk.StringVar(value="raw")
        self.ts_draw_scale_var = tk.StringVar(value=dict(TS_DRAW_SCALES)["all"])
        self.show_points_var = tk.BooleanVar(value=True)
        self.ts_vars = {k: tk.StringVar(value=v) for k, v in TS_DEFAULTS.items()}
        self.ts_edits = empty_edits()
        self.ts = None
        self.series_win = None
        self._times_backup = None
        self._ts_deselected = set()
        self._writing = False
        # every variable whose change must redraw: trace_add('write') calls schedule()
        all_vars = [self.mark_changes_var, self.phase_ref_var, self.draw_fit_var, self.light_color_var, self.dark_color_var, self.placed_var, self.mark_times_var, self.x_major_var, self.x_minor_var, self.label_onsets_var, self.label_row_starts_var, self.rows_auto_var, self.row_min_var, self.row_max_var, self.t0_var, self.tz_var, self.show_ld_var, self.extend_var, self.n_changes_var,
                    self.origin_var, self.origin_time_var, self.title_var, self.period_var,
                    self.plot_var, self.rowlab_var, self.show_values_var, self.link_peak_var,
                    self.link_trough_var, self.input_mode_var, self.ts_draw_var, self.ts_draw_data_var,
                    self.ts_draw_scale_var, self.show_points_var] + list(self.ts_vars.values()) \
            + [v for c in self.cycle_vars for v in c.values()]
        for v in all_vars:
            v.trace_add("write", lambda *_a: self.schedule())

    # ---------------- menu ----------------
    def _build_menu(self):
        """Menu bar: File (save figure, settings), Edit (example, clear) and Help."""
        bar = tk.Menu(self)
        # File menu
        m = tk.Menu(bar, tearoff=False)
        m.add_command(label="Save figure…", command=self.save_figure, accelerator="Ctrl+S")
        m.add_separator()
        m.add_command(label="Load settings…", command=self.load_settings_file)
        m.add_command(label="Save settings…", command=self.save_settings_file)
        m.add_command(label="Reset to defaults (example data)", command=lambda: self.apply_settings(default_settings()))
        m.add_separator()
        m.add_command(label="Quit", command=self.on_close)
        bar.add_cascade(label="File", menu=m)
        self.config(menu=bar)
        # keyboard shortcut Ctrl+S (Cmd+S on macOS) saves the figure
        self.bind_all("<Control-s>", lambda _e: self.save_figure())
        if sys.platform == "darwin":
            try:
                self.bind_all("<Command-s>", lambda _e: self.save_figure())
            except tk.TclError:
                pass

    # ---------------- left panel ----------------
    def _box(self, parent, title, kind=None):
        """A titled section; kind 'rec' (red frame) or 'disp' (blue frame) adds a coloured
        border and a tag after the title."""
        # plain box without the green/blue marking
        if kind is None:
            box = ttk.LabelFrame(parent, text=title, padding=(10, 6))
            box.pack(fill="x", pady=(0, 10))
            return box
        # colours of this kind of box
        color, bar, _tint, tag = FRAME_KINDS[kind]
        # the coloured outer frame shows as a bar on the left (the inner box is inset by 5 px)
        outer = tk.Frame(parent, background=bar)          # shows as a coloured bar on the left
        outer.pack(fill="x", pady=(0, 10))
        # the title row: bold title + small coloured tag
        head = ttk.Frame(outer)
        ttk.Label(head, text=title, font=self.bold_font).pack(side="left")
        ttk.Label(head, text=tag, foreground=color, font=self.tag_font).pack(side="left", padx=(10, 0))
        box = ttk.LabelFrame(outer, labelwidget=head, padding=(10, 6))
        box.pack(fill="x", padx=(5, 0))
        return box

    def _guide(self, parent):
        """Explains the red and blue frames (top of the settings column)."""
        frame = ttk.Frame(parent, padding=(2, 0, 2, 8))
        frame.pack(fill="x")
        # the two explanation lines at the top of the column
        texts = (("rec", "Green bar \u2013 from your records. Enter these from your lab notebook and experiment "
                         "records: the clock time of 0 h and its time zone, the peak and trough times, the "
                         "sample placement and the light/dark schedule. A wrong value puts the data at the "
                         "wrong time."),
                 ("disp", "Blue bar \u2013 view settings. Change these freely: day 0, the period T, the rows, "
                          "ticks, labels and other plot options only change how the actogram looks, never "
                          "the data."))
        for r, (kind, text) in enumerate(texts):
            _color, bar, tint, _tag = FRAME_KINDS[kind]
            # a small swatch: tinted rectangle with the coloured bar at its left
            swatch = tk.Frame(frame, width=26, height=16, background=tint)
            swatch.grid(row=r, column=0, sticky="nw", padx=(0, 8), pady=(3, 4))
            swatch.grid_propagate(False)
            tk.Frame(swatch, width=5, height=16, background=bar).place(x=0, y=0)
            ttk.Label(frame, text=text, wraplength=380, justify="left").grid(row=r, column=1, sticky="w", pady=(0, 4))

    def _note(self, parent, color="#666666", **grid):
        """A wrapped message label bound to a new StringVar (blue info / red error lines under the inputs)."""
        var = tk.StringVar()
        lab = ttk.Label(parent, textvariable=var, foreground=color, justify="left", wraplength=380)
        lab.grid(sticky="w", **grid)
        return var

    def _build_controls(self, root):
        """Build the settings column: clock time of the data, peaks and troughs (typed or detected),
        sample placement, light/dark conditions, actogram day 0 and the plot options.  Each block is
        a tinted box: green = from your records, blue = view settings.
        """
        # fonts: a bold copy of the default font (box titles) and a smaller bold one (the tags)
        from tkinter import font as tkfont
        base = tkfont.nametofont("TkDefaultFont")
        self.bold_font = base.copy(); self.bold_font.configure(weight="bold")
        self.tag_font = base.copy()
        self.tag_font.configure(weight="bold", size=max(7, int(abs(base.cget("size")) * 0.8)))
        # the explanation of green and blue boxes at the top
        self._guide(root)
        # clock time
        # ==== block 'Clock time of the data' (green) ====
        box = self._box(root, "Clock time of the data", "rec")
        # column 0 = short labels only; the wide notes below span all columns and give their
        # extra width to column 1 (weight 1), so the fields start right after the labels
        box.columnconfigure(0, weight=0)
        box.columnconfigure(1, weight=1)
        # 0 h = a date/time chosen in the picker
        ttk.Label(box, text="0 h =").grid(row=0, column=0, sticky="w")
        DateTimeField(box, self.t0_var, self.tz_var.get, title="Clock time of 0 h").grid(
            row=0, column=1, sticky="w", padx=(4, 0))
        # time zone: choose from the list or type any IANA name / fixed offset
        ttk.Label(box, text="Time zone").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(box, textvariable=self.tz_var, values=TIME_ZONE_CHOICES, width=40,
                     height=len(TIME_ZONE_CHOICES)).grid(
            row=1, column=1, sticky="we", padx=(4, 0), pady=(6, 0))
        ttk.Label(box, text="Default: US Central Time (America/Chicago, CST/CDT). Any IANA zone name "
                            "(e.g. Europe/Rome) or a fixed offset (e.g. UTC+09:00) can also be typed.",
                  foreground="#666666", wraplength=380, justify="left").grid(
            row=10, column=0, columnspan=2, sticky="w", pady=(2, 0))
        ttk.Label(box, text="\u26a0 Enter every date/time as the LOCAL clock time, as shown on a wall clock "
                            "on that day \u2013 standard or daylight time alike (e.g. CST in winter, CDT in "
                            "summer). Do not convert daylight time to standard time: the switch and the "
                            "offset to UTC are taken into account automatically.",
                  foreground="#a35400", wraplength=380, justify="left").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        # red error line (filled by redraw)
        self.clock_err = self._note(box, "#b8323f", row=3, column=0, columnspan=2)

        # ==== block 'Peaks and troughs' (green) ====
        # Two radio buttons choose the input; the time-series controls are shown only in that mode.
        # peaks and troughs: typed in, or detected in time-series data
        box = self._box(root, "Peaks and troughs (hours after 0 h)", "rec")
        modes = ttk.Frame(box)
        modes.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        for value, text in (("times", "Enter the peak and trough times"),
                            ("series", "Detect them in time-series data (e.g. bioluminescence)")):
            ttk.Radiobutton(modes, text=text, value=value, variable=self.input_mode_var,
                            command=self._input_mode_changed).pack(anchor="w")
        # the time-series data box and the detection settings (see _build_series_controls)
        self.series_frame = ttk.Frame(box)
        self.series_frame.grid(row=1, column=0, columnspan=2, sticky="we", pady=(0, 6))
        self._build_series_controls(self.series_frame)
        # the two lists: a Text widget each, with a coloured title and a count line below
        self.texts, self.count_vars, self.list_titles = {}, {}, {}
        for col, (key, title, color) in enumerate((("peaks", "Peaks (h)", PEAK_COLOR),
                                                   ("troughs", "Troughs (h)", TROUGH_COLOR))):
            tv = tk.StringVar(value="● " + title)
            ttk.Label(box, textvariable=tv, foreground=color).grid(row=2, column=col, sticky="w")
            self.list_titles[key] = (tv, title)
            # undo=True gives Ctrl+Z / Ctrl+Y in the lists
            txt = tk.Text(box, width=16, height=10, undo=True, font="TkFixedFont")
            txt.grid(row=3, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0))
            # <<Modified>> fires when the user edits the text
            txt.bind("<<Modified>>", lambda _e, t=txt: self._text_changed(t))
            self.texts[key] = txt
            var = tk.StringVar()
            ttk.Label(box, textvariable=var, foreground="#666666").grid(row=4, column=col, sticky="w")
            self.count_vars[key] = var
        box.columnconfigure(0, weight=1)
        box.columnconfigure(1, weight=1)
        # hint under the lists (changes with the input mode)
        self.list_hint = tk.StringVar()
        ttk.Label(box, textvariable=self.list_hint, foreground="#666666", wraplength=380, justify="left").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))
        # buttons: Load example, Clear data, Clear all
        line = ttk.Frame(box)
        line.grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(line, text="Load example", command=self.load_example).pack(side="left")
        ttk.Button(line, text="Clear data", command=self.clear_data).pack(side="left", padx=(6, 0))
        ttk.Button(line, text="Clear all", command=self.clear_all).pack(side="left", padx=(6, 0))
        ttk.Label(box, text="Clear data empties the peak and trough lists (Ctrl+Z in a list brings the values "
                            "back) or, with time-series data, the time series and its hand edits. Clear all also "
                            "blanks the clock time of 0 h, the sample placement and the LD start dates, and "
                            "resets the cycles to LD 12:00 / 12:00 followed by LL.",
                  foreground="#666666", wraplength=380, justify="left").grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # LD cycles
        # ==== block 'Sample placement' (green) ====
        box = self._box(root, "Sample placement", "rec")
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text="Placed at").grid(row=0, column=0, sticky="w")
        # clearable: the placement is optional
        DateTimeField(box, self.placed_var, self.tz_var.get, title="Sample placed at",
                      clearable=True).grid(row=0, column=1, sticky="w", padx=(6, 0))
        ttk.Label(box, text="Date and time when the samples were put into the light/dark conditions "
                            "(LL, DD or LD). It is marked with an orange asterisk in the actogram (0 h of "
                            "the data: green asterisk). Leave it empty if not needed.",
                  foreground="#666666", wraplength=380, justify="left").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        # error and information lines
        self.placed_err = self._note(box, "#b8323f", row=2, column=0, columnspan=2)
        self.placed_info = self._note(box, "#1f5fa8", row=3, column=0, columnspan=2)

        # ==== block 'Light/dark conditions' (green) ====
        # Up to 1 + MAX_CHANGES condition cards; redraw() shows only the used ones.
        box = self._box(root, "Light/dark conditions", "rec")
        box.columnconfigure(0, weight=1)
        ttk.Checkbutton(box, text="Show the light/dark conditions in the actogram",
                        variable=self.show_ld_var).grid(row=0, column=0, sticky="w")
        cards = ttk.Frame(box)
        cards.grid(row=1, column=0, sticky="we", pady=(4, 0))
        cards.columnconfigure(0, weight=1)
        self.cycle_widgets = []
        # one card per possible condition
        for i, cv in enumerate(self.cycle_vars):
            name = f"Condition {i + 1}"
            # a thin-bordered frame for the card
            card = tk.Frame(cards, highlightthickness=1, highlightbackground="#c9d1d9", padx=6, pady=5)
            card.grid(row=i, column=0, sticky="we", pady=3)
            row1 = ttk.Frame(card)
            row1.pack(fill="x")
            # row 1: mode (LD/LL/DD), then for LD: L, D and 'Light first / Dark first'
            ttk.Combobox(row1, textvariable=cv["mode"], values=LD_MODES, width=4,
                         state="readonly").pack(side="left")
            ld_part = ttk.Frame(row1)
            ttk.Label(ld_part, text="L", foreground="#666666").pack(side="left", padx=(6, 2))
            # L and D: hh:mm fields with the wheel pop-up (click to open)
            l_field = TimeField(ld_part, cv["L"], hours=100, width=6, button=False)
            l_field.pack(side="left")
            ttk.Label(ld_part, text="D", foreground="#666666").pack(side="left", padx=(6, 2))
            d_field = TimeField(ld_part, cv["D"], hours=100, width=6, button=False)
            d_field.pack(side="left")
            # the combobox shows 'Light first'/'Dark first'; the setting stores 'Light'/'Dark'
            phase_shown = tk.StringVar(value="Light first")
            phase_box = ttk.Combobox(ld_part, textvariable=phase_shown, values=("Light first", "Dark first"),
                                     width=10, state="readonly")
            phase_box.pack(side="left", padx=(6, 0))
            phase_box.bind("<<ComboboxSelected>>",
                           lambda _e, c=cv, v=phase_shown: c["phase"].set("Light" if v.get().startswith("Light") else "Dark"))
            # row 2: start date/time (with suggestions from the previous LD for cards 2..6) and the x button
            row2 = ttk.Frame(card)
            row2.pack(fill="x", pady=(5, 0))
            ttk.Label(row2, text="Starts at", foreground="#666666").pack(side="left", padx=(0, 6))
            DateTimeField(row2, cv["start"], self.tz_var.get, compact=True, title=f"{name} \u2013 start",
                          suggestions=(lambda k=i: self.start_suggestions(k)) if i > 0 else None).pack(side="left")
            remove = ttk.Button(row2, text="\u00d7", width=3, command=lambda k=i: self.remove_condition(k))
            remove.pack(side="right")
            # remember the widgets that redraw() shows, hides or updates
            self.cycle_widgets.append({"card": card, "ld_part": ld_part, "phase_shown": phase_shown,
                                       "remove": remove, "L": l_field, "D": d_field})
        # add a card / extend the first condition backwards
        self.add_condition_button = ttk.Button(box, text="Add condition", command=self.add_condition)
        self.add_condition_button.grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Checkbutton(box, text="Extend the first condition before its start time",
                        variable=self.extend_var).grid(row=3, column=0, sticky="w", pady=(6, 0))
        # error and information lines under the cards
        self.ld_err = self._note(box, "#b8323f", row=4, column=0)
        self.ld_info = self._note(box, "#1f5fa8", row=5, column=0)
        ttk.Label(box, text="LD uses L, D and the period it begins with; LL is constant light, DD constant "
                            "darkness. Each condition lasts until the next one starts. Click L or D to pick "
                            "the length with the mouse wheel. After an LD condition, the Starts at picker of "
                            "the next one lists the ends of D (for LL, or LD with Light first) or of L (for "
                            "DD, or LD with Dark first).",
                  foreground="#666666", wraplength=380, justify="left").grid(row=6, column=0, sticky="w", pady=(4, 0))

        # ==== block 'Actogram day 0, 0 h' (blue) ====
        # Six radio buttons; 'Another date/time' uses the date/time field below them.
        # origin
        box = self._box(root, "Actogram day 0, 0 h (left end of the top row)", "disp")
        for r, (value, text) in enumerate((("clock", "0 h of the data (time zero)"),
                                           ("zero_midnight", "00:00 (midnight) on the day of 0 h of the data"),
                                           ("lights_on", "Light-on of the first LD cycle on its start date "
                                                         "(LL/DD: its start)"),
                                           ("first_midnight", "00:00 (midnight) on the day the first "
                                                              "LD/LL/DD started"),
                                           ("placed_midnight", "00:00 (midnight) on the day the sample "
                                                               "was placed"),
                                           ("custom", "Another date/time:"))):
            ttk.Radiobutton(box, text=text, value=value, variable=self.origin_var).grid(
                row=r, column=0, sticky="w", pady=1)
        self.origin_entry = DateTimeField(box, self.origin_time_var, self.tz_var.get,
                                          title="Actogram day 0, 0 h", clearable=True)
        self.origin_entry.grid(row=7, column=0, columnspan=2, sticky="w", padx=(22, 0), pady=(0, 2))
        self.origin_err = self._note(box, "#b8323f", row=8, column=0, columnspan=2)
        self.origin_info = self._note(box, "#1f5fa8", row=9, column=0, columnspan=2)

        # ==== block 'Plot' (blue) ====
        # plot options
        box = self._box(root, "Plot", "disp")
        # title of the figure
        ttk.Label(box, text="Title").grid(row=0, column=0, sticky="w")
        ttk.Entry(box, textvariable=self.title_var, width=34).grid(row=0, column=1, columnspan=3, sticky="we", pady=2)
        # period T with the wheel pop-up and a 'reset to 24:00' button
        ttk.Label(box, text="Period T (hh:mm)").grid(row=1, column=0, sticky="w")
        period_line = ttk.Frame(box)
        period_line.grid(row=1, column=1, sticky="w", pady=2)
        TimeField(period_line, self.period_var, hours=PERIOD_MAX_MIN // 60 + 1, min_hour=0, width=6,
                  max_minutes=PERIOD_MAX_MIN, min_minutes=PERIOD_MIN_MIN, default=(24, 0)).pack(side="left")
        ttk.Button(period_line, text="\u21ba 24:00", width=8,                    # one click back to T = 24:00
                   command=lambda: self.period_var.set(DEFAULT_PERIOD)).pack(side="left", padx=(6, 0))
        self.period_err = self._note(box, "#b8323f", row=1, column=2, columnspan=2)
        # double/single plot and row labels
        ttk.Label(box, text="Plot").grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(box, text="Double", value="double", variable=self.plot_var).grid(row=2, column=1, sticky="w")
        ttk.Radiobutton(box, text="Single", value="single", variable=self.plot_var).grid(row=2, column=2, sticky="w")
        ttk.Label(box, text="Row labels").grid(row=3, column=0, sticky="w")
        ttk.Radiobutton(box, text="Number", value="number", variable=self.rowlab_var).grid(row=3, column=1, sticky="w")
        ttk.Radiobutton(box, text="Date", value="date", variable=self.rowlab_var).grid(row=3, column=2, sticky="w")
        # show times / connect peaks / connect troughs
        ttk.Checkbutton(box, text="Show times", variable=self.show_values_var).grid(row=4, column=0, sticky="w")
        ttk.Checkbutton(box, text="Connect peaks", variable=self.link_peak_var).grid(row=4, column=1, sticky="w")
        ttk.Checkbutton(box, text="Connect troughs", variable=self.link_trough_var).grid(row=4, column=2, sticky="w")
        # optional labels
        ttk.Checkbutton(box, text="Label the start times of light and dark periods",
                        variable=self.label_onsets_var).grid(row=5, column=0, columnspan=4, sticky="w")
        ttk.Checkbutton(box, text="Label the start date/time of each cycle (y axis)",
                        variable=self.label_row_starts_var).grid(row=6, column=0, columnspan=4, sticky="w")
        # major and minor x ticks
        ttk.Label(box, text="X major ticks").grid(row=7, column=0, sticky="w", pady=(4, 0))
        ttk.Combobox(box, textvariable=self.x_major_var, values=X_MAJOR_CHOICES, state="readonly",
                     width=36, height=len(X_MAJOR_CHOICES)).grid(row=7, column=1, columnspan=3,
                                                                  sticky="w", pady=(4, 0))
        ttk.Label(box, text="X minor ticks").grid(row=8, column=0, sticky="w", pady=(4, 0))
        ttk.Combobox(box, textvariable=self.x_minor_var, values=X_MINOR_CHOICES, state="readonly",
                     width=36, height=len(X_MINOR_CHOICES)).grid(row=8, column=1, columnspan=3,
                                                                  sticky="w", pady=(4, 0))
        # asterisks and condition-change lines
        ttk.Checkbutton(box, text="Mark 0 h of the data (green *) and the sample placement (orange *)",
                        variable=self.mark_times_var).grid(row=9, column=0, columnspan=4, sticky="w", pady=(4, 0))
        ttk.Checkbutton(box, text="Mark condition changes (light-purple lines)",
                        variable=self.mark_changes_var).grid(row=12, column=0, columnspan=4, sticky="w", pady=(4, 0))
        # colour swatches: clicking one stores its hex code in the variable
        # colours of the light and dark bands: 12 swatches each
        self.swatches = []
        for r, (title, palette, var) in enumerate((("Light colour", LIGHT_COLORS, self.light_color_var),
                                                   ("Dark colour", DARK_COLORS, self.dark_color_var))):
            ttk.Label(box, text=title).grid(row=10 + r, column=0, sticky="w", pady=(6, 0))
            row_frame = ttk.Frame(box)
            row_frame.grid(row=10 + r, column=1, columnspan=3, sticky="w", pady=(6, 0))
            for name, hex_code in palette:
                sw = tk.Label(row_frame, background=hex_code, width=2, height=1, cursor="hand2",
                              highlightthickness=2, highlightbackground="#ffffff", relief="solid", borderwidth=1)
                sw.pack(side="left", padx=1)
                # c=hex_code binds the current colour into the lambda
                sw.bind("<Button-1>", lambda _e, v=var, c=hex_code: v.set(c))
                self.swatches.append((sw, var, hex_code))
                Tooltip(sw, name)
            name_var = tk.StringVar()
            ttk.Label(row_frame, textvariable=name_var, foreground="#555555").pack(side="left", padx=(8, 0))
            # an extra entry (sw=None) for the name label after each palette (updated in redraw)
            self.swatches.append((None, var, (name_var, palette)))
        # show/hide the peak and trough points
        ttk.Checkbutton(box, text="Show the peak and trough points",
                        variable=self.show_points_var).grid(row=13, column=0, columnspan=4, sticky="w", pady=(4, 0))
        # drawing the time series in the actogram: None / Activity bars / Heat map, Raw / Detrended
        ttk.Label(box, text="Time series").grid(row=14, column=0, sticky="w", pady=(6, 0))
        line = ttk.Frame(box)
        line.grid(row=14, column=1, columnspan=3, sticky="w", pady=(6, 0))
        self.ts_draw_box = ttk.Combobox(line, textvariable=self.ts_draw_var, values=[n for _, n in TS_DRAW_MODES],
                                        state="readonly", width=13)
        self.ts_draw_box.pack(side="left")
        self.ts_draw_radios = []
        for value, text in (("raw", "Raw"), ("detrended", "Detrended")):
            rb = ttk.Radiobutton(line, text=text, value=value, variable=self.ts_draw_data_var)
            rb.pack(side="left", padx=(8, 0))
            self.ts_draw_radios.append(rb)
        # scale: the whole record or each row
        ttk.Label(box, text="Scale").grid(row=15, column=0, sticky="w", pady=(3, 0))
        self.ts_draw_scale_box = ttk.Combobox(box, textvariable=self.ts_draw_scale_var,
                                              values=[n for _, n in TS_DRAW_SCALES], state="readonly", width=13)
        self.ts_draw_scale_box.grid(row=15, column=1, columnspan=3, sticky="w", pady=(3, 0))
        # explanation line (filled by _update_series_controls)
        self.ts_draw_note = tk.StringVar()
        ttk.Label(box, textvariable=self.ts_draw_note, foreground="#666666", wraplength=370, justify="left").grid(
            row=16, column=0, columnspan=4, sticky="w", pady=(2, 0))
        box.columnconfigure(3, weight=1)

    def _build_series_controls(self, root):
        """Time-series input and the detection settings (shown in the time-series mode)."""
        root.columnconfigure(0, weight=1)
        ttk.Label(root, text="Time series: one row per time point \u2013 time and signal, separated by tabs, "
                             "spaces or commas. Time = hours after 0 h, or a date and time (ISO 8601, e.g. "
                             "2026-10-05T10:15:00-0500 or 20261005T1015; without an offset: the time zone of "
                             "the data). Header lines are skipped.",
                  foreground="#666666", wraplength=380, justify="left").grid(row=0, column=0, sticky="w")
        # the data box: a Text widget (no line wrapping) with a vertical scrollbar
        frame = ttk.Frame(root)
        frame.grid(row=1, column=0, sticky="we", pady=(3, 0))
        frame.columnconfigure(0, weight=1)
        self.series_text = tk.Text(frame, width=34, height=8, undo=True, font="TkFixedFont", wrap="none")
        self.series_text.grid(row=0, column=0, sticky="we")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.series_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.series_text.configure(yscrollcommand=scroll.set)
        # edits in the box trigger a redraw
        self.series_text.bind("<<Modified>>", lambda _e: self._text_changed(self.series_text))
        # buttons: open a file, load example 1, show the plot window
        line = ttk.Frame(root)
        line.grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Button(line, text="Open file\u2026", command=self.open_series_file).pack(side="left")
        ttk.Button(line, text="Load example series", command=self.load_example_series).pack(side="left", padx=(6, 0))
        ttk.Button(line, text="Show plot", command=self.show_series_window).pack(side="left", padx=(6, 0))
        # example 2 and the Clear buttons
        line2 = ttk.Frame(root)
        line2.grid(row=3, column=0, sticky="w", pady=(4, 0))
        ttk.Button(line2, text="Example 2 (date/time)", command=self.load_example2_series).pack(side="left", padx=(0, 6))
        ttk.Button(line2, text="Clear data", command=self.clear_data).pack(side="left")
        ttk.Button(line2, text="Clear all", command=self.clear_all).pack(side="left", padx=(6, 0))
        # blue information / red error lines of the analysis
        self.ts_info = self._note(root, "#1f5fa8", row=4, column=0)
        self.ts_err = self._note(root, "#b8323f", row=5, column=0)

        # the detection settings frame
        det = ttk.LabelFrame(root, text="Peak/trough detection", padding=(8, 4))
        det.grid(row=6, column=0, sticky="we", pady=(6, 0))
        # short name for the dict of detection-setting variables
        v = self.ts_vars
        # raw or detrended data
        ttk.Label(det, text="Detect in").grid(row=0, column=0, sticky="w")
        src = ttk.Frame(det)
        src.grid(row=0, column=1, columnspan=3, sticky="w")
        ttk.Radiobutton(src, text="Raw data", value="raw", variable=v["ts_source"]).pack(side="left")
        ttk.Radiobutton(src, text="Detrended data", value="detrended", variable=v["ts_source"]).pack(side="left", padx=(8, 0))
        # detrending method
        ttk.Label(det, text="Detrending").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.ts_method_box = ttk.Combobox(det, textvariable=v["ts_method"], values=TS_METHODS,
                                          state="readonly", width=15)
        self.ts_method_box.grid(row=1, column=1, columnspan=3, sticky="w", pady=(4, 0))
        # numeric settings as spinboxes: (setting key, label, minimum, maximum, step)
        self.ts_spins = {}
        for r, (key, text, lo, hi, step) in enumerate((("ts_sinc_cutoff", "Cutoff period (h)", 1, 240, 1),
                                                      ("ts_sinc_order", "Filter order", 3, 999, 2),
                                                      ("ts_ma_window", "Trend window (h)", 1, 240, 1),
                                                      ("ts_min_sep", "Min. peak spacing (h)", 1, 240, 1))):
            ttk.Label(det, text=text).grid(row=2 + r, column=0, sticky="w", pady=(3, 0))
            spin = ttk.Spinbox(det, from_=lo, to=hi, increment=step, width=7, textvariable=v[key], justify="right")
            spin.grid(row=2 + r, column=1, sticky="w", pady=(3, 0), padx=(4, 0))
            self.ts_spins[key] = spin
        # width of the moving average of the detection line
        ttk.Label(det, text="Line: moving average").grid(row=6, column=0, sticky="w", pady=(3, 0))
        smooth_line = ttk.Frame(det)
        smooth_line.grid(row=6, column=1, columnspan=3, sticky="w", pady=(3, 0), padx=(4, 0))
        ttk.Combobox(smooth_line, textvariable=v["ts_smooth"], values=[str(n) for n in TS_SMOOTH_CHOICES],
                     state="readonly", width=4).pack(side="left")
        ttk.Label(smooth_line, text="points (default 7; 1 = no moving average)", foreground="#666666").pack(side="left", padx=(6, 0))
        # explanation of the method
        ttk.Label(det, text="Peaks and troughs are the maxima and minima of the line: the raw data (default) or "
                            "the detrended data (data \u2212 trend), after a centred moving average (default "
                            "7 points; 1 = none), at least the minimum spacing apart (default 12 h). Sinc Filter: "
                            "windowed-sinc low-pass (Hamming), applied forwards and backwards; default cutoff "
                            "48 h, order 101. Moving Average trend: centred window (Trend window), default 24 h. Unequal intervals "
                            "are resampled onto a regular grid first.",
                  foreground="#666666", wraplength=370, justify="left").grid(
            row=7, column=0, columnspan=4, sticky="w", pady=(4, 0))
        # 'Reset manual edits' and the number of edits
        edits = ttk.Frame(det)
        edits.grid(row=8, column=0, columnspan=4, sticky="w", pady=(4, 0))
        ttk.Button(edits, text="Reset manual edits", command=self.reset_ts_edits).pack(side="left")
        self.ts_edit_info = tk.StringVar()
        ttk.Label(edits, textvariable=self.ts_edit_info, foreground="#1f5fa8").pack(side="left", padx=(8, 0))

    def _input_mode_changed(self):
        """Radio button 'peak and trough times' / 'time-series data' clicked."""
        # a mode switch forgets which values were deliberately deselected
        self._ts_deselected = set()
        if self.input_mode_var.get() == "series":
            # switching to series: keep the typed lists so switching back restores them
            if self._times_backup is None:       # keep the typed lists (this session) to come back to
                self._times_backup = {k: self.texts[k].get("1.0", "end-1c") for k in ("peaks", "troughs")}
                self._times_backup["selection"] = {k: list(v) for k, v in self.selection.items()}
            self.show_series_window()
        # switching back to typed times: restore the lists kept above
        elif self._times_backup is not None:
            b, self._times_backup = self._times_backup, None
            for key in ("peaks", "troughs"):
                self._set_text(self.texts[key], b[key], readonly=False)
            self.selection = b["selection"]
        self.schedule()

    def _set_text(self, txt: tk.Text, text: str, readonly: bool):
        """Replace the text of a Text widget without triggering a redraw loop, and set it read-only or editable."""
        # _writing tells _text_changed() to ignore this programmatic change
        current = txt.get("1.0", "end-1c")
        # a read-only Text must be made writable before it can be changed
        txt.configure(state="normal")
        if current != text:
            self._writing = True
            try:
                txt.delete("1.0", "end")
                txt.insert("1.0", text)
                # a new value cannot be undone into the old one
                txt.edit_reset()
                txt.edit_modified(False)
            finally:
                self._writing = False
        txt.configure(state="disabled" if readonly else "normal")

    def _write_detected(self, ts: dict):
        """Detected peaks/troughs -> the two lists; the selection for the phase analysis follows:
        new values are selected, unless that value was deselected earlier in this session."""
        # for the peak list and the trough list:
        for key, kind, sel in (("peaks", "peak", "sel_peaks"), ("troughs", "trough", "sel_troughs")):
            # the values shown before this update
            old = parse_list(self.texts[key].get("1.0", "end-1c"))[0]
            # remember which of them the user had deselected (and forget values that were reselected)
            chosen = {k4(v) for v in self.selection[sel]}
            for v in old:
                (self._ts_deselected.discard if k4(v) in chosen else self._ts_deselected.add)((kind, k4(v)))
            # the new detected values
            text = series_text(ts, kind) if ts.get("ok") else ""
            new = parse_list(text)[0]
            # select every new value unless it was deselected before
            self.selection[sel] = [v for v in new if (kind, k4(v)) not in self._ts_deselected]
            # show them (read-only)
            self._set_text(self.texts[key], text, readonly=True)

    def show_series_window(self):
        """Open the time-series window (or bring it to the front)."""
        if self.series_win is None:
            self.series_win = SeriesWindow(self)
        else:
            self.series_win.show()
        self.schedule()

    def open_series_file(self):
        """Read a time-series text file (UTF-8, Shift-JIS or Latin-1) into the data box."""
        path = filedialog.askopenfilename(title="Open time-series data",
                                          filetypes=[("Text data", "*.txt *.csv *.tsv *.dat *.tab"),
                                                     ("All files", "*.*")])
        if not path:
            return
        # try the usual encodings of instrument exports: UTF-8 (with BOM), Japanese Windows, Latin-1
        raw = Path(path).read_bytes()
        for enc in ("utf-8-sig", "cp932", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        self._load_series(text)

    def load_example2_series(self):
        """Example 2: a record every 8 minutes with the date and time (ISO 8601) in column 1 and
        its own schedule (LD 12:12, LL, LD 11.5:11.5, DD); the sinc filter order is raised to
        suit the shorter sampling interval."""
        self.load_example_series(example2_series_text(), {"ts_sinc_order": EXAMPLE2_ORDER}, example2_settings())

    def load_example_series(self, text: str | None = None, extra: dict | None = None,
                            conditions: dict | None = None):
        """The example time series together with the clock time, sample placement and
        light/dark conditions of the example (LD 12:12 -> LD 15:15 -> LL); display options
        are kept, the detection settings return to their defaults."""
        # is there any data that would be replaced?
        has = self.series_text.get("1.0", "end-1c").strip() or any(
            self.texts[k].get("1.0", "end-1c").strip() for k in ("peaks", "troughs"))
        if has and not messagebox.askyesno(
                APP_NAME, "Replace the current data with the example time series?\n\nThe clock time of 0 h, "
                          "the sample placement, the LD cycles and the detection settings are replaced by those "
                          "of the example; display options are kept.", parent=self):
            return
        # start from the current settings (keeps display options), overwrite data, conditions and detection
        settings = self.get_settings()
        settings.update(conditions or example_settings())
        settings.update(TS_DEFAULTS)
        settings.update(input_mode="series", series=text or example_series_text(), ts_edits=empty_edits())
        settings.update(extra or {})
        # fill all controls
        self.apply_settings(settings)
        ex = example_settings()
        # 'Enter the times' then shows the typed example lists (example 1 only)
        self._times_backup = None if conditions else {
            "peaks": ex["peaks"], "troughs": ex["troughs"],
            "selection": {"sel_peaks": list(ex["sel_peaks"]), "sel_troughs": list(ex["sel_troughs"])}}
        self.show_series_window()

    def _load_series(self, text: str):
        """Put new time-series text into the data box (asks before replacing other data)."""
        current = self.series_text.get("1.0", "end-1c").strip()
        if current and current != text.strip() and not messagebox.askyesno(
                APP_NAME, "Replace the current time-series data?", parent=self):
            return
        # hand edits belong to the old data
        if edit_count(self.ts_edits) and current != text.strip():
            self.ts_edits = empty_edits()
        self.series_text.delete("1.0", "end")
        self.series_text.insert("1.0", text)
        # loading a series implies the series input
        if self.input_mode_var.get() != "series":
            self.input_mode_var.set("series")
            self._input_mode_changed()
        else:
            self.show_series_window()

    def ts_remove(self, kind: str, index: int):
        """Called by the time-series window: remove a detected peak/trough by hand."""
        if self.ts and self.ts.get("ok"):
            self.ts_edits = edit_remove(self.ts_edits, self.ts, kind, index)
            self.schedule()

    def ts_add(self, kind: str, index: int):
        """Called by the time-series window: add a peak/trough by hand."""
        if self.ts and self.ts.get("ok"):
            self.ts_edits = edit_add(self.ts_edits, self.ts, kind, index)
            self.schedule()

    def reset_ts_edits(self):
        """Discard all hand edits (asks first)."""
        if not edit_count(self.ts_edits):
            return
        parent = self.series_win.win if self.series_win is not None else self
        if messagebox.askyesno(APP_NAME, "Discard all hand edits of the peaks and troughs and go back to the "
                                         "automatic detection?", parent=parent):
            self.ts_edits = empty_edits()
            self.schedule()

    def _update_series_controls(self, st: dict):
        """Show/hide and enable/disable the time-series controls for the current mode and refresh their messages."""
        series = st["input_mode"] == "series"
        drawing = st.get("ts_draw", "none") != "none"
        # the drawing options are only available with time-series input
        self.ts_draw_box.state(["!disabled", "readonly"] if series else ["disabled"])
        for w in self.ts_draw_radios:
            w.state(["!disabled"] if series and drawing else ["disabled"])
        self.ts_draw_scale_box.state(["!disabled", "readonly"] if series and drawing else ["disabled"])
        note = ""
        # the explanation line under the drawing options
        if not series:
            note = "Time series: only with \u2018Detect them in time-series data\u2019."
        elif drawing and self.ts is not None and self.ts.get("ok") and st.get("ts_draw_data") == "detrended" \
                and self.ts.get("trend") is None:
            note = "Detrended data cannot be drawn: " + (self.ts.get("trend_error") or "no trend.")
        elif drawing:
            note = ("Activity: bar height = signal (1st\u201399th percentile). " if st["ts_draw"] == "activity" else
                    "Heat map: colour = signal (1st\u201399th percentile; detrended: symmetric around 0). ") + \
                   "The detrending settings of the time series are used for detrended data."
        self.ts_draw_note.set(note)
        # show the data box and the detection settings only in series mode
        self.series_frame.grid() if series else self.series_frame.grid_remove()
        # list titles say whether the values were detected
        for key, (var, title) in self.list_titles.items():
            var.set("● " + title + ("  \u2013 detected" if series else ""))
        # typed-times mode: lists are editable
        if not series:
            for key in ("peaks", "troughs"):
                self.texts[key].configure(state="normal")
            self.list_hint.set("One value per line. Paste a column from a spreadsheet. Negative values are allowed.")
            return
        # messages of the analysis
        ts = self.ts or {}
        self.ts_info.set(ts.get("info", ""))
        self.ts_err.set(ts.get("error", ""))
        # the detrending settings matter when detecting in detrended data or drawing detrended data
        detrended = st["ts_source"] != "raw" or (drawing and st.get("ts_draw_data") == "detrended")
        moving = st["ts_method"] == "Moving Average"
        self.ts_method_box.state(["!disabled", "readonly"] if detrended else ["disabled"])
        for key, spin in self.ts_spins.items():
            # the spacing always matters; cutoff/order only for Sinc Filter; window only for Moving Average
            on = key == "ts_min_sep" or (detrended and ((key == "ts_ma_window") == moving))
            spin.state(["!disabled"] if on else ["disabled"])
        n = edit_count(self.ts_edits)
        self.ts_edit_info.set(f"{n} hand edit{'s' if n != 1 else ''}" if n else "No hand edits")
        self.list_hint.set("Detected automatically from the time series (read-only here). Click markers in "
                           "the time-series plot (Show plot) to remove or add peaks and troughs.")

    # ---------------- right panel ----------------
    def _build_plot(self, root):
        """Right panel: matplotlib toolbar and canvas for the actogram, the fine-tune panel above it and the phase analysis below."""
        # the actogram figure and its canvas; the standard matplotlib toolbar (zoom, pan, save)
        self.fig = Figure(figsize=(10, 6.2), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        toolbar_frame = ttk.Frame(root)
        toolbar_frame.pack(side="top", fill="x")
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()
        ttk.Button(toolbar_frame, text="Save figure…", command=self.save_figure).pack(side="right", padx=4)

        # fine-tuning above the actogram, phase analysis below it
        # fine-tune panel above the actogram and phase analysis below it
        tune = ttk.LabelFrame(root, text="Fine-tune the plot (1-minute steps)", padding=(8, 0, 8, 2))
        tune.pack(side="top", fill="x", pady=(0, 4))
        ana = ttk.LabelFrame(root, text="Phase analysis", padding=(10, 6))
        ana.pack(side="bottom", fill="x", pady=(6, 0))
        self._build_analysis(ana)
        # mouse events of the actogram: click/drag selection
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        # _press: the mouse press in progress; hits: positions of the drawn points (from draw_actogram)
        self._press = None
        self.hits = []
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        # ==== fine-tune panel: one line each for day 0 and period T, then the rows ====
        self.tune_vals, self.scales = {}, {}
        small = ("TkDefaultFont", 8)
        blue = FRAME_KINDS["disp"][0]
        # one compact line per control: name, -1h -10 -1, slider, +1 +10 +1h, value
        # for each of the two controls: name, -1h/-10/-1 buttons, slider, +1/+10/+1h buttons, value
        for r, (key, title) in enumerate((("origin", "Day 0, 0 h"), ("period", "Period T"))):
            tk.Label(tune, text=title, foreground=blue, anchor="w", width=10,
                     font=("TkDefaultFont", 9, "bold")).grid(row=r, column=0, sticky="w")
            for c, (text, d) in enumerate((("\u22121h", -60), ("\u221210", -10), ("\u22121", -1))):
                # repeatdelay/repeatinterval: holding a button repeats it
                tk.Button(tune, text=text, width=4, font=small, pady=0, repeatdelay=400, repeatinterval=70,
                          command=lambda k=key, dd=d: self.nudge(k, dd)).grid(row=r, column=1 + c, padx=0, pady=1)
            common = dict(orient="horizontal", showvalue=False, resolution=1, width=10, sliderlength=18,
                          borderwidth=0, highlightthickness=0)
            # period slider: absolute value in minutes (0:01 .. 240:00)
            if key == "period":
                scale = tk.Scale(tune, from_=PERIOD_MIN_MIN, to=PERIOD_MAX_MIN,
                                 command=lambda v: self._period_scale(v), **common)
            # day-0 slider: relative, -12 h .. +12 h from where the drag started; it snaps back to the
            # centre when released (see _shift_scale / _reset_scale)
            else:
                scale = tk.Scale(tune, from_=-720, to=720, command=lambda v, k=key: self._shift_scale(k, v), **common)
                scale.bind("<ButtonRelease-1>", lambda _e, k=key: self._reset_scale(k))
                scale.bind("<FocusOut>", lambda _e, k=key: self._reset_scale(k))
            scale.grid(row=r, column=4, sticky="we", padx=6)
            self.scales[key] = scale
            for c, (text, d) in enumerate((("+1", 1), ("+10", 10), ("+1h", 60))):
                tk.Button(tune, text=text, width=4, font=small, pady=0, repeatdelay=400, repeatinterval=70,
                          command=lambda k=key, dd=d: self.nudge(k, dd)).grid(row=r, column=5 + c, padx=0, pady=1)
            var = tk.StringVar()
            ttk.Label(tune, textvariable=var, foreground="#1f5fa8", width=31, font=small).grid(
                row=r, column=8, sticky="w", padx=(6, 0))
            self.tune_vals[key] = var
        # rows: Automatic, or Min/Max spinboxes
        tk.Label(tune, text="Rows", foreground=blue, anchor="w", width=10,
                 font=("TkDefaultFont", 9, "bold")).grid(row=2, column=0, sticky="w")
        rows_line = ttk.Frame(tune)
        rows_line.grid(row=2, column=1, columnspan=8, sticky="w", pady=(1, 0))
        ttk.Checkbutton(rows_line, text="Automatic", variable=self.rows_auto_var,
                        command=self._rows_auto_toggled).pack(side="left")
        self.row_spins = []
        for text, var in (("Min", self.row_min_var), ("Max", self.row_max_var)):
            ttk.Label(rows_line, text=f"  {text}").pack(side="left")
            spin = ttk.Spinbox(rows_line, from_=-9999, to=9999, increment=1, width=6,
                               textvariable=var, justify="right")
            spin.pack(side="left", padx=(4, 0))
            # mouse wheel and arrow keys step the spinboxes
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                spin.bind(sequence, lambda e, v=var, sp=spin: self._spin_wheel(e, v, sp))
            spin.bind("<Up>", lambda _e, v=var, sp=spin: self._spin_step(v, sp, 1))
            spin.bind("<Down>", lambda _e, v=var, sp=spin: self._spin_step(v, sp, -1))
            self.row_spins.append(spin)
        # rows information (blue) and notes (red)
        self.rows_info = tk.StringVar()
        ttk.Label(rows_line, textvariable=self.rows_info, foreground="#1f5fa8", font=small).pack(side="left", padx=(10, 0))
        self.rows_note = tk.StringVar()
        ttk.Label(rows_line, textvariable=self.rows_note, foreground="#b8323f", font=small).pack(side="left", padx=(10, 0))
        tune.columnconfigure(4, weight=1)

    # ---------------- settings in / out ----------------
    def get_settings(self) -> dict:
        """Read every control into one settings dict (the format of the settings file)."""
        # Every key below is also a key of the JSON settings file.  Values are read as they are shown
        # (strings for entries); compute() and the other functions validate them.
        return {
            "t0": self.t0_var.get(), "tz": self.tz_var.get(),
            "peaks": self.texts["peaks"].get("1.0", "end-1c"),
            "troughs": self.texts["troughs"].get("1.0", "end-1c"),
            "show_ld": self.show_ld_var.get(), "extend_before": self.extend_var.get(),
            "n_changes": int(self.n_changes_var.get() or 0),
            # one dict per condition card
            "cycles": [{k: v.get() for k, v in cv.items()} for cv in self.cycle_vars],
            "origin": self.origin_var.get(), "origin_time": self.origin_time_var.get(),
            "title": self.title_var.get(), "period": self.period_var.get(),
            "plot": self.plot_var.get(), "rowlab": self.rowlab_var.get(),
            "show_values": self.show_values_var.get(),
            "link_peak": self.link_peak_var.get(), "link_trough": self.link_trough_var.get(),
            "rows_auto": self.rows_auto_var.get(),
            "x_major": self.x_major_var.get(),
            "light_color": self.light_color_var.get(), "dark_color": self.dark_color_var.get(),
            # the selection is kept in self.selection (not in a Tk variable)
            "sel_peaks": list(self.selection["sel_peaks"]), "sel_troughs": list(self.selection["sel_troughs"]),
            # the combobox shows the text; the setting stores the short key
            "phase_ref": next((k for k, t in PHASE_REFS if t == self.phase_ref_var.get()), "zt0_prev"),
            "draw_fit": self.draw_fit_var.get(), "drag_mode": self.drag_mode_var.get(),
            "sel_target": self.sel_target_var.get(),
            "x_minor": self.x_minor_var.get(),
            "placed": self.placed_var.get(),
            "mark_times": self.mark_times_var.get(),
            "mark_changes": self.mark_changes_var.get(),
            "label_onsets": self.label_onsets_var.get(),
            "label_row_starts": self.label_row_starts_var.get(),
            "row_min": self.row_min_var.get(), "row_max": self.row_max_var.get(),
            # time-series input and its options (combobox texts are translated back into stored keys)
            "input_mode": "series" if self.input_mode_var.get() == "series" else "times",
            "ts_draw": next((c for c, n in TS_DRAW_MODES if n == self.ts_draw_var.get()), "none"),
            "ts_draw_data": "detrended" if self.ts_draw_data_var.get() == "detrended" else "raw",
            "ts_draw_scale": next((c for c, n in TS_DRAW_SCALES if n == self.ts_draw_scale_var.get()), "all"),
            "show_points": bool(self.show_points_var.get()),
            "series": self.series_text.get("1.0", "end-1c"),
            "ts_edits": clean_edits(self.ts_edits),
            # detection settings; ts_source/ts_method are not stripped (they come from fixed lists)
            **{k: (v.get() if k in ("ts_source", "ts_method") else v.get().strip()) for k, v in self.ts_vars.items()},
        }

    def apply_settings(self, s: dict):
        """Write a settings dict into the controls (missing keys take their defaults).  Redraws are
        suppressed while loading and done once at the end.
        """
        # start from the defaults, so settings files from older versions (missing keys) work
        d = default_settings()
        d.update(s or {})
        # suppress redraws while dozens of variables are set
        self._loading = True
        try:
            self.t0_var.set(d["t0"])
            # show the zone as its list entry if it is in the list
            self.tz_var.set(time_zone_display(d["tz"]))
            # the lists (made writable first, they may be read-only in series mode)
            for key in ("peaks", "troughs"):
                self.texts[key].configure(state="normal")
                self.texts[key].delete("1.0", "end")
                self.texts[key].insert("1.0", d[key])
                self.texts[key].edit_modified(False)
            # time-series input, data, hand edits and drawing options
            self.input_mode_var.set("series" if d.get("input_mode") == "series" else "times")
            self.series_text.delete("1.0", "end")
            self.series_text.insert("1.0", str(d.get("series", "") or ""))
            self.series_text.edit_modified(False)
            self.ts_edits = clean_edits(d.get("ts_edits"))
            self.ts_draw_var.set(dict(TS_DRAW_MODES).get(d.get("ts_draw"), "None"))
            self.ts_draw_data_var.set("detrended" if d.get("ts_draw_data") == "detrended" else "raw")
            self.ts_draw_scale_var.set(dict(TS_DRAW_SCALES).get(d.get("ts_draw_scale"), "Whole record"))
            self.show_points_var.set(bool(d.get("show_points", True)))
            # forget per-session memories that belong to the previous data
            self._ts_deselected = set()
            self._times_backup = None
            # detection settings, validated against the allowed values
            for k, var in self.ts_vars.items():
                value = str(d.get(k, TS_DEFAULTS[k]))
                if k == "ts_source" and value not in ("detrended", "raw"):
                    value = TS_DEFAULTS[k]
                if k == "ts_method" and value not in TS_METHODS:
                    value = TS_DEFAULTS[k]
                if k == "ts_smooth" and value not in [str(n) for n in TS_SMOOTH_CHOICES]:
                    value = TS_DEFAULTS[k]
                var.set(value)
            # light/dark conditions
            self.show_ld_var.set(bool(d["show_ld"]))
            self.extend_var.set(bool(d["extend_before"]))
            self.n_changes_var.set(max(0, min(MAX_CHANGES, int(d["n_changes"]))))
            # pad a shorter list of cycles (old files) with the defaults
            cycles = list(d["cycles"]) + default_settings()["cycles"][len(d["cycles"]):]
            for cv, c in zip(self.cycle_vars, cycles):
                for k in cv:
                    value = c.get(k, "")
                    # L and D are normalised to hh:mm
                    if k in ("L", "D"):
                        dur = parse_duration(value)
                        value = format_duration(dur).zfill(5) if math.isfinite(dur) else "12:00"
                    cv[k].set(value)
            # origin, title, period
            self.origin_var.set(d["origin"])
            self.origin_time_var.set(d["origin_time"])
            self.title_var.set(d["title"])
            period = d["period"]
            # older files may store the period as a number of hours
            if isinstance(period, (int, float)):
                period = format_duration(period)
            dur = parse_duration(period)
            self.period_var.set(f"{format_duration(dur).zfill(5)}" if math.isfinite(dur) and PERIOD_MIN_MIN <= round(dur * 60) <= PERIOD_MAX_MIN
                                else DEFAULT_PERIOD)
            # plot options
            self.plot_var.set(d["plot"])
            self.rowlab_var.set(d["rowlab"])
            self.show_values_var.set(bool(d["show_values"]))
            self.link_peak_var.set(bool(d["link_peak"]))
            self.link_trough_var.set(bool(d["link_trough"]))
            self.rows_auto_var.set(bool(d["rows_auto"]))
            self.x_major_var.set(X_MAJOR_CHOICES[x_major_count(d["x_major"])])
            self.light_color_var.set(pick_color(d.get("light_color"), LIGHT_COLORS))
            # the selection
            for key in ("sel_peaks", "sel_troughs"):
                vals = d.get(key, [])
                self.selection[key] = [float(v) for v in vals] if isinstance(vals, list) else []
            # phase-analysis and selection options
            self.phase_ref_var.set(dict(PHASE_REFS).get(d.get("phase_ref"), PHASE_REFS[0][1]))
            self.draw_fit_var.set(bool(d.get("draw_fit", True)))
            self.drag_mode_var.set(d.get("drag_mode") if d.get("drag_mode") in ("select", "deselect") else "select")
            self.sel_target_var.set(d.get("sel_target") if d.get("sel_target") in ("both", "peaks", "troughs") else "both")
            # remaining display options
            self.dark_color_var.set(pick_color(d.get("dark_color"), DARK_COLORS))
            self.x_minor_var.set(X_MINOR_CHOICES[x_minor_count(d["x_minor"])])
            self.placed_var.set(str(d.get("placed", "") or "").replace("T", " "))
            self.mark_times_var.set(bool(d.get("mark_times", True)))
            self.mark_changes_var.set(bool(d.get("mark_changes", True)))
            self.label_onsets_var.set(bool(d["label_onsets"]))
            self.label_row_starts_var.set(bool(d["label_row_starts"]))
            self.row_min_var.set(str(d["row_min"]))
            self.row_max_var.set(str(d["row_max"]))
        # always re-enable redraws, then redraw once
        finally:
            self._loading = False
        self.schedule()

    def load_example(self):
        """Replace the data and conditions with the example (5 days LD 12:12, 5 cycles
        LD 15:15, then 168 h LL); display options are kept."""
        # ask first if there are data that would be lost
        has_data = any(self.texts[k].get("1.0", "end-1c").strip() for k in ("peaks", "troughs"))
        if has_data and not messagebox.askyesno(
                APP_NAME, "Replace the current peaks, troughs, clock time and LD cycles with the "
                          "example (LD 12:12 \u2192 LD 15:15 \u2192 LL)?", parent=self):
            return
        # keep the display options, replace data and conditions
        settings = self.get_settings()
        settings.update(example_settings())
        self.apply_settings(settings)
        # the time-series window is not needed for typed times
        if self.series_win is not None:
            self.series_win.close()

    def clear_all(self):
        """Blank the data and every date, and reset the light/dark cycles to LD 12:00 / 12:00
        followed by LL (Change 1); display options are kept.  Asks first."""
        if not messagebox.askyesno(APP_NAME, "Clear all data and dates?\n\nPeaks and troughs (and the time-series data), the clock time of 0 h, the sample placement and every LD start date are cleared. The first cycle is reset to LD 12:00 / 12:00 and Change 1 to LL. Display options are kept. This cannot be undone.",
                                   icon="warning", default="no", parent=self):
            return
        settings = self.get_settings()
        # fresh conditions: LD 12:12 without start date, followed by LL
        cycles = [{"mode": "LD", "L": "12:00", "D": "12:00", "start": "", "phase": "Light"}
                  for _ in range(1 + MAX_CHANGES)]
        cycles[1]["mode"] = "LL"
        # blank the data and every date; keep display options
        settings.update(peaks="", troughs="", t0="", placed="", cycles=cycles, n_changes=1, sel_peaks=[], sel_troughs=[],
                        series="", ts_edits=empty_edits())
        # the example title goes too
        if settings["title"].strip() == EXAMPLE_TITLE:
            settings["title"] = ""
        self.apply_settings(settings)

    def clear_data(self):
        """Empty the peak and trough lists (undoable with Ctrl+Z in each list); the
        'Example Data' title goes with them.  With time-series input: the series and its edits."""
        # time-series input: clear the series (Ctrl+Z in the box brings it back) and the hand edits
        if self.input_mode_var.get() == "series":
            if not self.series_text.get("1.0", "end-1c").strip():
                return
            if not messagebox.askyesno(APP_NAME, "Clear the time-series data and its hand edits?\n\n"
                                                 "(Ctrl+Z in the data box brings the data back.)",
                                       icon="warning", default="no", parent=self):
                return
            # edit separators make the deletion one undo step
            self.series_text.edit_separator()
            self.series_text.delete("1.0", "end")
            self.series_text.edit_separator()
            self.ts_edits = empty_edits()
            self.schedule()
            return
        # typed-times input: clear both lists
        if not any(self.texts[k].get("1.0", "end-1c").strip() for k in ("peaks", "troughs")):
            return                                    # nothing to clear
        if not messagebox.askyesno(APP_NAME, "Clear all peak and trough values?\n\n"
                                             "(Ctrl+Z in a list brings its values back.)",
                                   icon="warning", default="no", parent=self):
            return
        if self.title_var.get().strip() == EXAMPLE_TITLE:
            self.title_var.set("")
        for key in ("peaks", "troughs"):
            txt = self.texts[key]
            txt.edit_separator()
            txt.delete("1.0", "end")
            txt.edit_separator()
        # nothing is selected any more
        self.selection = {"sel_peaks": [], "sel_troughs": []}
        self.schedule()

    def save_settings_file(self):
        """Save all settings as JSON."""
        path = filedialog.asksaveasfilename(title="Save settings", defaultextension=".json",
                                            filetypes=[("Settings", "*.json")])
        if path:
            # pretty-printed UTF-8 JSON (ensure_ascii=False keeps characters such as the en dash readable)
            Path(path).write_text(json.dumps(self.get_settings(), indent=2, ensure_ascii=False), encoding="utf-8")

    def load_settings_file(self):
        """Load a JSON settings file (from this app or from the web version)."""
        path = filedialog.askopenfilename(title="Load settings", filetypes=[("Settings", "*.json"), ("All", "*.*")])
        if not path:
            return
        try:
            # apply_settings validates and fills in missing keys
            self.apply_settings(json.loads(Path(path).read_text(encoding="utf-8")))
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not read the settings file:\n{exc}")

    def on_close(self):
        """Remember the display options for the next session, then quit."""
        try:
            # the settings of this session are written to ~/.actogram_plotter.json; at the next start only
            # the display options are taken from it (the data start with the example)
            SETTINGS_FILE.write_text(json.dumps(self.get_settings(), indent=2, ensure_ascii=False),
                                     encoding="utf-8")
        except Exception:
            pass
        self.destroy()

    # ---------------- redraw ----------------
    def _text_changed(self, txt: tk.Text):
        """A Text widget was edited by the user: schedule a redraw."""
        if self._writing:
            return
        # edit_modified() is the Text widget's 'changed' flag; reset it so the next edit fires again
        if txt.edit_modified():
            txt.edit_modified(False)
            self.schedule()

    def schedule(self):
        """Request a redraw in 30 ms; several quick changes cause only one redraw."""
        # no redraw while loading settings, and only one pending redraw at a time
        if self._loading or self._pending is not None:
            return
        self._pending = self.after(30, self.redraw)

    def redraw(self):
        """Recompute and redraw everything from the current settings (see the class docstring)."""
        self._pending = None
        # 1. read all controls; with time-series input, detect the peaks/troughs first and write
        #    them into the (read-only) lists, then read the settings again so they include them
        st = self.get_settings()
        self.ts = None
        if st["input_mode"] == "series":
            self.ts = analyze_series(st)
            self._write_detected(self.ts)
            st = self.get_settings()
        # 2. derive 0 h, the LD schedule, placement, origin and period; refresh the series window
        res = compute(st)
        self.res = res
        self._update_series_controls(st)
        if self.series_win is not None:
            try:
                self.series_win.update(self.ts or {"ok": False, "error": "Choose \u2018Detect them in "
                                                   # detection succeeded or failed: the window shows the plot or the message
                                                   "time-series data\u2019 to use the time series."}, st, res)
            except tk.TclError:
                self.series_win = None
            except Exception as exc:          # never leave the window without a message
                self.series_win.fig.clear()
                self.series_win.fig.text(0.5, 0.5, f"Could not draw the time series:\n{exc}",
                                         ha="center", va="center")
                self.series_win.canvas.draw_idle()

        # 3. messages and visibility of the controls (counts, LD cards, info and error lines)
        self.clock_err.set(res.clock_error)
        for key in ("peaks", "troughs"):
            vals, bad = parse_list(st[key])
            if self.ts is not None and self.ts.get("ok"):
                kind = key
                hand = len([i for i in self.ts[kind] if i not in set(self.ts["auto_" + kind])])
                self.count_vars[key].set(f"{len(vals)} detected" + (f" ({hand} added by hand)" if hand else ""))
                continue
            self.count_vars[key].set(
                f"Not a number: {', '.join(bad[:3])}{' …' if len(bad) > 3 else ''}" if bad
                else (f"{len(vals)} value{'s' if len(vals) != 1 else ''}" if vals else "No values yet"))
        n = st["n_changes"]
        for i, w in enumerate(self.cycle_widgets):
            w["card"].grid() if i <= n else w["card"].grid_remove()
            if self.cycle_vars[i]["mode"].get() == "LD":
                if not w["ld_part"].winfo_ismapped():
                    w["ld_part"].pack(side="left")
            else:
                w["L"].close(); w["D"].close()
                w["ld_part"].pack_forget()
            shown = "Light first" if self.cycle_vars[i]["phase"].get() != "Dark" else "Dark first"
            if w["phase_shown"].get() != shown:
                w["phase_shown"].set(shown)
            w["remove"].state(["disabled"] if n < 1 else ["!disabled"])
        self.add_condition_button.state(["disabled"] if n >= MAX_CHANGES else ["!disabled"])
        self.ld_err.set("\n".join(res.ld_errors) if st["show_ld"] else "")
        self.ld_info.set(res.ld_info if st["show_ld"] else "")
        self.origin_entry.state(["!disabled"] if st["origin"] == "custom" else ["disabled"])
        self.placed_err.set(res.placed_error)
        self.placed_info.set(f"= {g(res.placed_hour)} h of the data ({res.placed_label})"
                             if res.placed_hour is not None else "")
        self.origin_err.set(res.origin_error)
        self.origin_info.set(res.origin.info + (f"\n{res.origin.note}" if res.origin.note else ""))
        self.period_err.set(res.period_error)
        for sw, var, code in getattr(self, "swatches", []):
            if sw is None:                      # the name shown after a palette
                name_var, palette = code
                current = pick_color(var.get(), palette)
                name_var.set(next(n for n, c in palette if c == current))
            else:
                chosen = pick_color(var.get(), LIGHT_COLORS if var is self.light_color_var else DARK_COLORS) == code
                sw.configure(highlightbackground="#1f2933" if chosen else "#ffffff")

        # 4. the actogram itself, the row range, the fine-tune panel and the phase analysis
        try:
            self.hits = draw_actogram(self.fig, st, res) or []
        except Exception as exc:       # never leave the window without a plot
            self.hits = []
            self.fig.clear()
            self.fig.text(0.5, 0.5, f"Could not draw the actogram:\n{exc}", ha="center", va="center")
        self.canvas.draw_idle()
        (lo, hi), self.auto_range, note = row_range(st, res)
        self.rows_info.set(f"{lo} to {hi}  ({hi - lo + 1} rows)" + ("  automatic" if st["rows_auto"] else ""))
        self.rows_note.set(note)
        for spin in self.row_spins:
            spin.state(["disabled"] if st["rows_auto"] else ["!disabled"])
        self._update_tune()
        self._update_analysis(st, res)

    # ---------------- phase analysis ----------------
    def _build_analysis(self, root):
        """Phase-analysis panel: selection tools, the 0° reference for LL/DD, result cards and tables, export buttons."""
        # line 1: drag mode, which kinds, Select all / Clear selection, and the count of selected points
        bar = ttk.Frame(root)
        bar.pack(fill="x")
        ttk.Label(bar, text="Drag to").pack(side="left")
        for value, text in (("select", "Select"), ("deselect", "Deselect")):
            ttk.Radiobutton(bar, text=text, value=value, variable=self.drag_mode_var).pack(side="left", padx=(4, 0))
        ttk.Label(bar, text="   Applies to").pack(side="left")
        for value, text in (("both", "Both"), ("peaks", "Peaks"), ("troughs", "Troughs")):
            ttk.Radiobutton(bar, text=text, value=value, variable=self.sel_target_var).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="Select all", command=self.select_all).pack(side="left", padx=(12, 0))
        ttk.Button(bar, text="Clear selection", command=self.clear_selection).pack(side="left", padx=(6, 0))
        self.sel_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.sel_count, foreground="#1f5fa8").pack(side="left", padx=(12, 0))
        # line 2: the 0-degree reference for LL/DD and 'Draw fitted lines'
        bar2 = ttk.Frame(root)
        bar2.pack(fill="x", pady=(6, 0))
        ttk.Label(bar2, text="0\u00b0 for LL and DD").pack(side="left")
        ttk.Combobox(bar2, textvariable=self.phase_ref_var, values=[t for _k, t in PHASE_REFS], state="readonly",
                     width=48).pack(side="left", padx=(6, 0))
        ttk.Checkbutton(bar2, text="Draw fitted lines (LD: mean phase, dotted black; LL/DD: regression)", variable=self.draw_fit_var).pack(side="left", padx=(12, 0))
        # explanation of the selection and of the formulas
        ttk.Label(root, text="Click a point to select or deselect it; drag a box to select many (hold Alt to do the "
                             "opposite). Use it with the toolbar's zoom/pan switched off. LD: phase = ZT \u00f7 (L + D) "
                             "\u00d7 360\u00b0 with ZT0 at light-on. LL/DD: t = b + \u03c4\u00b7n fitted on the cycle "
                             "number n (cycle 0 begins at the 0\u00b0 reference); \u03c4 is the period and the phase is "
                             "(b mod \u03c4) \u00f7 \u03c4 \u00d7 360\u00b0.",
                  foreground="#666666", wraplength=900, justify="left").pack(fill="x", pady=(4, 0))
        # notes of the analysis (e.g. points before the first condition)
        self.ana_note = tk.StringVar()
        ttk.Label(root, textvariable=self.ana_note, foreground="#1f5fa8").pack(fill="x")
        # the summary table as a Treeview with the same columns as result_rows()
        cols = result_rows({"groups": []})[0]
        self.ana_tree = ttk.Treeview(root, columns=cols, show="headings", height=5)
        for c in cols:
            self.ana_tree.heading(c, text=c)
            self.ana_tree.column(c, width=170 if c in ("Condition", "0\u00b0 reference") else 78,
                                 anchor="w" if c in ("Condition", "Type", "0\u00b0 reference") else "e")
        self.ana_tree.pack(fill="x", pady=(4, 0))
        ttk.Label(root, text="Phase (h) is the phase in hours within one cycle: for LD the mean ZT (hours after "
                             "light-on), for LL/DD b mod \u03c4 (hours from the 0\u00b0 reference to the fitted event). "
                             "Phase (\u00b0) is the same as a fraction of the cycle: Phase (h) \u00f7 cycle length "
                             "\u00d7 360\u00b0.", foreground="#666666", wraplength=900, justify="left").pack(fill="x", pady=(2, 0))
        # buttons: the results window, CSV export, copy to the clipboard
        btns = ttk.Frame(root)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="Phase results\u2026", command=self.show_results_window).pack(side="left")
        ttk.Button(btns, text="Export results (CSV)…", command=self.export_results).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="Copy results (tab-separated)", command=self.copy_results).pack(side="left", padx=(6, 0))
        self.ana_status = tk.StringVar()
        ttk.Label(btns, textvariable=self.ana_status, foreground="#666666").pack(side="left", padx=(10, 0))
        # the last result tables (for export/copy)
        self._results = ([], [])

    def show_results_window(self):
        """A window with one block per condition (dial and results); it follows every change."""
        # only one results window; bring it to the front if open
        win = getattr(self, "_res_win", None)
        if win is not None and win.winfo_exists():
            win.lift()
            return
        win = self._res_win = tk.Toplevel(self)
        win.title("Phase results")
        win.geometry("1000x720")
        # a scrollable canvas holding the matplotlib figure (it can be taller than the window)
        outer = tk.Canvas(win, highlightthickness=0, background="white")
        bar = ttk.Scrollbar(win, orient="vertical", command=outer.yview)
        outer.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        outer.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(outer, background="white")
        outer.create_window((0, 0), window=inner, anchor="nw")
        self._res_fig = Figure(figsize=(9.6, 4), dpi=100, facecolor="white")
        self._res_canvas = FigureCanvasTkAgg(self._res_fig, master=inner)
        self._res_canvas.get_tk_widget().pack()
        inner.bind("<Configure>", lambda _e: outer.configure(scrollregion=outer.bbox("all")))
        self._res_scroll = outer
        save = ttk.Button(win, text="Save as image\u2026", command=self._save_results_figure)
        # the save button floats at the top right
        save.place(relx=1.0, x=-24, y=6, anchor="ne")
        self._draw_results_window()

    def _draw_results_window(self):
        """Refresh the 'Phase results' window (cards with dials) if it is open."""
        win = getattr(self, "_res_win", None)
        if win is None or not win.winfo_exists():
            return
        st = self.get_settings()
        res = compute(st)
        # the figure height depends on the number of conditions
        h = draw_phase_results(self._res_fig, analyze(st, res), res)
        self._res_canvas.get_tk_widget().configure(width=int(9.6 * 100), height=int(h * 100))
        self._res_canvas.draw_idle()

    def _save_results_figure(self):
        """Save the phase-results window as an image."""
        path = filedialog.asksaveasfilename(title="Save phase results", defaultextension=".png",
                                            filetypes=[("PNG image", "*.png"), ("SVG image", "*.svg"), ("PDF", "*.pdf")])
        if path:
            self._res_fig.savefig(path, dpi=200, facecolor="white")

    def _update_analysis(self, st, res):
        """Run analyze() on the selected points and show the summary and the per-point tables."""
        self._draw_results_window()
        ana = analyze(st, res)
        self.ana_note.set(ana["note"])
        # tables for the Treeview and for export
        rows, events = result_rows(ana), event_rows(ana, res)
        self._results = (rows, events)
        # refill the Treeview
        self.ana_tree.delete(*self.ana_tree.get_children())
        for r in rows[1:]:
            self.ana_tree.insert("", "end", values=r)
        # 'Selected: n peaks, m troughs'
        n_p = sum(1 for e in ana["events"] if e["kind"] == "Peak")
        n_t = len(ana["events"]) - n_p
        self.sel_count.set(f"Selected: {n_p} peak{'s' if n_p != 1 else ''}, {n_t} trough{'s' if n_t != 1 else ''}")

    def _targets(self):
        """Which kinds the selection tools act on: ['p'] peaks, ['t'] troughs, or both."""
        t = self.sel_target_var.get()
        return ["p"] if t == "peaks" else ["t"] if t == "troughs" else ["p", "t"]

    def _set_selected(self, kk, value, on):
        """Select or deselect one peak ('p') or trough ('t') value."""
        key = "sel_peaks" if kk == "p" else "sel_troughs"
        # remove any entry with the same 4-decimal key, then add it if selecting
        current = [v for v in self.selection[key] if k4(v) != k4(value)]
        if on:
            current.append(float(value))
        self.selection[key] = current

    def _is_selected(self, kk, value):
        """True if this peak/trough value is selected."""
        key = "sel_peaks" if kk == "p" else "sel_troughs"
        return any(k4(v) == k4(value) for v in self.selection[key])

    def select_all(self):
        """Select all peaks and/or troughs (according to 'Applies to')."""
        st = self.get_settings()
        for kk in self._targets():
            key = "sel_peaks" if kk == "p" else "sel_troughs"
            # select every value of the list(s)
            self.selection[key] = parse_list(st["peaks" if kk == "p" else "troughs"])[0]
        self.schedule()

    def clear_selection(self):
        """Deselect all peaks and/or troughs (according to 'Applies to')."""
        for kk in self._targets():
            self.selection["sel_peaks" if kk == "p" else "sel_troughs"] = []
        self.schedule()

    def _mouse_ok(self, event):
        """True for a left click in the actogram while the zoom/pan tools are off."""
        # the toolbar's mode is non-empty while zoom/pan is active
        return (event.inaxes is not None and event.button == 1 and not getattr(self.toolbar, "mode", "")
                and self.fig.axes and event.inaxes is self.fig.axes[0])

    def _on_press(self, event):
        """Mouse button down in the actogram: remember the start (for a click or a selection box)."""
        if not self._mouse_ok(event):
            self._press = None
            return
        # remember where the press happened and whether Alt was held
        self._press = {"x": event.x, "y": event.y, "alt": "alt" in str(event.key or ""), "rect": None}

    def _on_motion(self, event):
        """Dragging: draw the selection rectangle."""
        p = self._press
        if p is None or event.x is None:
            return
        # less than 5 pixels: still a click, not a drag
        if p["rect"] is None and math.hypot(event.x - p["x"], event.y - p["y"]) < 5:
            return
        ax = self.fig.axes[0]
        # pixels -> data coordinates of the two corners
        inv = ax.transData.inverted()
        (x0, y0), (x1, y1) = inv.transform((p["x"], p["y"])), inv.transform((event.x, event.y))
        if p["rect"] is None:
            from matplotlib.patches import Rectangle
            # a light blue dashed rectangle shows the box
            p["rect"] = Rectangle((x0, y0), 0, 0, fill=True, facecolor=(0.12, 0.31, 0.82, 0.08),
                                  edgecolor="#1f4fd1", linestyle="--", zorder=10)
            ax.add_patch(p["rect"])
        p["rect"].set_bounds(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
        self.canvas.draw_idle()

    def _on_release(self, event):
        """Mouse button up: a click toggles the nearest point; a box selects (or, with Alt or
        'Deselect', deselects) every point inside it.
        """
        p, self._press = self._press, None
        if p is None or not self.fig.axes:
            return
        ax = self.fig.axes[0]
        to_px = ax.transData.transform
        if p["rect"] is None:                    # a click: toggle the nearest point
            # nearest drawn point within 8 pixels
            best, best_d = None, 8.0
            for x, y, kk, h in self.hits:
                # point position in pixels
                px, py = to_px((x, y))
                d = math.hypot(px - p["x"], py - p["y"])
                if d < best_d:
                    best, best_d = (kk, h), d
            if best is not None:
                # toggle it
                self._set_selected(best[0], best[1], not self._is_selected(*best))
                self.schedule()
            return
        # a box: remove the rectangle and select/deselect every point inside
        p["rect"].remove()
        x_end = event.x if event.x is not None else p["x"]
        y_end = event.y if event.y is not None else p["y"]
        xa, xb = sorted((p["x"], x_end))
        ya, yb = sorted((p["y"], y_end))
        # select, unless 'Deselect' is chosen or Alt is held (Alt inverts the mode)
        on = (self.drag_mode_var.get() == "select") != (p["alt"] or "alt" in str(event.key or ""))
        kinds = self._targets()
        changed = False
        for x, y, kk, h in self.hits:
            px, py = to_px((x, y))
            if xa <= px <= xb and ya <= py <= yb and kk in kinds:
                self._set_selected(kk, h, on)
                changed = True
        # redraw only if something changed; otherwise just remove the rectangle
        self.schedule() if changed else self.canvas.draw_idle()

    def export_results(self):
        """Save the summary table and the per-point table as one CSV file."""
        rows, events = self._results
        if len(rows) < 2:
            self.ana_status.set("No results yet.")
            return
        # file name from the title (characters not allowed in file names replaced by '_')
        base = re.sub(r'[\\/:*?"<>|\s]+', "_", self.title_var.get().strip() or "actogram")[:80]
        path = filedialog.asksaveasfilename(title="Export results", initialfile=base + "_phase.csv",
                                            defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        import csv
        # utf-8-sig adds a BOM so Excel recognises the encoding; the two tables are separated by an empty row
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerows(rows)
            w.writerow([])
            w.writerows(events)
        self.ana_status.set(f"Saved {Path(path).name}")

    def copy_results(self):
        """Copy both result tables to the clipboard as tab-separated text (for spreadsheets)."""
        rows, events = self._results
        if len(rows) < 2:
            self.ana_status.set("Nothing to copy yet.")
            return
        # tab-separated rows paste directly into spreadsheet cells
        text = "\n".join("\t".join(str(c) for c in r) for r in rows + [[]] + events)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.ana_status.set("Copied to the clipboard.")

    # ---------------- fine-tuning ----------------
    def _current_ms(self, key, res: Result):
        """Current moment of 0 h of the data ('t0') or of the actogram origin, as a UTC datetime."""
        # 0 h of the data itself
        if key == "t0":
            return res.zero
        # the origin = 0 h + origin hours (rounded to the minute)
        return res.zero + timedelta(minutes=round(res.origin.hour * 60))

    def _set_moment(self, key, utc: datetime, res: Result):
        """Store a new moment for 't0' or the origin (the origin then becomes 'Another date/time')."""
        # write as local clock time text (with CDT/CST if ambiguous) so it reads back exactly
        text = wall_string(utc, res.tz)
        if key == "t0":
            if text != self.t0_var.get():
                self.t0_var.set(text)
        else:
            # moving the origin by hand turns the origin option into 'Another date/time'
            if self.origin_var.get() != "custom":
                self.origin_var.set("custom")
            if text != self.origin_time_var.get():
                self.origin_time_var.set(text)

    def nudge(self, key: str, minutes: int):
        """The ±1 min / ±10 min / ±1 h buttons of the fine-tune panel."""
        res = compute(self.get_settings())
        # period: change T by the given minutes within the allowed range
        if key == "period":
            current = round(res.period * 60)
            self.period_var.set(format_duration(max(PERIOD_MIN_MIN, min(PERIOD_MAX_MIN, current + minutes)) / 60))
            return
        if res.zero is None or res.tz is None:
            return
        # a button press ends any slider drag
        self._anchor[key] = None
        self._set_moment(key, self._current_ms(key, res) + timedelta(minutes=minutes), res)

    def _shift_scale(self, key: str, value):
        """The day-0 slider: shift the origin by up to ±12 h from where the drag started."""
        value = float(value)
        res = compute(self.get_settings())
        if res.zero is None or res.tz is None:
            return
        # first movement of a drag: the anchor = the moment when the slider was at 0
        if self._anchor[key] is None:
            self._anchor[key] = self._current_ms(key, res) - timedelta(minutes=self._last_scale[key])
        self._last_scale[key] = value
        # new moment = anchor + slider value (minutes)
        target = self._anchor[key] + timedelta(minutes=value)
        if target != self._current_ms(key, res):
            self._set_moment(key, target, res)

    def _reset_scale(self, key: str):
        """Recentre the day-0 slider after a drag (it is relative to its anchor)."""
        self._anchor[key] = None
        self._last_scale[key] = 0.0
        self.scales[key].set(0)

    def _period_scale(self, value):
        """The period slider: set T in minutes."""
        minutes = int(round(float(value)))
        res = getattr(self, "res", None)
        if res is not None and round(res.period * 60) == minutes:
            return
        self.period_var.set(format_duration(minutes / 60))

    def _update_tune(self):
        """Refresh the texts and slider positions of the fine-tune panel."""
        res = self.res
        ok = res.zero is not None and res.tz is not None
        if ok:
            # show the origin as local time and as hours of the data
            self.tune_vals["origin"].set(f"{format_local(self._current_ms('origin', res), res.tz)}  "
                                         f"(= {g(res.origin.hour)} h)")
        else:
            self.tune_vals["origin"].set("Set a valid clock time and time zone")
        m = round(res.period * 60)
        self.tune_vals["period"].set(f"{format_duration(m / 60)}  ({m / 60:.3f} h)")
        try:
            focused = self.focus_get()
        except Exception:          # e.g. while a combobox list is open
            focused = None
        # keep the period slider in step with T, except while the user is dragging it
        if focused is not self.scales["period"] and int(self.scales["period"].get()) != m:
            self.scales["period"].set(m)

    # ---------------- light/dark conditions: add and remove ----------------
    BLANK_CYCLE = {"mode": "LD", "L": "12:00", "D": "12:00", "start": "", "phase": "Light"}

    def add_condition(self):
        """Append a light/dark condition card (up to MAX_CHANGES changes)."""
        n = int(self.n_changes_var.get() or 0)
        if n >= MAX_CHANGES:
            return
        # the next unused card gets the blank values, then one more card is shown
        for k, v in self.BLANK_CYCLE.items():
            self.cycle_vars[n + 1][k].set(v)
        self.n_changes_var.set(n + 1)

    def remove_condition(self, index: int):
        """Remove one condition; the later ones move up."""
        n = int(self.n_changes_var.get() or 0)
        if n < 1:
            return
        # copy all cards, drop the removed one and append a blank card at the end
        values = [{k: v.get() for k, v in cv.items()} for cv in self.cycle_vars]
        values.pop(index)
        values.append(dict(self.BLANK_CYCLE))
        # write back without a redraw for every single variable
        self._loading = True
        try:
            for cv, c in zip(self.cycle_vars, values):
                for k in cv:
                    cv[k].set(c[k])
            self.n_changes_var.set(n - 1)
        finally:
            self._loading = False
        self.schedule()

    # ---------------- suggested start times for LD -> LL / DD ----------------
    SUGGEST_COUNT = 120

    def start_suggestions(self, index: int):
        """For a change right after an LD cycle: the times at which D of that LD cycle ends
        (lights-on) when the new condition is LL or an LD cycle beginning with Light, or the
        times at which L ends (lights-off) when it is DD or an LD cycle beginning with Dark.
        None if not applicable."""
        st = self.get_settings()
        # the first condition has no predecessor
        if index < 1:
            return None
        mode, phase = st["cycles"][index]["mode"], st["cycles"][index]["phase"]
        # LL and 'LD, light first' start at a lights-on; DD and 'LD, dark first' at a lights-off
        lights_on = mode == "LL" or (mode == "LD" and phase == "Light")
        what = ("end of D (lights-on)" if lights_on else "end of L (lights-off)")
        title = f"Suggested: {what} of the previous LD cycle"
        if mode == "LD":
            title += f" \u2013 this cycle begins with {'Light' if lights_on else 'Dark'}"
        # suggestions only make sense after an LD condition
        prev_mode = st["cycles"][index - 1]["mode"]
        if prev_mode != "LD":
            return None
        # compute the schedule up to the previous condition only
        sub = dict(st, show_ld=True, n_changes=index - 1)
        res = compute(sub)
        if res.ld is None or len(res.ld.segments) != index:
            return (title, [], "Fix the earlier cycles (and the clock time of 0 h) first; "
                               "then the suggested times are listed here.")
        prev = res.ld.segments[-1]
        if prev.light <= 0 or prev.dark <= 0:
            return (title, [], "The previous LD cycle has no "
                               f"{'D' if lights_on else 'L'} period, so there is nothing to suggest.")
        # list the next SUGGEST_COUNT onsets of the wanted kind after the previous condition started
        period = prev.light + prev.dark
        # first onset at or after the start of the previous cycle
        if lights_on:              # light onsets = ends of D
            first = prev.start_hour + (0 if prev.starts_with_light else prev.dark)
        else:                      # dark onsets = ends of L
            first = prev.start_hour + (prev.light if prev.starts_with_light else 0)
        items = []
        for k in range(self.SUGGEST_COUNT):
            hour = first + k * period
            if hour <= prev.start_hour:
                continue
            # the onset as local clock time (text that reads back exactly) and a descriptive list label
            moment = res.zero + timedelta(minutes=round(hour * 60))
            text = wall_string(moment, res.tz)
            local = moment.astimezone(res.tz)
            word = "lights-on" if lights_on else "lights-off"
            items.append((text, f"{local:%a %Y-%m-%d %H:%M} {local.tzname():<4}  {g(hour):>8} h  {word}"))
        note = (f"L {format_duration(prev.light)} / D {format_duration(prev.dark)} of the cycle that starts "
                f"{prev.label}.  You can still pick any other date/time above.")
        return (title, items, note)

    # ---------------- rows ----------------
    def _rows_auto_toggled(self):
        """Rows 'Automatic' switched off: start the manual Min/Max at the automatic range."""
        # prefill Min/Max with the automatic range when switching to manual rows
        if not self.rows_auto_var.get():          # start the manual range at the automatic one
            lo, hi = getattr(self, "auto_range", (0, 5))
            self.row_min_var.set(str(lo))
            self.row_max_var.set(str(hi))

    def _spin_step(self, var, spin, step: int) -> str:
        """Step a row spinbox by one (keys/buttons)."""
        if spin.instate(["disabled"]):
            return "break"
        try:
            value = int(str(var.get()).strip())
        except ValueError:
            value = 0
        # keep within -9999 .. 9999
        var.set(str(max(-9999, min(9999, value + step))))
        return "break"

    def _spin_wheel(self, event, var, spin) -> str:
        """Mouse wheel over a row spinbox."""
        num = getattr(event, "num", 0)
        # X11 button 4 or a positive delta = wheel up
        up = num == 4 or getattr(event, "delta", 0) > 0
        return self._spin_step(var, spin, 1 if up else -1)

    # ---------------- saving ----------------
    def save_figure(self):
        """Save the actogram as PNG (300 dpi), SVG or PDF; the file name defaults to the title."""
        # file name from the title
        base = re.sub(r'[\\/:*?"<>|\s]+', "_", self.title_var.get().strip() or "actogram")[:80]
        path = filedialog.asksaveasfilename(
            title="Save figure", initialfile=base + ".png", defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("SVG image", "*.svg"), ("PDF", "*.pdf")])
        if not path:
            return
        try:
            # 300 dpi PNG (or vector SVG/PDF); 'tight' removes empty margins
            self.fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not save the figure:\n{exc}")


def main():
    """Start the desktop app."""
    # create the window and run the Tk event loop until the window is closed
    app = App()
    app.mainloop()


# run main() only when the file is executed, not when it is imported
if __name__ == "__main__":
    main()
