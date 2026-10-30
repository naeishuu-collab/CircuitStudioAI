"""Minimal native Windows desktop UI built with Python's standard Tk toolkit."""

import json
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .analysis import analyze
from .dsl import DslError, parse_circuit
from .kicad import compile_project, find_kicad_cli, run_native_check
from .pcb import inspect_board
from .providers import OpenAICompatibleProvider
from .spice import simulate
from .sexpr import require_root

ROOT = Path(__file__).resolve().parent.parent


class CircuitStudioApp:
    def __init__(self, root):
        self.root = root
        root.title("CircuitStudio AI — オフライン回路設計")
        root.geometry("1120x780")
        root.minsize(900, 620)
        self.file_path = None
        self._busy = False
        self._task_queue = queue.Queue()
        self._action_buttons = []
        self._build()
        root.after(100, self._drain_task_queue)

    def _build(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="日本語の設計指示", font=("Yu Gothic UI", 11, "bold")).pack(anchor="w")
        self.instruction = tk.Text(top, height=3, wrap="word")
        self.instruction.pack(fill="x", pady=(4, 8))
        bar = ttk.Frame(top)
        bar.pack(fill="x")
        for title, action in (("AIからDSL案", self.generate_ai), ("DSLを開く", self.load_dsl),
                              ("サンプル", self.load_sample), ("DSL保存", self.save_dsl),
                              ("検証してKiCad出力", self.compile), ("回路図/ERC", self.open_schematic),
                              ("既存PCB評価", self.open_board), ("SPICE実行", self.open_spice),
                              ("KiCad起動", self.launch_kicad)):
            button = ttk.Button(bar, text=title, command=action)
            button.pack(side="left", padx=(0, 5), pady=2)
            self._action_buttons.append(button)
        ttk.Label(self.root, text="CircuitDSL (JSON形式はそのままYAML 1.2としても有効です)", padding=(10, 2),
                  font=("Yu Gothic UI", 11, "bold")).pack(anchor="w")
        split = ttk.Panedwindow(self.root, orient="vertical")
        split.pack(fill="both", expand=True, padx=10, pady=(2, 8))
        dsl_frame = ttk.Frame(split)
        result_frame = ttk.Frame(split)
        split.add(dsl_frame, weight=3)
        split.add(result_frame, weight=2)
        self.editor = tk.Text(dsl_frame, wrap="none", undo=True, font=("Consolas", 10))
        yscroll = ttk.Scrollbar(dsl_frame, orient="vertical", command=self.editor.yview)
        xscroll = ttk.Scrollbar(dsl_frame, orient="horizontal", command=self.editor.xview)
        self.editor.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.editor.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        dsl_frame.columnconfigure(0, weight=1)
        dsl_frame.rowconfigure(0, weight=1)
        ttk.Label(result_frame, text="診断・実行履歴", font=("Yu Gothic UI", 11, "bold")).pack(anchor="w")
        self.results = tk.Text(result_frame, height=10, wrap="word", state="disabled", font=("Yu Gothic UI", 9))
        self.results.pack(fill="both", expand=True, pady=(4, 0))
        self._log("手動DSLはAPIキーなしで利用できます。KiCad ERC/DRCとSPICEは実行環境に依存します。")

    def _log(self, message):
        self.results.configure(state="normal")
        self.results.insert("end", message.rstrip() + "\n\n")
        self.results.see("end")
        self.results.configure(state="disabled")

    def _dsl_text(self):
        return self.editor.get("1.0", "end-1c")

    def _set_dsl(self, text):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", text)

    def load_dsl(self):
        path = filedialog.askopenfilename(filetypes=[("CircuitDSL", "*.circuit.yaml *.circuit.json *.yaml *.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
            parse_circuit(text)
        except (OSError, DslError, UnicodeError) as exc:
            messagebox.showerror("DSL読み込みエラー", str(exc))
            return
        self.file_path = Path(path)
        self._set_dsl(text)
        self._log(f"DSLを読み込みました: {self.file_path}")

    def load_sample(self):
        path = filedialog.askopenfilename(initialdir=ROOT / "samples", filetypes=[("CircuitDSL", "*.circuit.yaml")])
        if not path:
            return
        self.file_path = Path(path)
        self._set_dsl(self.file_path.read_text(encoding="utf-8-sig"))
        self._log(f"サンプルを開きました: {self.file_path.name}")

    def save_dsl(self):
        path = filedialog.asksaveasfilename(defaultextension=".circuit.yaml", filetypes=[("CircuitDSL", "*.circuit.yaml"), ("JSON", "*.json")])
        if not path:
            return
        target = Path(path)
        if target.exists() and not messagebox.askyesno("上書き確認", f"既存ファイルをバックアップして上書きしますか？\n{target}"):
            return
        if target.exists():
            backup = target.with_suffix(target.suffix + ".bak")
            if backup.exists():
                messagebox.showerror("保存エラー", f"既存バックアップを保持するため保存しません: {backup}")
                return
            target.replace(backup)
        target.write_text(self._dsl_text(), encoding="utf-8")
        self.file_path = target
        self._log(f"DSLを保存しました: {target}")

    def generate_ai(self):
        instruction = self.instruction.get("1.0", "end-1c").strip()
        if not instruction:
            messagebox.showerror("AI DSL案を作れません", "日本語の設計指示を入力してください。")
            return

        def action():
            schema = json.loads((ROOT / "schemas" / "circuit-v2.schema.json").read_text(encoding="utf-8"))
            generated = OpenAICompatibleProvider().generate(instruction, schema)
            data = parse_circuit(generated)
            return generated, analyze(data)[0]

        def completed(result):
            generated, diagnostics = result
            self._set_dsl(generated)
            self._log("AIが返したDSLを構文/スキーマ検証しました。KiCadへはまだ出力していません。\n" + _format_diagnostics(diagnostics))

        self._run_background("AI DSL案生成", action, completed, "AI DSL案を作れません")

    def compile(self):
        try:
            data = parse_circuit(self._dsl_text())
        except DslError as exc:
            messagebox.showerror("DSL検証エラー", str(exc))
            return
        parent = filedialog.askdirectory(title="プロジェクト出力先を選択")
        if not parent:
            return
        def completed(result):
            self._show_compile_result(result)

        self._run_background("回路図/PCB生成とKiCad検証", lambda: compile_project(data, parent), completed, "KiCad出力エラー")

    def _show_compile_result(self, result):
        exports = result["native_exports"]
        pcb = exports["pcb"]
        self._log(f"出力状態: {result['status']}\nKiCad ERC: {result['native_erc']['status']}\n"
                  f"KiCad netlist/SVG: {exports['netlist']['status']} / {exports['svg']['status']}\n"
                  f"PCB/DRC/製造判定: {pcb['status']} / {pcb.get('native_drc', {}).get('status', 'NOT_EXECUTED')} / {pcb.get('manufacturing_status', 'NOT_PROVEN')}\n"
                  f"SPICEデッキ/実行: {exports.get('spice', {}).get('status', 'NOT_EXECUTED')}\n"
                  f"電気承認: {result['electrical_approval']}\n" + _format_diagnostics_from_dict(result["diagnostics"]) +
                  "\nファイル:\n" + "\n".join(result["outputs"]))

    def open_schematic(self):
        path = filedialog.askopenfilename(filetypes=[("KiCad schematic", "*.kicad_sch"), ("All files", "*.*")])
        if not path:
            return

        def action():
            schematic_path = Path(path)
            if schematic_path.stat().st_size > 64_000_000:
                raise ValueError("回路図が64 MB上限を超えています。")
            text = schematic_path.read_text(encoding="utf-8-sig")
            require_root(text, "kicad_sch")
            check = run_native_check("erc", path)
            return check

        def completed(check):
            self._log(f"回路図読み込み: {path}\nERC: {check['status']}\n{check.get('reason', check.get('stderr', check.get('report', '')))}")

        self._run_background("回路図ERC評価", action, completed, "回路図評価エラー")

    def open_board(self):
        path = filedialog.askopenfilename(filetypes=[("KiCad board", "*.kicad_pcb"), ("All files", "*.*")])
        if not path:
            return
        def completed(report):
            self._show_board_report(path, report)

        self._run_background("既存PCBの構造/DRC評価", lambda: inspect_board(path), completed, "PCB評価エラー")

    def _show_board_report(self, path, report):
        self._log("PCB構造サマリー:\n" + json.dumps(report, ensure_ascii=False, indent=2))
        if messagebox.askyesno("評価レポート", "評価結果JSONを保存しますか？"):
            target = filedialog.asksaveasfilename(defaultextension=".json", initialfile="pcb_diagnostics.json")
            if target:
                if Path(target).exists():
                    messagebox.showerror("保存エラー", "既存ファイルを上書きしないため、別の保存先を選んでください。")
                    return
                Path(target).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                self._log(f"評価結果を保存しました: {target}")

    def open_spice(self):
        path = filedialog.askopenfilename(filetypes=[("SPICE", "*.cir *.sp *.spi *.spice"), ("All files", "*.*")])
        if not path:
            return
        self._run_background("SPICEシミュレーション", lambda: simulate(path),
                             lambda result: self._log("SPICE: " + json.dumps(result, ensure_ascii=False, indent=2)),
                             "SPICEエラー")

    def _run_background(self, label, action, completed, error_title):
        if self._busy:
            self._log("別の処理が実行中です。完了後に再試行してください。")
            return
        self._busy = True
        for button in self._action_buttons:
            button.configure(state="disabled")
        self._log(label + "を開始しました。")

        def worker():
            try:
                result, error = action(), None
            except Exception as exc:
                result, error = None, exc

            def deliver(result=result, error=error):
                try:
                    if error is not None:
                        messagebox.showerror(error_title, str(error))
                    else:
                        completed(result)
                except Exception as exc:
                    messagebox.showerror("処理結果の表示エラー", str(exc))
                finally:
                    self._busy = False
                    for button in self._action_buttons:
                        button.configure(state="normal")
            self._task_queue.put(deliver)

        threading.Thread(target=worker, daemon=True).start()

    def _drain_task_queue(self):
        try:
            while True:
                self._task_queue.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(100, self._drain_task_queue)

    def launch_kicad(self):
        path = filedialog.askopenfilename(filetypes=[("KiCad project", "*.kicad_pro *.kicad_sch *.kicad_pcb"), ("All files", "*.*")])
        if not path:
            return
        cli = find_kicad_cli()
        exe = Path(cli).with_name("kicad.exe") if cli else None
        if not exe or not exe.is_file():
            messagebox.showinfo("KiCad未検出", "KiCadの起動ファイルが見つかりません。プロジェクトはディスクに保存されています。")
            return
        try:
            subprocess.Popen([str(exe), path], shell=False)
            self._log(f"KiCadを起動しました: {path}")
        except OSError as exc:
            messagebox.showerror("KiCad起動エラー", str(exc))


def _format_diagnostics(diagnostics):
    return "\n".join(f"{d.status} [{d.severity}] {d.id}: {d.evidence}\n  対応: {d.recommendation}" for d in diagnostics) or "診断なし"


def _format_diagnostics_from_dict(diagnostics):
    return "\n".join(f"{d['status']} [{d['severity']}] {d['id']}: {d['evidence']}\n  対応: {d['recommendation']}" for d in diagnostics) or "診断なし"


def main():
    root = tk.Tk()
    CircuitStudioApp(root)
    root.mainloop()
