import json
import os
import uuid
from pathlib import Path
from flask import Flask, Response, abort, jsonify, render_template, request
from utils.zsh_theme import ZshTheme

class ProfileBuilder:
    COLORS = ["Foreground Color", "Background Color", "Bold Color", "Cursor Color", "Cursor Text Color",
              "Selection Color", "Selected Text Color", "Link Color", "Badge Color", "Cursor Guide Color"]
    COLORS += [f"Ansi {i} Color" for i in range(16)]
    CURSORS = {"0": "Sublinhado", "1": "Barra vertical", "2": "Bloco"}
    RGB = ("Red Component", "Green Component", "Blue Component")

    def __init__(self, path):
        self.base = json.loads(Path(path).read_text())

    @classmethod
    def to_hex(cls, color):
        return "#" + "".join(f"{round(color.get(k, 0) * 255):02x}" for k in cls.RGB)

    @classmethod
    def to_color(cls, value):
        value = value.lstrip("#")
        color = {k: int(value[i:i + 2], 16) / 255 for k, i in zip(cls.RGB, (0, 2, 4))}
        return {**color, "Alpha Component": 1, "Color Space": "sRGB"}

    def defaults(self):
        b = self.base
        font, _, size = b.get("Normal Font", "Menlo-Regular 13").rpartition(" ")
        return {
            "name": b.get("Name", "Default"),
            "font": font,
            "size": size,
            "columns": b.get("Columns", 80),
            "rows": b.get("Rows", 25),
            "transparency": round(b.get("Transparency", 0) * 100),
            "blur": b.get("Blur", False),
            "cursor": str(b.get("Cursor Type", 2)),
            "blink": b.get("Blinking Cursor", False),
            "scrollback": b.get("Scrollback Lines", 1000),
            "unlimited": b.get("Unlimited Scrollback", False),
            "colors": {k: self.to_hex(b.get(k, {})) for k in self.COLORS},
        }

    def build(self, form):
        font = f"{form['font']} {form['size']}"
        profile = {**self.base,
                   "Name": form["name"],
                   "Guid": str(uuid.uuid4()).upper(),
                   "Normal Font": font,
                   "Non Ascii Font": font,
                   "Columns": int(form["columns"]),
                   "Rows": int(form["rows"]),
                   "Transparency": int(form["transparency"]) / 100,
                   "Blur": "blur" in form,
                   "Cursor Type": int(form["cursor"]),
                   "Blinking Cursor": "blink" in form,
                   "Scrollback Lines": int(form["scrollback"]),
                   "Unlimited Scrollback": "unlimited" in form,
                   "Default Bookmark": "No"}
        for k in self.COLORS:
            color = self.to_color(form[k])
            profile[k] = profile[f"{k} (Dark)"] = profile[f"{k} (Light)"] = color
        return profile

    @staticmethod
    def filename(name):
        return ("".join(ch for ch in name if ch.isalnum() or ch in "-_") or "profile") + ".json"


app = Flask(__name__)
builder = ProfileBuilder(Path(__file__).with_name("parabellum.json"))
THEMES_DIR = os.environ.get("PARABELLUM_THEMES_DIR",
                            str(Path(__file__).resolve().parent.parent / "parabellum-zsh-theme"))


@app.get("/")
def index():
    return render_template("index.html", d=builder.defaults(), cursors=builder.CURSORS, themes_dir=THEMES_DIR)


@app.get("/themes")
def themes():
    return jsonify(ZshTheme.list(request.args.get("dir", THEMES_DIR)))


@app.get("/themes/<name>")
def theme(name):
    directory = Path(request.args.get("dir", THEMES_DIR)).expanduser()
    if name not in ZshTheme.list(directory):
        abort(404)
    t = ZshTheme(directory / f"{name}.zsh-theme")
    return jsonify({"name": t.name, "prompt": t.render()})


@app.post("/export")
def export():
    profile = builder.build(request.form)
    return Response(json.dumps(profile, indent=2), mimetype="application/json",
                    headers={"Content-Disposition": f"attachment; filename={builder.filename(profile['Name'])}"})


if __name__ == "__main__":
    app.run(debug=True)
