import { themeQuartz } from "ag-grid-community"

// One theme for every table. All colours are the project's CSS variables, so the light and dark themes switch by
// themselves when the panel's data-theme changes, with no second theme object.
export const gridTheme = themeQuartz.withParams({
    backgroundColor: "var(--card)",
    foregroundColor: "var(--text)",
    headerBackgroundColor: "var(--bg)",
    headerTextColor: "var(--muted)",
    borderColor: "var(--border)",
    accentColor: "var(--primary)",
    chromeBackgroundColor: "var(--card)",
    rowHoverColor: "color-mix(in srgb, var(--border) 45%, transparent)",
    wrapperBorder: false,
    wrapperBorderRadius: 0,
    fontSize: 13,
    headerFontSize: 12,
    spacing: 6,
})
