import threading
import re
import requests
from urllib.parse import urlparse
from kivy.lang import Builder
from kivy.utils import platform
from kivy.clock import Clock
from kivymd.app import MDApp
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.properties import StringProperty
from kivy.uix.video import Video # <--- Internal Video Widget

# --- SCREENS ---
class BrowseScreen(Screen): pass
class DetailScreen(Screen): pass
class PlayerScreen(Screen): pass # <--- New Video Screen

class MovieCard(MDCard):
    title = StringProperty("")
    poster = StringProperty("")
    movie_id = StringProperty("")

# --- UI (KV) ---
KV = '''
ScreenManager:
    BrowseScreen:
    DetailScreen:
    PlayerScreen:

<MovieCard>:
    orientation: "vertical"
    padding: "8dp"
    size_hint: None, None
    size: "160dp", "280dp"
    ripple_behavior: True
    on_release: app.show_details(root.movie_id)
    AsyncImage:
        source: root.poster
        allow_stretch: True
    MDLabel:
        text: root.title
        font_style: "Caption"
        halign: "center"
        size_hint_y: None
        height: "40dp"

<BrowseScreen>:
    name: "browse"
    MDBoxLayout:
        orientation: "vertical"
        MDTopAppBar:
            title: "Movie2k Explorer"
            right_action_items: [["refresh", lambda x: app.load_movies()]]
        ScrollView:
            MDGridLayout:
                id: movie_grid
                cols: 2
                adaptive_height: True
                padding: "10dp"
                spacing: "10dp"
        MDBoxLayout:
            size_hint_y: None
            height: "50dp"
            MDRaisedButton:
                text: "PREV"
                on_release: app.change_page(-1)
            MDLabel:
                text: "Page " + str(app.current_page)
                halign: "center"
            MDRaisedButton:
                text: "NEXT"
                on_release: app.change_page(1)

<DetailScreen>:
    name: "details"
    MDBoxLayout:
        orientation: "vertical"
        MDTopAppBar:
            title: "Details"
            left_action_items: [["arrow-left", lambda x: app.go_back()]]
        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                adaptive_height: True
                padding: "20dp"
                spacing: "20dp"
                AsyncImage:
                    id: detail_poster
                    size_hint_y: None
                    height: "350dp"
                MDLabel:
                    id: detail_title
                    font_style: "H5"
                    halign: "center"
                MDBoxLayout:
                    id: stream_container
                    orientation: "vertical"
                    adaptive_height: True
                    spacing: "10dp"

<PlayerScreen>:
    name: "player"
    MDBoxLayout:
        orientation: "vertical"
        MDTopAppBar:
            title: "Internal Player"
            left_action_items: [["close", lambda x: app.stop_video()]]
        
        # The Video Widget
        Video:
            id: video_player
            state: 'pause'
            allow_stretch: True
            options: {'eos': 'stop'}
        
        MDBoxLayout:
            size_hint_y: None
            height: "60dp"
            padding: "10dp"
            MDRaisedButton:
                text: "PLAY/PAUSE"
                on_release: video_player.state = 'play' if video_player.state == 'pause' else 'pause'
'''

class MovieApp(MDApp):
    current_page = 1
    
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Red"
        self.headers = {"User-Agent": "Mozilla/5.0"}
        return Builder.load_string(KV)

    def on_start(self):
        self.load_movies()

    def load_movies(self):
        self.root.get_screen('browse').ids.movie_grid.clear_widgets()
        threading.Thread(target=self._fetch_movies, daemon=True).start()

    def _fetch_movies(self):
        url = "https://movie2k.ch/data/browse/"
        params = {"lang": 2, "order_by": "trending", "page": self.current_page, "limit": 20}
        try:
            res = requests.get(url, params=params, headers=self.headers, timeout=10).json()
            Clock.schedule_once(lambda dt: self._populate_grid(res.get('movies', [])))
        except: pass

    def _populate_grid(self, movies):
        grid = self.root.get_screen('browse').ids.movie_grid
        for m in movies:
            card = MovieCard()
            card.movie_id = str(m.get('_id', ''))
            card.title = m.get('title', 'No Title')
            if m.get('poster_path'):
                card.poster = f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}"
            grid.add_widget(card)

    def show_details(self, movie_id):
        self.root.current = "details"
        screen = self.root.get_screen('details')
        screen.ids.stream_container.clear_widgets()
        threading.Thread(target=self._fetch_details, args=(movie_id,), daemon=True).start()

    def _fetch_details(self, movie_id):
        url = "https://movie2k.ch/data/watch/"
        try:
            res = requests.get(url, params={"_id": movie_id}, headers=self.headers, timeout=10).json()
            Clock.schedule_once(lambda dt: self.update_detail_ui(res))
        except: pass

    def update_detail_ui(self, data):
        screen = self.root.get_screen('details')
        if data.get('poster_path'):
            screen.ids.detail_poster.source = f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}"
        screen.ids.detail_title.text = data.get('title', 'Unknown')
        
        container = screen.ids.stream_container
        for s in data.get('streams', []):
            url = s.get('stream', '')
            domain = urlparse(url).netloc
            if not domain: continue
            
            # Button 1: Play Internal
            container.add_widget(MDRaisedButton(
                text=f"Play In-App ({domain})",
                pos_hint={"center_x": .5},
                on_release=lambda x, u=url: self.prepare_video(u)
            ))

    def prepare_video(self, landing_url):
        # Move to player screen and show "loading"
        self.root.current = "player"
        player = self.root.get_screen('player').ids.video_player
        player.source = "" # Clear previous
        
        def task():
            try:
                res = requests.get(landing_url, headers=self.headers, timeout=10).text
                match = re.search(r'file\s*:\s*"([^"]+master\.m3u8[^"]+)"', res)
                if match:
                    hls_url = match.group(1)
                    Clock.schedule_once(lambda dt: self.start_video(hls_url))
            except: pass
        threading.Thread(target=task, daemon=True).start()

    def start_video(self, hls_url):
        player = self.root.get_screen('player').ids.video_player
        player.source = hls_url
        player.state = 'play'

    def stop_video(self):
        player = self.root.get_screen('player').ids.video_player
        player.state = 'stop'
        player.unload()
        self.root.current = "details"

    def change_page(self, delta):
        self.current_page = max(1, self.current_page + delta)
        self.load_movies()

    def go_back(self):
        self.root.current = "browse"

if __name__ == "__main__":
    MovieApp().run()