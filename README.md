# Foundation

A personal learning platform for Linux that enforces the Feynman Technique.

## What it does

Organise your learning into **Subjects → Courses → Lessons**. To mark a lesson complete you must
write an explanation in your own words — no passive reading counts as done. The app tracks your
progress with a per-course progress bar and a full activity log.

Additional features:

- **Bookmarks** dashboard — drag-reorderable quick-access links, CSV import/export
- **PDF and video lessons** — open files and URLs in your default viewer
- **Markdown text lessons** — write and read notes inside the app
- **Export courses** to Markdown
- **Settings** — color scheme (light/dark/system), Feynman minimum character count, grid columns
- Data stored locally in SQLite (`~/.local/share/foundation/foundation.db`)

## Requirements

- Linux
- GNOME 49 or later (org.gnome.Platform//49)
- Flatpak

## Install

Download `foundation.flatpak` from the [Releases](https://github.com/cha1tany4/foundation-gtk/releases) page, then:

```bash
flatpak install foundation.flatpak
```

> Flathub distribution is planned for a future release.

## Build from source

Install prerequisites:

```bash
sudo apt install flatpak-builder
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user org.gnome.Platform//49 org.gnome.Sdk//49
```

Build and install locally:

```bash
flatpak-builder --user --install --force-clean build-dir io.github.cha1tany4.foundation.json
```

## Run

```bash
flatpak run io.github.cha1tany4.foundation
```

## License

MIT — see [LICENSE](LICENSE).
