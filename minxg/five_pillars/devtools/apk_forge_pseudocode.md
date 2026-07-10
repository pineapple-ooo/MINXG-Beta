# ApkForgeWorker — UI / Icon / Asset expansion (pseudocode)

Goal: make the AI able to author a **near-complete Android UI** from prompts,
covering the patterns our web-search uncovered (KivyMD, Flet, Compose MDC,
adaptive launcher icons).

## 1. UI framework selection (facade)

Psevdo:

```
async def ui_template_apply(
    root_path,
    framework: str,          # "kivy" | "kivymd" | "flet" | "compose_mdc" | "react_native"
    style,                   # "material3" | "cupertino" | "minimal"
    theme: {primary, accent, mode}   # dark/light
) -> Dict:
    blueprints:
      kivy + material3 → kivymd templates (.kv, .py)
      flet + material3 → flet Page + ft.Theme + NavigationBar
      compose_mdc → Kotlin/Android scaffold (skeleton, not runnable without ndk)
      react_native → JSX scaffold (skeleton, not runnable)

    write tree:
      root_path/
        app/entry.[py|kt|tsx]
        app/screens/<Screens>.py or .kt
        app/theme/colors.json
```

## 2. Widget catalogue

Psevdo — sliding from the search results we pick:

* Material3: NavigationDrawer, BottomSheet (modal+standard), Snackbar, Cards (elevated/filled/outlined), Buttons (MDButton/MDButtonText MD2.x API), AppBar (MDTopAppBar), Tabs (MDTabs), Slider, Switch, TextField
* Cupertino: ActionSheet, AlertDialog (kept minor)
* Compose MDC skeleton: Card, Scaffold, TopAppBar, ElevatedCard, FilledTextField, AssistChip (coroutines; not runnable here)

`ui_widgets_list` returns the catalogue so the AI picks by name.

## 3. Screen scaffold

Psevdo:

```
async def screen_scaffold(root_path, framework, screen_name,
                          components: List[str],
                          nav: "drawer" | "bottom_bar" | "tabs" | "none") -> Dict:
    write screens/<screen_name>.py|kt
    include chosen components, wire on_press callbacks as no-op
    return path + line_count
```

## 4. Adaptive launcher icon generator

Psevdo:

```
async def apk_icon_generate(
    root_path,
    prompt:      # AI prompt for the foreground; canvas image embedded as base64
                # OR existing image bytes
    accent: "#RRGGBB",
    bg_mode:     # "solid" | "gradient" | "trans"
    foreground_path: Optional[bytes path]
    style: "adaptive" | "legacy"
) -> Dict:
    plan:
      if foreground_path supplied: read bytes
      else:        require client image-base64 OR seed elliptical gradient

      build alpha-safe PNG 1024x1024 foreground (resample < 432 inner)
      save as drawable/ic_launcher_foreground.png
      build background layer 1024x1024 (solid or solid→solid gradient)
      save as drawable/ic_launcher_background.png
      write mipmap-anydpi-v26/ic_launcher.xml (adaptive manifest)
      write mipmap-anydpi-v26/ic_launcher_round.xml
      write values/colors.xml (ic_launcher_background)
      write values/ic_launcher_background.xml (legacy color fallback)

      emit monochrome variant for status bar (Android 13+ themedIcons)
      save as drawable/ic_launcher_monochrome.png
```

Library-free path because Termux/Android PIL is fragile — use only `zlib`
+ `struct` to emit minimal PNGs. Foreground compositing via simple Pillow
when available; fallback is `cairo` (rare) or pure-std RGBA bitmap. The
**worker** produces a structured bitmap that the AI can refine; the AI
typically seeds its own image first via an external API.

## 5. Asset pack generator

Psevdo:

```
async def apk_asset_pack(root_path, blueprint) -> Dict:
    writes:
      res/values/strings.xml (app_name, package_name, locale buckets)
      res/values/colors.xml (primary, secondary, on_primary, surface)
      res/values/themes.xml (MD3 theme is the default)
      res/values-*/strings.xml stubs for already-locales
      res/mipmap-anydpi-v26/ic_launcher.xml + ic_launcher_round.xml
      res/values/styles.xml  (legacy Theme.AppCompat fallback)
```

## 6. Static lint pass

Psevdo:

```
async def apk_dryrun_lint(root_path) -> Dict:
    findings:
      - package conflicts with reserved words
      - missing INTERNET permission when requirements include requests/urllib
      - min_sdk < 21 → fail
      - python_version not in {3.11,3.12,3.13} → fail
      - title contains emoji or html escape arrow
      - orientation not in {landscape,portrait,all,sensor}
      - icon missing
    return {ok, findings, blocking}
```

## 7. AAB bundle mode

Psevdo:

```
async def apk_release_aab(root_path, timeout_s=1800) -> Dict:
    run buildozer android release --bundle
    env: GRADLE_OPTS, ANDROID_HOME (must be set by caller)
    return last 200 stdout lines
    on fail: hint about -d (deps download offline)
```

## Constraints

* Each tool returns the same envelope shape: `status`, `tool`, `error`
  (cf. Pitfall 13 in polyglot-orchestration).
* The Python 3.11+ `tomllib` is **not** required; use raw strings for
  buildozer.spec generation (matches existing project style).
* No new third-party deps — `apk_icon_generate` uses only `zlib/struct`.
  Pillow usage optional, behind a try/except.
* Each tool runs on the executor (Pitfall 12): `loop.run_in_executor`
  wrap for any disk-touching work, but exec is fast here so sync
  inline is fine for non-blocking paths.
