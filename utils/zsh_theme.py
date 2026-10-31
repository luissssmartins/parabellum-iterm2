import re
from pathlib import Path

class ZshTheme:
    NAME_RE = re.compile(r"(?m)^[ \t]*(?:export[ \t]+|local[ \t]+|typeset[ \t]+)?([A-Za-z_]\w*)=")
    VAR_RE = re.compile(r"\$\{([A-Za-z_]\w*)\}|\$([A-Za-z_]\w*)")
    CMD_RE = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")
    ZSTYLE_RE = re.compile(r"zstyle[ \t]+\S+[ \t]+(\w+)[ \t]+")

    COLOR_NAMES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
    SAMPLE = {"user": "user", "host": "host", "home": "/Users/user", "cwd": "/Users/user/projetos/parabellum",
              "branch": "main", "venv": "venv"}
    ESCAPES = {"n": "\n", "t": "\t", "e": "\x1b", "\\": "\\", "'": "'", '"': '"'}

    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.name.removesuffix(".zsh-theme")
        text = self.path.read_text(errors="replace")
        self.vars, self.zstyles = {}, {}

        for m in self.NAME_RE.finditer(text):
            self.vars.setdefault(m.group(1), self.read_word(text, m.end())[0])
        for m in self.ZSTYLE_RE.finditer(text):
            self.zstyles.setdefault(m.group(1), self.read_word(text, m.end())[0])

    @staticmethod
    def list(directory):
        directory = Path(directory).expanduser()
        if not directory.is_dir():
            return []
        return sorted(p.name.removesuffix(".zsh-theme") for p in directory.glob("*.zsh-theme"))

    @classmethod
    def read_word(cls, text, i):
        out = []
        while i < len(text) and text[i] not in " \t\n;":
            if text.startswith("$'", i):
                i += 2
                while i < len(text) and text[i] != "'":
                    if text[i] == "\\" and i + 1 < len(text):
                        out.append(cls.ESCAPES.get(text[i + 1], "\\" + text[i + 1]))
                        i += 2
                    else:
                        out.append(text[i])
                        i += 1
                i += 1
            elif text[i] == "'":
                end = text.find("'", i + 1)
                end = len(text) if end < 0 else end
                out.append(text[i + 1:end])
                i = end + 1
            elif text[i] == '"':
                i += 1
                while i < len(text) and text[i] != '"':
                    if text[i] == "\\" and i + 1 < len(text) and text[i + 1] in '"\\$`':
                        out.append(text[i + 1])
                        i += 2
                    else:
                        out.append(text[i])
                        i += 1
                i += 1
            else:
                out.append(text[i])
                i += 1
        return "".join(out), i

    @staticmethod
    def xterm_hex(n):
        if n < 232:
            n -= 16
            steps = [0, 95, 135, 175, 215, 255]
            rgb = (steps[n // 36], steps[n // 6 % 6], steps[n % 6])
        else:
            rgb = (8 + (n - 232) * 10,) * 3
        return "#" + "".join(f"{c:02x}" for c in rgb)

    @classmethod
    def parse_color(cls, value):
        value = value.strip().lower()
        if value.isdigit():
            n = int(value)
            return n if n < 16 else cls.xterm_hex(min(n, 255))
        if value in cls.COLOR_NAMES:
            return cls.COLOR_NAMES.index(value)
        if value.startswith("bright") and value[6:].strip("-_") in cls.COLOR_NAMES:
            return cls.COLOR_NAMES.index(value[6:].strip("-_")) + 8
        if re.fullmatch(r"#[0-9a-f]{3}", value):
            return "#" + "".join(c * 2 for c in value[1:])
        if re.fullmatch(r"#[0-9a-f]{6}", value):
            return value
        return None

    def expand(self, value, depth=0):
        if depth > 8:
            return value
        
        value = self.CMD_RE \
            .sub(lambda m: self.command((m.group(1) or m.group(2)).strip(), depth), value)

        def var(m):
            name = m.group(1) or m.group(2)
            if name == "vcs_info_msg_0_":
                return self.vcs_info(depth)
            if name in self.vars:
                return self.expand(self.vars[name], depth + 1)
            return {"USER": self.SAMPLE["user"], "HOST": self.SAMPLE["host"], "HOME": self.SAMPLE["home"],
                    "PWD": self.SAMPLE["cwd"]}.get(name, "")

        return self.VAR_RE.sub(var, value)

    def command(self, cmd, depth):
        if cmd.startswith("git_prompt_info"):
            v = lambda k: self.expand(self.vars.get(k, ""), depth + 1)
            return (v("ZSH_THEME_GIT_PROMPT_PREFIX") + self.SAMPLE["branch"]
                    + v("ZSH_THEME_GIT_PROMPT_DIRTY") + v("ZSH_THEME_GIT_PROMPT_SUFFIX"))
        return ""

    def vcs_info(self, depth):
        fmt = self.expand(self.zstyles.get("formats", ""), depth + 1)
        fields = {"b": self.SAMPLE["branch"], "s": "git", "r": "parabellum", "a": "",
                  "u": self.expand(self.zstyles.get("unstagedstr", ""), depth + 1),
                  "c": self.expand(self.zstyles.get("stagedstr", ""), depth + 1)}
        return re.sub(r"%([bsrauc])", lambda m: fields[m.group(1)], fmt)

    def render(self, var="PROMPT"):
        return self.render_prompt(self.expand(self.vars.get(var, "%n@%m %~ %# ")))

    @classmethod
    def render_prompt(cls, prompt):
        segments, state, buf = [], {"fg": None, "bg": None, "bold": False, "underline": False}, []

        def flush():
            if buf:
                segments.append({"text": "".join(buf), **state})
                buf.clear()

        def set_style(key, value):
            if state[key] != value:
                flush()
                state[key] = value

        sample = cls.SAMPLE
        cwd = sample["cwd"].replace(sample["home"], "~", 1)
        i = 0
        while i < len(prompt):
            ch = prompt[i]
            if ch != "%" or i + 1 >= len(prompt):
                buf.append(ch)
                i += 1
                continue
            start = i
            i += 1
            num = re.match(r"-?\d*", prompt[i:]).group()
            i += len(num)
            code = prompt[i] if i < len(prompt) else ""
            i += 1
            arg = None
            if code in "FK" and prompt.startswith("{", i):
                end = prompt.find("}", i)
                end = len(prompt) if end < 0 else end
                arg, i = prompt[i + 1:end], end + 1
            if code == "F":
                set_style("fg", cls.parse_color(arg if arg is not None else num))
            elif code == "f":
                set_style("fg", None)
            elif code == "K":
                set_style("bg", cls.parse_color(arg if arg is not None else num))
            elif code == "k":
                set_style("bg", None)
            elif code in "BbUu":
                set_style("bold" if code in "Bb" else "underline", code.isupper())
            elif code == "(":
                j = i
                while j < len(prompt) and (prompt[j].isalnum() or prompt[j] in "?!#-"):
                    j += 1
                sep = prompt[j] if j < len(prompt) else "."
                end_true = prompt.find(sep, j + 1)
                end_all = prompt.find(")", end_true + 1)
                if end_true < 0 or end_all < 0:
                    break
                prompt = prompt[:start] + prompt[j + 1:end_true] + prompt[end_all + 1:]
                i = start
            else:
                text = {
                    "%": "%", ")": ")", "n": sample["user"], "m": sample["host"], "M": sample["host"] + ".local",
                    "#": "%", "?": "0", "h": "42", "!": "42", "y": "ttys000", "l": "ttys000",
                    "T": "19:22", "t": "7:22PM", "@": "7:22PM", "*": "19:22:05", "D": "26-10-31", "j": "0", "L": "1",
                    "/": sample["cwd"], "d": sample["cwd"], "~": cwd, "c": cwd.rsplit("/", 1)[-1],
                    ".": cwd.rsplit("/", 1)[-1], "C": cwd.rsplit("/", 1)[-1],
                }.get(code, "")
                if code in "~/d" and num.lstrip("-").isdigit() and int(num) > 0:
                    text = "/".join(text.split("/")[-int(num):])
                buf.append(text)
        flush()
        return segments
