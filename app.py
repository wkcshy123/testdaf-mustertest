# -*- coding: utf-8 -*-
"""
德语转语音 · Deutsch → Sprache
Apple-style GUI · Powered by Qwen-TTS
"""
import os
import sys
import threading
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk
import requests
import dashscope

# ──────────────────── API 配置 ────────────────────
dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

# ──────────────────── 音色 & 模型 ────────────────────
VOICES = [
    ("Cherry",  "芊悦 · 女声 · 阳光亲切"),
    ("Serena",  "苏瑶 · 女声 · 温柔如水"),
    ("Ethan",   "晨煦 · 男声 · 阳光温暖"),
    ("Maia",    "四月 · 女声 · 知性温柔"),
    ("Moon",    "月白 · 男声 · 率性帅气"),
    ("Kai",     "凯 · 男声 · 治愈低音"),
    ("Neil",    "阿闻 · 男声 · 新闻主播"),
    ("Mochi",   "沙小弥 · 男声 · 聪慧少年"),
    ("Mia",     "乖小妹 · 女声 · 温顺恬静"),
    ("Elias",   "墨讲师 · 女声 · 娓娓道来"),
]

MODEL = "qwen3-tts-flash"

# ──────────────────── 主题色 ────────────────────
# Apple 风格浅灰调色板，亮色模式
BLUE   = "#007AFF"   # iOS 蓝
GREEN  = "#34C759"
RED    = "#FF3B30"
GRAY1  = "#F2F2F7"   # 背景底色
GRAY2  = "#FFFFFF"   # 卡片背景
GRAY3  = "#E5E5EA"   # 分隔线 / 边框
GRAY4  = "#C7C7CC"   # placeholder
GRAY5  = "#8E8E93"   # 次要文字
GRAY6  = "#3A3A3C"   # 主文字
GRAY7  = "#1C1C1E"   # 标题
RADIUS = 14          # 全局圆角


class App(ctk.CTk):
    """主窗口"""

    def __init__(self):
        super().__init__()

        # ── 窗口 ──
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.title("德语转语音")
        self.geometry("680x820")
        self.minsize(580, 700)

        # ── 状态 ──
        self.is_running = False

        # ── 布局 ──
        self._build()
        self._center()

    # ────────────────────────────────────────────────────
    #  布局
    # ────────────────────────────────────────────────────
    def _build(self):
        # 外层可滚动
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=GRAY1, corner_radius=0,
            scrollbar_button_color=GRAY3,
            scrollbar_button_hover_color=GRAY4,
        )
        self.scroll.pack(fill="both", expand=True)

        # 内容容器 — 限宽居中
        container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        container.pack(fill="x", padx=24, pady=(16, 24))

        # ── 标题区 ──
        self._build_header(container)

        # ── API Key ──
        self._build_apikey_card(container)

        # ── 音色选择 ──
        self._build_voice_card(container)

        # ── 文本输入 ──
        self._build_text_card(container)

        # ── 输出设置 ──
        self._build_output_card(container)

        # ── 操作区 ──
        self._build_action(container)

        # ── 底部 ──
        self._build_footer(container)

    # ─────────── Header ───────────
    def _build_header(self, parent):
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            hdr, text="德语转语音",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=GRAY7,
        ).pack(anchor="w")

        ctk.CTkLabel(
            hdr, text="Deutsch → Sprache · Powered by Qwen-TTS",
            font=ctk.CTkFont(size=13),
            text_color=GRAY5,
        ).pack(anchor="w", pady=(2, 0))

    # ─────────── Card 辅助 ───────────
    def _card(self, parent, title: str, *, pady=(12, 0)):
        """创建一张 Apple 风格白色卡片，返回内容 Frame"""
        card = ctk.CTkFrame(
            parent, fg_color=GRAY2, corner_radius=RADIUS,
            border_width=0.5, border_color=GRAY3,
        )
        card.pack(fill="x", pady=pady)

        # 标题
        ctk.CTkLabel(
            card, text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=GRAY5,
        ).pack(anchor="w", padx=20, pady=(16, 0))

        # 内容区
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=20, pady=(8, 16))
        return body

    # ─────────── API Key ───────────
    def _build_apikey_card(self, parent):
        body = self._card(parent, "API KEY")

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")

        self.apikey_entry = ctk.CTkEntry(
            row, placeholder_text="请输入阿里云百炼 API Key",
            show="•", height=42, corner_radius=10,
            font=ctk.CTkFont(size=14),
            border_width=1, border_color=GRAY3,
            fg_color=GRAY1, text_color=GRAY6,
        )
        self.apikey_entry.pack(side="left", fill="x", expand=True)

        self._show_key = False
        self.eye_btn = ctk.CTkButton(
            row, text="👁", width=42, height=42,
            corner_radius=10, fg_color=GRAY1,
            hover_color=GRAY3, text_color=GRAY5,
            font=ctk.CTkFont(size=16),
            border_width=1, border_color=GRAY3,
            command=self._toggle_key,
        )
        self.eye_btn.pack(side="left", padx=(8, 0))

        ctk.CTkLabel(
            body, text="仅在本地使用，不会上传到第三方服务器",
            font=ctk.CTkFont(size=11), text_color=GRAY4,
        ).pack(anchor="w", pady=(6, 0))

    def _toggle_key(self):
        self._show_key = not self._show_key
        self.apikey_entry.configure(show="" if self._show_key else "•")

    # ─────────── 音色 ───────────
    def _build_voice_card(self, parent):
        body = self._card(parent, "音色选择")

        # 下拉框
        display_list = [f"{v[0]}  —  {v[1]}" for v in VOICES]
        self.voice_menu = ctk.CTkOptionMenu(
            body, values=display_list,
            height=40, corner_radius=10,
            font=ctk.CTkFont(size=13),
            dropdown_font=ctk.CTkFont(size=13),
            fg_color=GRAY1, button_color=GRAY3,
            button_hover_color=GRAY4,
            text_color=GRAY6,
            dropdown_fg_color=GRAY2,
            dropdown_text_color=GRAY6,
            dropdown_hover_color="#E8E8ED",
            command=self._on_voice_change,
        )
        self.voice_menu.pack(fill="x")
        self.voice_val = VOICES[0][0]

        ctk.CTkLabel(
            body,
            text="所有音色均支持德语 · 语言参数自动设为 German",
            font=ctk.CTkFont(size=11), text_color=GRAY4,
        ).pack(anchor="w", pady=(8, 0))

    def _on_voice_change(self, choice: str):
        self.voice_val = choice.split("  —  ")[0].strip()

    # ─────────── 文本输入 ───────────
    def _build_text_card(self, parent):
        body = self._card(parent, "德语文本")

        self.textbox = ctk.CTkTextbox(
            body, height=220, corner_radius=10,
            font=ctk.CTkFont(family="Menlo", size=14),
            fg_color=GRAY1, text_color=GRAY6,
            border_width=1, border_color=GRAY3,
            scrollbar_button_color=GRAY3,
            wrap="word",
        )
        self.textbox.pack(fill="x")

        # 占位文字
        self._ph = "在此输入或粘贴德语文字…\n\nBeispiel: Guten Tag! Wie geht es Ihnen heute? Ich hoffe, Sie haben einen wunderbaren Tag."
        self._ph_active = True
        self.textbox.insert("0.0", self._ph)
        self.textbox.configure(text_color=GRAY4)
        self.textbox.bind("<FocusIn>", self._ph_in)
        self.textbox.bind("<FocusOut>", self._ph_out)
        self.textbox.bind("<KeyRelease>", self._update_count)

        # 字数
        self.count_label = ctk.CTkLabel(
            body, text="0 字符",
            font=ctk.CTkFont(size=11), text_color=GRAY4,
        )
        self.count_label.pack(anchor="e", pady=(4, 0))

    def _ph_in(self, _):
        if self._ph_active:
            self.textbox.delete("0.0", "end")
            self.textbox.configure(text_color=GRAY6)
            self._ph_active = False

    def _ph_out(self, _):
        if not self.textbox.get("0.0", "end").strip():
            self.textbox.insert("0.0", self._ph)
            self.textbox.configure(text_color=GRAY4)
            self._ph_active = True

    def _update_count(self, _=None):
        if not self._ph_active:
            n = len(self.textbox.get("0.0", "end").strip())
            self.count_label.configure(text=f"{n} 字符")

    # ─────────── 输出设置 ───────────
    def _build_output_card(self, parent):
        body = self._card(parent, "保存位置")

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")

        self.path_var = ctk.StringVar(
            value=os.path.join(os.path.expanduser("~/Desktop"), "output.wav")
        )
        self.path_entry = ctk.CTkEntry(
            row, textvariable=self.path_var,
            height=42, corner_radius=10,
            font=ctk.CTkFont(family="Menlo", size=12),
            border_width=1, border_color=GRAY3,
            fg_color=GRAY1, text_color=GRAY6,
        )
        self.path_entry.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            row, text="浏览…", width=72, height=42,
            corner_radius=10,
            font=ctk.CTkFont(size=13),
            fg_color=GRAY1, hover_color=GRAY3,
            text_color=BLUE, border_width=1, border_color=GRAY3,
            command=self._browse,
        ).pack(side="left", padx=(8, 0))

        # 快捷位置
        shortcuts = ctk.CTkFrame(body, fg_color="transparent")
        shortcuts.pack(fill="x", pady=(8, 0))

        for label, path in [
            ("桌面", "~/Desktop"),
            ("文稿", "~/Documents"),
            ("下载", "~/Downloads"),
        ]:
            ctk.CTkButton(
                shortcuts, text=label, width=60, height=28,
                corner_radius=8,
                font=ctk.CTkFont(size=12),
                fg_color=GRAY1, hover_color=GRAY3,
                text_color=BLUE, border_width=0,
                command=lambda p=path: self._quick_path(p),
            ).pack(side="left", padx=(0, 6))

    def _browse(self):
        p = filedialog.asksaveasfilename(
            title="选择保存位置",
            defaultextension=".wav",
            filetypes=[("WAV 音频", "*.wav"), ("所有文件", "*.*")],
            initialdir=os.path.expanduser("~/Desktop"),
        )
        if p:
            self.path_var.set(p)

    def _quick_path(self, base: str):
        d = os.path.expanduser(base)
        fn = f"german_tts_{datetime.now().strftime('%H%M%S')}.wav"
        self.path_var.set(os.path.join(d, fn))

    # ─────────── 操作区 ───────────
    def _build_action(self, parent):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.pack(fill="x", pady=(20, 0))

        self.btn = ctk.CTkButton(
            wrap, text="开始转录",
            height=50, corner_radius=RADIUS,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=BLUE, hover_color="#005EC4",
            text_color="#FFFFFF",
            command=self._start,
        )
        self.btn.pack(fill="x")

        self.progress = ctk.CTkProgressBar(
            wrap, height=4, corner_radius=2,
            fg_color=GRAY3, progress_color=BLUE,
        )
        self.progress.pack(fill="x", pady=(10, 0))
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(
            wrap, text="就绪",
            font=ctk.CTkFont(size=12), text_color=GRAY5,
        )
        self.status_label.pack(anchor="w", pady=(6, 0))

    # ─────────── Footer ───────────
    def _build_footer(self, parent):
        ctk.CTkLabel(
            parent, text="德语转语音 v1.0  ·  Qwen-TTS  ·  阿里云百炼",
            font=ctk.CTkFont(size=11), text_color=GRAY4,
        ).pack(pady=(20, 0))

    # ────────────────────────────────────────────────────
    #  核心逻辑
    # ────────────────────────────────────────────────────
    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    def _set_status(self, msg: str, color=GRAY5):
        self.after(0, lambda: self.status_label.configure(text=msg, text_color=color))

    def _start(self):
        if self.is_running:
            return

        api_key = self.apikey_entry.get().strip()
        if not api_key:
            messagebox.showwarning("缺少 API Key", "请先填写阿里云百炼 API Key。")
            return

        text = self.textbox.get("0.0", "end").strip()
        if not text or self._ph_active:
            messagebox.showwarning("文本为空", "请输入要转录的德语文字。")
            return

        save_path = self.path_var.get().strip()
        if not save_path:
            messagebox.showwarning("路径为空", "请指定音频文件的保存路径。")
            return

        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            messagebox.showerror("路径错误", f"目录不存在：{save_dir}")
            return

        self.is_running = True
        self.btn.configure(text="转录中…", state="disabled", fg_color=GRAY4)
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self._set_status("正在调用 Qwen-TTS…")

        threading.Thread(
            target=self._convert,
            args=(api_key, text, self.voice_val, save_path),
            daemon=True,
        ).start()

    def _convert(self, api_key, text, voice, save_path):
        try:
            self._set_status("请求 API 中…")

            resp = dashscope.MultiModalConversation.call(
                model=MODEL,
                api_key=api_key,
                text=text,
                voice=voice,
                language_type="German",
                stream=False,
            )

            if resp.status_code != 200:
                raise RuntimeError(f"API 错误 {resp.status_code}: {resp.message or resp.code}")

            url = resp.output.audio.url
            if not url:
                raise RuntimeError("API 未返回音频 URL")

            self._set_status("下载音频中…")
            dl = requests.get(url, timeout=60)
            dl.raise_for_status()

            with open(save_path, "wb") as f:
                f.write(dl.content)

            kb = len(dl.content) / 1024
            self.after(0, self._done, save_path, kb)

        except Exception as e:
            self.after(0, self._fail, str(e))

    def _done(self, path, kb):
        self.is_running = False
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(1.0)
        self.btn.configure(text="开始转录", state="normal", fg_color=BLUE)
        self._set_status(f"✓ 已保存 {os.path.basename(path)}（{kb:.0f} KB）", GREEN)
        messagebox.showinfo(
            "完成",
            f"音频已生成！\n\n{path}\n\n{kb:.1f} KB",
        )

    def _fail(self, msg):
        self.is_running = False
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self.btn.configure(text="开始转录", state="normal", fg_color=BLUE)
        self._set_status(f"✗ {msg}", RED)
        messagebox.showerror("失败", msg)


if __name__ == "__main__":
    App().mainloop()
