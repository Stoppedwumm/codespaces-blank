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
from kivymd.uix.dialog import MDDialog
from kivymd.uix.spinner import MDSpinner
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.video import Video

KV = '''
ScreenManager:
    BrowseScreen:
    DetailScreen:
    PlayerScreen:

<MovieCard@MDCard>:
    orientation: "vertical"
    padding: "8dp"
    size_hint: None, None
    size: "160dp", "280dp"
    ripple_behavior: True
    poster: ""
    title: ""
    movie_id: ""
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
        theme_text_color: "Custom"
        text_color: 1, 1, 1, 1

<BrowseScreen>:
    name: "browse"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: 0.1, 0.1, 0.1, 1
        MDTopAppBar:
            title: "Movie2k Explorer"
            right_action_items: [["refresh", lambda x: app.load_movies()]]
            md_bg_color: 0.8, 0.1, 0.1, 1
        ScrollView:
            MDGridLayout:
                id: movie_grid
                cols: 2
                adaptive_height: True
                padding: "12dp"
                spacing: "12dp"
        MDBoxLayout:
            size_hint_y: None
            height: "56dp"
            padding: "10dp"
            md_bg_color: 0.05, 0.05, 0.05, 1
            MDRaisedButton:
                text: "PREV"
                on_release: app.change_page(-1)
            MDLabel:
                text: f"Page {app.current_page}"
                halign: "center"
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 1
            MDRaisedButton:
                text: "NEXT"
                on_release: app.change_page(1)

<DetailScreen>:
    name: "details"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: 0.1, 0.1, 0.1, 1
        MDTopAppBar:
            title: "Details"
            left_action_items: [["arrow-left", lambda x: app.go_back()]]
            md_bg_color: 0.2, 0.2, 0.2, 1
        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                adaptive_height: True
                padding: "20dp"
                spacing: "15dp"
                AsyncImage:
                    id: detail_poster
                    size_hint_y: None
                    height: "350dp"
                MDLabel:
                    id: detail_title
                    font_style: "H5"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 1, 1, 1, 1
                MDBoxLayout:
                    id: stream_container
                    orientation: "vertical"
                    adaptive_height: True
                    spacing: "10dp"

<PlayerScreen>:
    name: "player"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: 0, 0, 0, 1
        MDTopAppBar:
            title: "Internal Player"
            left_action_items: [["close", lambda x: app.stop_player()]]
            md_bg_color: 0.1, 0.1, 0.1, 1
        
        FloatLayout:
            Video:
                id: video_widget
                play: False
                allow_stretch: True
            MDLabel:
                id: player_status
                text: "Connecting to stream..."
                halign: "center"
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 1
'''

class BrowseScreen(Screen): pass
class DetailScreen(Screen): pass
class PlayerScreen(Screen): pass

class MovieApp(MDApp):
    current_page = 1
    dialog = None
    
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Red"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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
            Clock.schedule_once(lambda dt: self._display_movies(res.get('movies', [])))
        except: pass

    def _display_movies(self, movies):
        grid = self.root.get_screen('browse').ids.movie_grid
        from kivy.factory import Factory
        for m in movies:
            card = Factory.MovieCard()
            card.movie_id = m.get('_id')
            card.title = m.get('title')
            card.poster = f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}"
            grid.add_widget(card)

    def show_details(self, movie_id):
        self.root.current = "details"
        self.root.get_screen('details').ids.stream_container.clear_widgets()
        threading.Thread(target=self._fetch_details, args=(movie_id,), daemon=True).start()

    def _fetch_details(self, movie_id):
        url = "https://movie2k.ch/data/watch/"
        try:
            res = requests.get(url, params={"_id": movie_id}, headers=self.headers, timeout=10).json()
            Clock.schedule_once(lambda dt: self._display_details(res))
        except: pass

    def _display_details(self, data):
        screen = self.root.get_screen('details')
        screen.ids.detail_poster.source = f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}"
        screen.ids.detail_title.text = data.get('title', 'Unknown')
        container = screen.ids.stream_container
        for s in data.get('streams', []):
            url = s.get('stream', '')
            domain = urlparse(url).netloc.lower()
            btn = MDRaisedButton(
                text=f"PLAY IN APP: {domain.upper()}",
                pos_hint={"center_x": .5},
                size_hint_x=0.9,
                on_release=lambda x, u=url: self.start_extraction(u)
            )
            container.add_widget(btn)

    # --- EXTRACTION & PLAYER ---

    def start_extraction(self, url):
        if not self.dialog:
            self.dialog = MDDialog(
                title="Extracting Stream",
                type="custom",
                content_cls=MDSpinner(size_hint=(None, None), size=("48dp", "48dp"), pos_hint={'center_x': .5}),
                buttons=[MDRaisedButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss())]
            )
        self.dialog.open()
        threading.Thread(target=self._extract_logic, args=(url,), daemon=True).start()

    def _extract_logic(self, url):
        hls_url = None
        try:
            print(f"Scraping: {url}")
            response = requests.get(url, headers=self.headers, timeout=10).text
            # More aggressive regex to find m3u8 in JS sources
            match = re.search(r'["\'](http[^"\']+\.m3u8[^"\']*)["\']', response)
            if match:
                hls_url = match.group(1).replace('\\/', '/')
                print(f"Found HLS: {hls_url}")
        except Exception as e:
            print(f"Scraper error: {e}")

        Clock.schedule_once(lambda dt: self._finish_extraction(hls_url))

    def _finish_extraction(self, hls_url):
        if self.dialog:
            self.dialog.dismiss()
        
        if hls_url:
            self.open_player(hls_url)
        else:
            self.show_error("Could not find a playable stream for this source.")

    def open_player(self, hls_url):
        self.root.current = "player"
        p_screen = self.root.get_screen('player')
        video = p_screen.ids.video_widget
        video.source = hls_url
        video.state = 'play'
        p_screen.ids.player_status.text = "" # Hide status if playing

    def stop_player(self):
        video = self.root.get_screen('player').ids.video_widget
        video.state = 'stop'
        video.source = ""
        self.root.current = "details"

    def show_error(self, text):
        MDDialog(title="Error", text=text, buttons=[MDRaisedButton(text="OK", on_release=lambda x: x.parent.parent.parent.parent.dismiss())]).open()

    def change_page(self, delta):
        self.current_page = max(1, self.current_page + delta)
        self.load_movies()

    def go_back(self):
        self.root.current = "browse"

if __name__ == "__main__":
    MovieApp().run()