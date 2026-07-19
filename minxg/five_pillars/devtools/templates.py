"""minxg/five_pillars/devtools/templates.py — Template library for DevForge.

Pure-data template kit for the four supported platforms and
their canonical entrypoints.  Keeping templates as data (not
methods) means the AI can introspect the catalogue cheaply
and we can add a new framework without touching the worker.
"""

from __future__ import annotations

from typing import Dict, List

# ── Supported platforms ─────────────────────────────────────────────
PLATFORMS = ("android", "harmonyos", "linux", "windows")

PLATFORM_DISPLAY = {
    "android": "Android (Linux/ART)",
    "harmonyos": "HarmonyOS NEXT (ArkTS)",
    "linux": "Linux desktop (X11/Wayland)",
    "windows": "Windows desktop (Win32/WinUI)",
}

# ── Frameworks per platform ──────────────────────────────────────────
FRAMEWORKS: Dict[str, List[str]] = {
    "android": ["kivy", "kivymd", "flet", "kotlin_compose", "flutter",
                "react_native", "cordova", "termux_python"],
    "harmonyos": ["arkts", "arkui", "harmonyos_native", "harmonyos_web"],
    "linux": ["gtk4", "qt6", "pyqt6", "fltk", "tauri", "electron",
              "pyinstaller"],
    "windows": ["winui3", "wpf", "winforms", "uwp", "tauri", "electron",
                "msix", "pyinstaller", "wsl_linux"],
}

# ── Canonical entrypoint templates ──────────────────────────────────
ENTRYPOINTS: Dict[str, str] = {
    # Android — kivy baseline
    "kivy": """\
# Entry point: kivy baseline (Android)
from kivy.app import App
from kivy.uix.label import Label


class {app_class}(App):
    def build(self):
        return Label(text="{title}")


if __name__ == "__main__":
    {app_class}().run()
""",
    # Android — Kotlin Compose baseline
    "kotlin_compose": """\
// Entry point: Android Kotlin/Compose baseline
package {package}

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.*
import androidx.compose.runtime.Composable

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { App() }
    }
}

@Composable
fun App() {
    MaterialTheme {
        Surface { Text("{title}") }
    }
}
""",
    # Android — termux python (existing)
    "termux_python": """\
# Entry point: Termux Python baseline (Android)
from kivy.app import App
from kivy.uix.label import Label

class TermuxApp(App):
    def build(self):
        return Label(text="{title} — running in Termux")

if __name__ == "__main__":
    TermuxApp().run()
""",
    # HarmonyOS — ArkTS baseline
    "arkts": """\
// Entry point: HarmonyOS NEXT ArkTS baseline
@Entry
@Component
struct {app_class} {{
  build() {{
    Column() {{
      Text('{title}')
        .fontSize(32)
        .fontWeight(FontWeight.Bold)
    }}
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
  }}
}}
""",
    # HarmonyOS — ArkUI (declarative)
    "arkui": """\
// Entry point: HarmonyOS ArkUI declarative baseline
import { Column, Text, FlexAlign } from '@ohos.arkui.advanced';

@Entry
@Component
struct {app_class} {{
  build() {{
    Column() {{
      Text('{title}').fontSize(32)
    }}
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
  }}
}}
""",
    # Linux — Tauri (Rust + Web)
    "tauri": """\
// Linux Tauri baseline (Rust backend at src-tauri/src/main.rs)
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {{
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}}
""",
    # Linux — GTK4
    "gtk4": """\
// GTK4 baseline (Linux)
// gcc $(pkg-config --cflags gtk4) -o app main.c $(pkg-config --libs gtk4)
#include <gtk/gtk.h>

static void on_activate(GtkApplication *app, gpointer user_data) {{
    GtkWidget *win = gtk_application_window_new(app);
    gtk_window_set_title(GTK_WINDOW(win), "{title}");
    gtk_window_present(GTK_WINDOW(win));
}}

int main(int argc, char **argv) {{
    GtkApplication *app = gtk_application_new(
        "{package}", G_APPLICATION_DEFAULT_FLAGS);
    g_signal_connect(app, "activate", G_CALLBACK(on_activate), NULL);
    int status = g_application_run(G_APPLICATION(app), argc, argv);
    g_object_unref(app);
    return status;
}}
""",
    # Linux — Electron
    "electron": """\
// Electron main process (Linux/Windows cross-platform)
// package.json scripts: "start": "electron ."
// main.js:
const {{ app, BrowserWindow }} = require('electron');

function createWindow() {{
  const win = new BrowserWindow({{ width: 800, height: 600 }});
  win.loadFile('index.html');
}}

app.whenReady().then(createWindow);
""",
    # Windows — WinUI3 (C#/.NET)
    "winui3": """\
// WinUI3 App.xaml.cs baseline (Windows)
using Microsoft.UI.Xaml;

namespace {app_class}
{{
    public partial class App : Application
    {{
        private Window? _window;

        public App() {{
            this.InitializeComponent();
        }}

        protected override void OnLaunched(LaunchActivatedEventArgs args) {{
            _window = new MainWindow();
            _window.Activate();
        }}
    }}
}}
""",
    # Windows — pyinstaller (Python → .exe)
    "pyinstaller": """\
# Entry point: pyinstaller baseline (Windows/Linux)
def main():
    print("Hello from {title}")

if __name__ == "__main__":
    main()
# Build: pyinstaller --onefile main.py
""",
    # Windows — MSIX packaged
    "msix": """\
<!-- MSIX Package.appxmanifest baseline (Windows) -->
<?xml version="1.0" encoding="utf-8"?>
<Package
  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10">
  <Identity Name="{package}" Version="1.0.0.0" Publisher="CN=dev" />
  <Properties><DisplayName>{title}</DisplayName></Properties>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Universal" MinVersion="10.0.0.0"/>
  </Dependencies>
  <Applications>
    <Application Id="App" Executable="app.exe" EntryPoint="App">
      <uap:VisualElements DisplayName="{title}"/>
    </Application>
  </Applications>
</Package>
""",
}


def render_entrypoint(framework: str, *,
                      app_class: str = "App",
                      title: str = "MINXG",
                      package: str = "ai.minxg") -> str:
    """Render the canonical entry template for *framework*.

    Returns an empty string if *framework* is unknown so callers
    can detect "no template" and fall back to ``main.py``.
    """
    tmpl = ENTRYPOINTS.get(framework)
    if tmpl is None:
        return ""
    return tmpl.format(
        app_class=app_class, title=title, package=package,
    )


# ── Build commands per platform/framework ─────────────────────────────
BUILD_CMDS: Dict[str, Dict[str, List[str]]] = {
    "android": {
        "kivy":           ["buildozer", "android", "debug"],
        "termux_python":  ["buildozer", "android", "debug"],
        "kivymd":         ["buildozer", "android", "debug"],
        "flet":           ["flet", "build", "apk"],
        "kotlin_compose": ["./gradlew", "assembleDebug"],
        "flutter":        ["flutter", "build", "apk"],
        "react_native":   ["npx", "react-native", "run-android"],
        "cordova":        ["cordova", "build", "android"],
    },
    "harmonyos": {
        "arkts":             ["hvigorw", "assembleHap"],
        "arkui":             ["hvigorw", "assembleHap"],
        "harmonyos_native":  ["hvigorw", "assembleHap"],
        "harmonyos_web":     ["npm", "run", "build"],
    },
    "linux": {
        "tauri":      ["cargo", "tauri", "build"],
        "gtk4":       ["make"],
        "qt6":        ["cmake", "--build", "build"],
        "pyqt6":      ["pyinstaller", "--onefile", "main.py"],
        "fltk":       ["make"],
        "electron":   ["npm", "run", "build:linux"],
        "pyinstaller":["pyinstaller", "--onefile", "main.py"],
    },
    "windows": {
        "winui3":     ["dotnet", "publish", "-c", "Release"],
        "wpf":        ["dotnet", "build", "-c", "Release"],
        "winforms":   ["dotnet", "build", "-c", "Release"],
        "uwp":        ["msbuild", "/p:Configuration=Release"],
        "tauri":      ["cargo", "tauri", "build"],
        "electron":   ["npm", "run", "build:win"],
        "msix":       ["msbuild", "/p:Configuration=Release"],
        "pyinstaller":["pyinstaller", "--onefile", "main.py"],
        "wsl_linux":  ["wsl", "./build.sh"],
    },
}


def build_command(platform: str, framework: str) -> List[str]:
    """Return argv list for building *platform*/*framework*.

    Returns an empty list if unsupported — caller decides
    whether to error out or fall back to ``python main.py``.
    """
    return list(BUILD_CMDS.get(platform, {}).get(framework, []))


__all__ = [
    "PLATFORMS", "PLATFORM_DISPLAY", "FRAMEWORKS",
    "ENTRYPOINTS", "BUILD_CMDS",
    "render_entrypoint", "build_command",
]
