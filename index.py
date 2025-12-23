import requests
import io
import threading
import platform
import webbrowser
import re
import os
from urllib.parse import urlparse

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    import Tkinter as tk
    import ttk
    import messagebox

from PIL import Image, ImageTk
import mpv # Requires: brew install mpv && pip install python-mpv

class MovieViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Movie2k Explorer (Integrated Player)")
        self.root.geometry("1100x850")
        self.root.configure(bg="#1a1a1a")

        self.browse_url = "https://movie2k.ch/data/browse/"
        self.watch_url = "https://movie2k.ch/data/watch/"
        self.img_base = "https://image.tmdb.org/t/p/w500"
        
        self.current_page = 1
        self.headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

        self.setup_ui()
        self.show_browse_view()

    # --- SCRAPER ---
    def get_hls_manifest(self, landing_url):
        try:
            response = requests.get(landing_url, headers=self.headers, timeout=10)
            match = re.search(r'file\s*:\s*"([^"]+master\.m3u8[^"]+)"', response.text)
            return match.group(1) if match else None
        except:
            return None

    # --- INTEGRATED MPV PLAYER ---
    def open_internal_player(self, stream_url):
        # Create a popup loading window
        loading = tk.Toplevel(self.root)
        loading.title("Loading Stream")
        loading.geometry("300x100")
        tk.Label(loading, text="Extracting HLS Manifest...").pack(pady=30)
        loading.update()

        def task():
            hls_url = self.get_hls_manifest(stream_url)
            loading.destroy()
            if not hls_url:
                self.root.after(0, lambda: messagebox.showerror("Error", "Could not find video stream."))
                return
            self.root.after(0, lambda: self.create_mpv_window(hls_url))

        threading.Thread(target=task, daemon=True).start()

    def create_mpv_window(self, m3u8_url):
        player_win = tk.Toplevel(self.root)
        player_win.title("Integrated Player")
        player_win.geometry("960x540")
        player_win.configure(bg="black")

        # Container for MPV
        video_frame = tk.Frame(player_win, bg="black")
        video_frame.pack(fill=tk.BOTH, expand=True)

        # Force window rendering to get a valid ID
        player_win.update()

        # Initialize MPV with the frame's window ID
        # On macOS, mpv handles the embedding much more gracefully than VLC
        try:
            player = mpv.MPV(
                wid=str(video_frame.winfo_id()),
                osc=True,      # Show the built-in on-screen controller
                ytdl=False,    # We are providing the direct m3u8
                input_default_bindings=True,
                input_vo_keyboard=True
            )

            player.play(m3u8_url)

            def on_close():
                player.terminate() # Properly shut down the engine
                player_win.destroy()

            player_win.protocol("WM_DELETE_WINDOW", on_close)
        except Exception as e:
            messagebox.showerror("MPV Error", f"Failed to initialize MPV engine: {e}")
            player_win.destroy()

    # --- UI RENDERING ---
    def setup_ui(self):
        self.header = tk.Frame(self.root, bg="#111111", pady=20)
        self.header.pack(fill=tk.X)
        tk.Label(self.header, text="MOVIE2K EXPLORER", fg="#e74c3c", bg="#111111", font=("Arial", 24, "bold")).pack()

        self.container = tk.Frame(self.root, bg="#1a1a1a")
        self.container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(self.container, bg="#1a1a1a", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.container, orient="vertical", command=self.canvas.yview)
        self.view_frame = tk.Frame(self.canvas, bg="#1a1a1a")

        self.view_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.view_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.footer = tk.Frame(self.root, bg="#111111", pady=15)
        self.footer.pack(fill=tk.X)
        self.btn_prev = self.create_custom_button(self.footer, " << PREV ", "#34495e", self.prev_page)
        self.btn_prev.pack(side=tk.LEFT, padx=40)
        self.page_label = tk.Label(self.footer, text="PAGE 1", fg="white", bg="#111111", font=("Arial", 12, "bold"))
        self.page_label.pack(side=tk.LEFT, expand=True)
        self.btn_next = self.create_custom_button(self.footer, " NEXT >> ", "#34495e", self.next_page)
        self.btn_next.pack(side=tk.RIGHT, padx=40)

        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

    def create_custom_button(self, parent, text, color, command, width=15):
        btn = tk.Label(parent, text=text, bg=color, fg="white", font=("Arial", 10, "bold"), pady=8, width=width, cursor="hand2")
        btn.bind("<Button-1>", lambda e: command())
        return btn

    def _on_mousewheel(self, event):
        if platform.system() == 'Darwin': self.canvas.yview_scroll(-1 * event.delta, "units")

    def show_browse_view(self):
        self.footer.pack(fill=tk.X)
        for widget in self.view_frame.winfo_children(): widget.destroy()
        tk.Label(self.view_frame, text="Loading trending...", fg="#bdc3c7", bg="#1a1a1a").pack(pady=100, padx=400)
        threading.Thread(target=self.load_browse_data, daemon=True).start()

    def load_browse_data(self):
        params = {"lang": 2, "order_by": "trending", "page": self.current_page, "limit": 20}
        try:
            res = requests.get(self.browse_url, params=params, headers=self.headers, timeout=10).json()
            self.root.after(0, lambda: self.render_browse(res.get('movies', [])))
        except: pass

    def render_browse(self, movies):
        for widget in self.view_frame.winfo_children(): widget.destroy()
        grid = tk.Frame(self.view_frame, bg="#1a1a1a")
        grid.pack(padx=20, pady=20)
        cols = 2
        for i, m in enumerate(movies):
            row, col = i // cols, i % cols
            card = tk.Frame(grid, bg="#262626", padx=10, pady=10, cursor="hand2")
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            card.bind("<Button-1>", lambda e, id=m.get('_id'): self.show_detail_view(id))
            tk.Label(card, text=m.get('title'), font=("Arial", 10, "bold"), fg="white", bg="#262626", wraplength=200).grid(row=1, column=0)
            if m.get('poster_path'): self.load_image(self.img_base + m.get('poster_path'), card, (200, 300), click_id=m.get('_id'), row=0)

    def show_detail_view(self, movie_id):
        self.footer.pack_forget()
        for widget in self.view_frame.winfo_children(): widget.destroy()
        threading.Thread(target=self.load_detail_data, args=(movie_id,), daemon=True).start()

    def load_detail_data(self, movie_id):
        res = requests.get(self.watch_url, params={"_id": movie_id}, headers=self.headers, timeout=10).json()
        self.root.after(0, lambda: self.render_details(res))

    def render_details(self, data):
        for widget in self.view_frame.winfo_children(): widget.destroy()
        self.create_custom_button(self.view_frame, " ← BACK ", "#e74c3c", self.show_browse_view, width=15).pack(anchor="nw", padx=30, pady=20)
        
        info = tk.Frame(self.view_frame, bg="#1a1a1a")
        info.pack(fill=tk.X, padx=30)
        if data.get('poster_path'): self.load_image(self.img_base + data.get('poster_path'), info, (250, 375), row=0)

        # STREAMS: Priority to SaveFiles
        playable = ["savefiles.com", "streamhls.to"]
        streams = data.get('streams', [])
        sorted_s = sorted(streams, key=lambda s: any(x in urlparse(s.get('stream','')).netloc.lower() for x in playable), reverse=True)

        tk.Label(self.view_frame, text="AVAILABLE STREAMS", font=("Arial", 14, "bold"), fg="white", bg="#222", pady=10).pack(fill=tk.X, pady=20)

        for s in sorted_s:
            url = s.get('stream', '')
            domain = urlparse(url).netloc.lower()
            is_playable = any(src in domain for src in playable)

            row = tk.Frame(self.view_frame, bg="#262626", pady=5)
            row.pack(fill=tk.X, padx=30, pady=2)
            tk.Label(row, text=domain.upper(), font=("Arial", 10, "bold"), fg="#f1c40f", bg="#262626", width=25).pack(side=tk.LEFT)
            
            if is_playable:
                self.create_custom_button(row, " PLAY IN APP ", "#9b59b6", lambda u=url: self.open_internal_player(u), width=12).pack(side=tk.RIGHT, padx=5)
            self.create_custom_button(row, " BROWSER ", "#27ae60", lambda u=url: webbrowser.open(u), width=10).pack(side=tk.RIGHT, padx=5)

    def load_image(self, url, parent, size, click_id=None, row=0):
        def download():
            try:
                res = requests.get(url, timeout=5)
                pil_img = Image.open(io.BytesIO(res.content))
                pil_img.thumbnail(size)
                self.root.after(0, lambda: self.display_image_safe(pil_img, parent, click_id, row))
            except: pass
        threading.Thread(target=download, daemon=True).start()

    def display_image_safe(self, pil_img, parent, click_id, row):
        tk_img = ImageTk.PhotoImage(pil_img)
        lbl = tk.Label(parent, image=tk_img, bg=parent.cget('bg'))
        lbl.image = tk_img
        lbl.grid(row=row, column=0)
        if click_id: lbl.bind("<Button-1>", lambda e: self.show_detail_view(click_id))

    def next_page(self):
        self.current_page += 1
        self.page_label.config(text=f"PAGE {self.current_page}")
        self.show_browse_view()
        self.canvas.yview_moveto(0)

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.page_label.config(text=f"PAGE {self.current_page}")
            self.show_browse_view()
            self.canvas.yview_moveto(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = MovieViewer(root)
    root.mainloop()