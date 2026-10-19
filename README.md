Actogram-like visualization tracking circadian peak and trough times
# Actogram Plotter

**▶ Open the app: https://dxda6216.github.io/actogram_plotter/**

Actogram Plotter draws a double‑plotted (or single‑plotted) actogram from peak and trough times of a rhythm, together with the light/dark conditions of the experiment. It does no rhythm analysis: you enter the times, it draws the figure.

The app runs entirely in your web browser from the link above. There is nothing to install and no account is needed. Everything you enter stays in your browser: no data is uploaded or sent anywhere, and the only external request is for the web font.

## Quick start

1. Open **https://dxda6216.github.io/actogram_plotter/** in a current desktop browser (Chrome, Edge, Firefox or Safari). Bookmark it for next time.
2. The app starts with example data, so a finished actogram is shown straight away.
3. Click **Clear data**, paste your own peak and trough times, set the clock time of 0 h and the light/dark cycles, and the plot updates as you type.
4. Save the figure with **Save as PNG** or **Save as SVG**, and your inputs with **Save settings**.

To use the app without an internet connection, download `index.html` from this repository and open it in your browser; it works the same way (only the web font falls back to a system font).

## Entering the data

### Clock time of the data

Set **0 h =** to the local date and time at which your time axis starts, and choose the **time zone** of the experiment. The default is US Central Time (America/Chicago). The list runs from the zone furthest ahead of UTC westwards, with UTC last; any other IANA zone name (for example `Europe/Rome`) or a fixed offset (for example `UTC+09:00`) can be typed under **Other…**.

Enter every date and time as the local clock time shown on a wall clock on that day, whether standard or daylight time. Do not convert daylight time to standard time: the app converts each date and time to UTC itself, so intervals that cross a daylight‑saving change get their true length.

All dates and times are entered with a picker: click a day in the calendar and choose the hour and minute. Days on which the clocks change are shaded. A time that does not exist (clocks going forward) is rejected, and for a time that occurs twice (clocks going back) you choose the first or the second occurrence. Times entered this way are stored with the zone abbreviation, for example `2026-11-01 01:30 CST`.

### Peaks and troughs

Paste the peak times and the trough times into the two lists, one value per line, as hours after 0 h (for example `12.76`, `36.71`, `60.52`). A column copied from a spreadsheet works as it is; commas, tabs and spaces also separate values, and negative values plot before 0 h. Under each list the app shows how many values it read and points out anything that is not a number.

**Load example** loads the example data set and **Clear data** empties both lists after asking for confirmation.

### Light/dark (LD) cycles

Describe the lighting with a first cycle and up to five changes. Each one has:

- **Condition**: `LD` (light/dark cycle), `LL` (constant light) or `DD` (constant darkness).
- **L** and **D**: the lengths of the light and dark periods, 00:00 to 99:59 (hh:mm, default 12:00), so T‑cycles other than 24 h are possible. Type them or pick them with the mouse from the wheel next to each field.
- **Starts at**: the local date and time at which the condition begins.
- **Begins with**: whether an LD cycle starts with its light or its dark period.

Each condition lasts until the next change starts. When a change from LD to LL or DD is picked, the picker also lists the times at which D (lights‑on) or L (lights‑off) of the previous LD cycle ends. **Also draw the first cycle before its start time** extends the first condition backwards. Light periods are drawn pale yellow and dark periods grey.

### Actogram day 0, 0 h

This sets the left end of the top row (0 h on the horizontal axis). It can be 0 h of the data, the lights‑on of the first LD cycle on its start date, or any other date and time.

## Plot options

| Option | What it does |
|---|---|
| Title | Title of the figure (default when empty: a description of the plot). |
| Period T | Length of one row, 0:01 to 240:00 (hh:mm, default 24:00). |
| Plot | Double‑plotted (two cycles per row) or single‑plotted. |
| Row labels | Row numbers or the date at which each row starts. |
| X major ticks | 0 to 5 labelled ticks per period T (default 3, that is quarters of T). |
| X minor ticks | 0 to 11 unlabelled ticks between the major ticks (default none). |
| Show times | Writes the time (h) next to each point. |
| Connect peaks / troughs | Joins each point to the one about one period later. |
| Label the start times of light and dark periods | Writes the local time and date of each lights‑on and lights‑off, for example `D 04:00  Oct. 6`. |
| Label the start date/time of each cycle | Adds the start date and time of each row to the vertical axis. |

### Fine‑tuning

The panel under the figure changes three values in 1‑minute steps while you watch the plot: **0 h of the data**, **actogram day 0, 0 h** and **period T**. Use the buttons (hold one to repeat), drag the sliders, or focus a slider and use the arrow keys.

**Rows (cycles)** sets which rows are drawn. *Automatic* covers all data; untick it to set the first (Min) and last (Max) row in whole cycles, negative values included. At most 1000 rows are drawn.

## Saving

- **Save as PNG** saves a high‑resolution image (3× the on‑screen size).
- **Save as SVG** saves a vector image for editing in Illustrator, Inkscape and similar programs.
- **Save settings** saves every input and option as a JSON file, and **Load settings…** reads one back.

Settings files use the same format as the desktop version of Actogram Plotter (`Actogram_Plotter_app.py`), so a file saved in either version opens in the other.

The page also remembers its display options in the browser between visits. Each visit starts with the example data, period T = 24:00 and US Central Time; use **Save settings** to keep your own data.

## Example data

The example covers about 18 days, with 0 h = Monday 5 October 2026, 08:00 CDT (lights‑on):

| Hours | Condition | Behaviour of the rhythm |
|---|---|---|
| 0–120 | 5 days of LD 12:12 (lights on 08:00) | Entrained; peaks about 12.5 h after lights‑on. |
| 120–270 | 5 cycles of LD 15:15 (T = 30 h) | Pulled to the longer cycle within a few cycles. |
| 270–438 | 168 h of LL, from the end of the last dark period | Free‑running with a period of about 24.8 h. |

Set **Period T** to 30:00 to see the LD 15:15 part line up.

## Privacy

The page is delivered by GitHub Pages, but everything you enter stays in your browser: no data is uploaded or sent anywhere, and the only external request is for the web font. What the page remembers between visits is stored only in your own browser, so it is not shared with other people or other computers; use **Save settings** to move your work.
