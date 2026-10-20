# Actogram Plotter

**▶ Open the app: https://dxda6216.github.io/actogram_plotter/**

This is a very simple web app that plots rhythm peaks and troughs like an actogram. It draws a double‑plotted (or single‑plotted) actogram from peak and trough times of a rhythm, together with the light/dark conditions of the experiment. It does no rhythm analysis: you enter the times, it draws the figure.

I wrote the core logic, and Claude assisted with the GUI, graphing details, and converting the Python code into the web application. Functions, such as automated detection for peaks and troughs in rhythms, period and phase analysis using linear regression, are not yet implemented.

The app runs entirely in your web browser from the link above. There is nothing to install and no account is needed.

## Quick start

1. Open **https://dxda6216.github.io/actogram_plotter/** in a current desktop browser (Chrome, Edge, Firefox or Safari). Bookmark it for next time.
2. The app starts with example data, so a finished actogram is shown straight away.
3. Click **Clear data**, paste your own peak and trough times, set the clock time of 0 h and the light/dark cycles, and the plot updates as you type.
4. Save the figure with **Save as PNG** or **Save as SVG**, and your inputs with **Save settings**.

To use the app without an internet connection, download `index.html` from this repository and open it in your browser; it works the same way (only the web font falls back to a system font).

## User manual

**▶ https://github.com/dxda6216/actogram_plotter/blob/main/actogram_plotter_web_app_manual.pdf**

## Privacy and data confidentiality

The page is delivered by GitHub Pages, but everything you enter stays in your browser: no data is uploaded or sent anywhere, and the only external request is to import web fonts from Google. What the page remembers between visits is stored only in your own browser, so it is not shared with other people or other computers.
