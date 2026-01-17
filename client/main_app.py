import customtkinter as ctk
import requests
import subprocess
import threading
import json
import os
import sys
import urllib.parse

REPO_URL = "https://github.com/KiryaScript/white-lists/raw/refs/heads/main/githubmirror/26.txt"
CORE_FILE = "xray.exe"
LOCAL_PORT = 10808
HTTP_PORT = 10809

COLOR_BG = "#2b2b2b"
COLOR_LIST_BG = "#353535"
COLOR_HEADER = "#404040"
COLOR_SELECTED = "#3c77c9"
COLOR_TEXT = "#ffffff"
COLOR_BTN = "#454545"
COLOR_BTN_HOVER = "#505050"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class ServerRow(ctk.CTkFrame):
    """Класс для отрисовки одной строки (сервера) как в таблице"""
    def __init__(self, master, index, name, protocol, address, command):
        super().__init__(master, fg_color="transparent", corner_radius=0, height=30)
        self.command = command
        self.data_index = index
        self.pack(fill="x", pady=1)

        self.bind("<Button-1>", self.on_click)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

        self.lbl_id = ctk.CTkLabel(self, text=str(index), width=40, anchor="center", font=("Arial", 11))
        self.lbl_id.pack(side="left", padx=2)
        
        self.lbl_name = ctk.CTkLabel(self, text=name, width=250, anchor="w", font=("Arial", 11, "bold"))
        self.lbl_name.pack(side="left", padx=5)

        self.lbl_proto = ctk.CTkLabel(self, text=protocol, width=80, anchor="center", font=("Arial", 11), text_color="#aaa")
        self.lbl_proto.pack(side="left", padx=5)

        self.lbl_addr = ctk.CTkLabel(self, text=address, width=150, anchor="w", font=("Arial", 11))
        self.lbl_addr.pack(side="left", padx=5)

        for w in [self.lbl_id, self.lbl_name, self.lbl_proto, self.lbl_addr]:
            w.bind("<Button-1>", self.on_click)

    def on_click(self, event):
        self.command(self)

    def on_enter(self, event):
        if self.fg_color != COLOR_SELECTED:
            self.configure(fg_color="#3a3a3a")

    def on_leave(self, event):
        if self.fg_color != COLOR_SELECTED:
            self.configure(fg_color="transparent")

    def set_selected(self, selected=True):
        color = COLOR_SELECTED if selected else "transparent"
        self.configure(fg_color=color)


class NekoClient(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("WhiteLists Client (NekoRay Style)")
        self.geometry("900x650")
        self.configure(fg_color=COLOR_BG)

        self.process = None
        self.is_running = False
        self.configs = []
        self.rows = []
        self.selected_row = None
        self.selected_config_str = None

        self.setup_ui()
        self.log("System initialized. Ready.")
        
        self.load_servers_thread()

    def setup_ui(self):
        self.toolbar = ctk.CTkFrame(self, height=50, fg_color=COLOR_BG, corner_radius=0)
        self.toolbar.pack(fill="x", side="top", padx=5, pady=5)

        btn_opts = {"width": 120, "height": 32, "corner_radius": 4, "fg_color": COLOR_BTN, "hover_color": COLOR_BTN_HOVER, "font": ("Segoe UI", 12)}
        
        self.btn_run = ctk.CTkButton(self.toolbar, text="▶ Запустить", command=self.toggle_vpn, **btn_opts)
        self.btn_run.pack(side="left", padx=5)

        self.btn_update = ctk.CTkButton(self.toolbar, text="🔄 Обновить подписку", command=self.load_servers_thread, **btn_opts)
        self.btn_update.pack(side="left", padx=5)
        
        self.lbl_status = ctk.CTkLabel(self.toolbar, text="Статус: Остановлен", font=("Segoe UI", 12))
        self.lbl_status.pack(side="right", padx=15)

        self.header_frame = ctk.CTkFrame(self, height=30, fg_color=COLOR_HEADER, corner_radius=0)
        self.header_frame.pack(fill="x", padx=5, pady=(0, 0))

        headers = [("№", 45), ("Имя сервера", 255), ("Тип", 85), ("Адрес", 155)]
        for text, width in headers:
            lbl = ctk.CTkLabel(self.header_frame, text=text, width=width, anchor="w", font=("Segoe UI", 11, "bold"))
            lbl.pack(side="left", padx=2)

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color=COLOR_LIST_BG, corner_radius=2)
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=2)

        self.log_label = ctk.CTkLabel(self, text="Журнал событий:", anchor="w", font=("Segoe UI", 11))
        self.log_label.pack(fill="x", padx=5, pady=(5,0))

        self.log_box = ctk.CTkTextbox(self, height=150, fg_color="black", text_color="#00ff00", font=("Consolas", 10), corner_radius=2)
        self.log_box.pack(fill="x", padx=5, pady=5)
        self.log_box.configure(state="disabled")

    def log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{self.get_time()}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def get_time(self):
        import datetime
        return datetime.datetime.now().strftime("%H:%M:%S")

    def load_servers_thread(self):
        threading.Thread(target=self.fetch_configs, daemon=True).start()

    def fetch_configs(self):
        try:
            self.btn_update.configure(state="disabled")
            self.log("Обновление списка серверов...")
            
            resp = requests.get(REPO_URL, timeout=10)
            resp.raise_for_status()
            raw_data = [line.strip() for line in resp.text.splitlines() if line.strip() and "vless://" in line]
            
            self.configs = raw_data
            
            self.after(0, self.render_list)

        except Exception as e:
            self.log(f"Ошибка обновления: {e}")
        finally:
            self.btn_update.configure(state="normal")

    def render_list(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.rows = []
        self.selected_row = None
        self.selected_config_str = None

        for i, conf in enumerate(self.configs):
            name = f"Server {i+1}"
            address = "Unknown"
            protocol = "VLESS"

            try:
                if "#" in conf:
                    name = urllib.parse.unquote(conf.split("#")[-1])
                temp = conf.split("@")[1]
                address = temp.split(":")[0]
            except: pass

            row = ServerRow(self.scroll_frame, i+1, name, protocol, address, self.select_row)
            self.rows.append(row)
        
        self.log(f"Список обновлен. Серверов: {len(self.configs)}")

    def select_row(self, row_widget):
        for r in self.rows:
            r.set_selected(False)
        
        row_widget.set_selected(True)
        self.selected_row = row_widget
        self.selected_config_str = self.configs[row_widget.data_index - 1]
        
        self.log(f"Выбран сервер: {row_widget.lbl_name.cget('text')}")

    def toggle_vpn(self):
        if not self.is_running:
            self.start_xray()
        else:
            self.stop_xray()

    def start_xray(self):
        if not self.selected_config_str:
            self.log("Ошибка: Сервер не выбран!")
            return
        
        if not os.path.exists(CORE_FILE):
            self.log(f"Критическая ошибка: Файл {CORE_FILE} не найден!")
            return

        self.log("Генерация конфигурации...")
        try:
            config_json = self.generate_xray_config(self.selected_config_str)
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config_json, f, indent=2)
        except Exception as e:
            self.log(f"Ошибка парсинга конфига: {e}")
            return

        self.log("Запуск ядра Xray...")
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            self.process = subprocess.Popen([CORE_FILE, "-c", "config.json"], creationflags=flags)
            self.is_running = True
            
            self.btn_run.configure(text="⏹ Остановить", fg_color="#8a2b2b", hover_color="#a13333")
            self.lbl_status.configure(text="Статус: РАБОТАЕТ (TUN/SOCKS)", text_color="#00ff00")
            self.log(f"Xray запущен. SOCKS5: :{LOCAL_PORT} | HTTP: :{HTTP_PORT}")
        except Exception as e:
            self.log(f"Не удалось запустить процесс: {e}")

    def stop_xray(self):
        if self.process:
            self.process.terminate()
            self.process = None
        
        self.is_running = False
        self.btn_run.configure(text="▶ Запустить", fg_color=COLOR_BTN, hover_color=COLOR_BTN_HOVER)
        self.lbl_status.configure(text="Статус: Остановлен", text_color="white")
        self.log("Ядро остановлено.")

    def generate_xray_config(self, link):
        link = link.replace("vless://", "").split("#")[0]
        user, connection = link.split("@")
        addr_full, params_str = connection.split("?")
        addr, port = addr_full.split(":")
        params = dict(urllib.parse.parse_qsl(params_str))
        
        return {
            "log": {"loglevel": "warning"},
            "inbounds": [
                {"port": LOCAL_PORT, "protocol": "socks", "settings": {"udp": True}},
                {"port": HTTP_PORT, "protocol": "http"}
            ],
            "outbounds": [
                {
                    "protocol": "vless",
                    "settings": {
                        "vnext": [{
                            "address": addr, "port": int(port),
                            "users": [{"id": user, "encryption": "none", "flow": params.get("flow", "")}]
                        }]
                    },
                    "streamSettings": {
                        "network": params.get("type", "tcp"),
                        "security": params.get("security", "none"),
                        "tlsSettings": {"serverName": params.get("sni", ""), "allowInsecure": True},
                        "wsSettings": {"path": params.get("path", "/"), "headers": {"Host": params.get("host", "")}} if params.get("type") == "ws" else None,
                        "grpcSettings": {"serviceName": params.get("serviceName", "")} if params.get("type") == "grpc" else None
                    }
                },
                {"protocol": "freedom", "tag": "direct"}
            ]
        }
    
    def on_close(self):
        self.stop_xray()
        self.destroy()

if __name__ == "__main__":
    app = NekoClient()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()