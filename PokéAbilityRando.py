import json
import os
import random
import sys
import threading
import time
import subprocess
import webbrowser
import customtkinter as ctk
import requests
from PIL import Image, ImageTk

APP_NAME = "PokéAbilityRando"
CURRENT_VERSION = "v1.0.4"

# --- Path Helpers ---
def get_app_install_dir() -> str:
    """Returns directory where the executable or script sits."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_user_cache_dir() -> str:
    """Returns OS-standard hidden cache directory for cache.json."""
    if sys.platform == "win32":
        base = os.environ.get(
            "LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")
        )
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Caches")
    else:  # Linux / Unix
        base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))

    cache_dir = os.path.join(base, APP_NAME)
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


# File Paths
BLACKLIST_FILE = os.path.join(get_app_install_dir(), "blacklist.txt")
WILDCARD_FILE = os.path.join(get_app_install_dir(), "wildcards.txt")
CACHE_FILE = os.path.join(get_user_cache_dir(), "cache.json")
CACHE_EXPIRY_DAYS = 30

# Windows Taskbar Icon Fix (Skipped on macOS/Linux)
if sys.platform == "win32":
    import ctypes

    try:
        my_app_id = "pokeabilityrando.app.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_app_id)
    except Exception:
        pass

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# Abilities that only function in Double/Multi battles or require an ally
DOUBLES_ONLY_ABILITIES = {
    "plus",
    "minus",
    "commander",
    "telepathy",
    "friend guard",
    "symbiosis",
    "receiver",
    "power of alchemy",
    "battery",
    "power spot",
    "steely spirit",
    "flower gift",
    "healer",
}


def ensure_text_file_exists(filepath: str):
    """Creates an empty text file if it does not exist."""
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            pass


def load_list_from_file(filepath: str) -> set:
    """Reads a line-separated text file into a lower-cased set."""
    ensure_text_file_exists(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}


def append_to_file(filepath: str, ability_name: str):
    """Appends a new ability name to the specified text file cleanly."""
    ensure_text_file_exists(filepath)
    with open(filepath, "r+", encoding="utf-8") as f:
        content = f.read()
        if content and not content.endswith("\n"):
            f.write("\n")
        f.write(f"{ability_name}\n")


class PokemonAbilityApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("PokéAbilityRando")
        self.geometry("580x780")

        self.load_app_icon()

        self.all_abilities = []
        self.ability_cache = {}
        self.latest_asset_url = None

        ensure_text_file_exists(BLACKLIST_FILE)
        ensure_text_file_exists(WILDCARD_FILE)

        self.setup_ui()
        threading.Thread(target=self.load_ability_list, daemon=True).start()
        
        # Check updates silently in the background on startup
        threading.Thread(target=self.check_for_updates, args=(False,), daemon=True).start()

    def load_app_icon(self):
        """Cross-platform app icon handler with garbage collection protection."""
        base_path = get_app_install_dir()

        ico_names = ["PokéAbilityRando.ico", "app_icon.ico"]
        png_names = ["PokéAbilityRando.png", "app_icon.png"]

        ico_path = next(
            (
                os.path.join(base_path, f)
                for f in ico_names
                if os.path.exists(os.path.join(base_path, f))
            ),
            None,
        )
        png_path = next(
            (
                os.path.join(base_path, f)
                for f in png_names
                if os.path.exists(os.path.join(base_path, f))
            ),
            None,
        )

        try:
            if sys.platform == "win32" and ico_path:
                self.iconbitmap(ico_path)
            elif png_path:
                img = Image.open(png_path)
                self._icon_photo = ImageTk.PhotoImage(img)
                self.wm_iconphoto(True, self._icon_photo)
        except Exception as e:
            print(f"Icon loading error: {e}")

    def fetch_max_generation(self) -> int:
        """Dynamically fetches the latest generation count from PokéAPI to support future gens."""
        try:
            response = requests.get("https://pokeapi.co/api/v2/generation/", timeout=3)
            if response.status_code == 200:
                data = response.json()
                return data.get("count", 9)
        except Exception:
            pass
        return 9  # Fallback ceiling if offline

    def setup_ui(self):
        self.title_label = ctk.CTkLabel(
            self, text="PokéAbilityRando", font=("Arial", 20, "bold")
        )
        self.title_label.pack(pady=(15, 2))

        self.status_label = ctk.CTkLabel(
            self, text="Checking cache...", text_color="gray"
        )
        self.status_label.pack(pady=(0, 10))

        # Progress bar initialized but hidden by default
        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.set(0)

        input_frame = ctk.CTkFrame(self)
        input_frame.pack(padx=20, pady=5, fill="x")

        # Row 0: Count & Reload Info
        ctk.CTkLabel(input_frame, text="Count:").grid(
            row=0, column=0, padx=(10, 5), pady=8, sticky="w"
        )
        self.count_entry = ctk.CTkEntry(input_frame, width=50)
        self.count_entry.insert(0, "5")
        self.count_entry.grid(row=0, column=1, padx=5, pady=8, sticky="w")

        self.reload_btn = ctk.CTkButton(
            input_frame,
            text="Reload Files Info",
            width=120,
            command=self.show_config_status,
        )
        self.reload_btn.grid(row=0, column=2, padx=10, pady=8, sticky="e")

        # Row 1: Generation Selector & Update Cache Button
        ctk.CTkLabel(input_frame, text="Gen:").grid(
            row=1, column=0, padx=(10, 5), pady=8, sticky="w"
        )
        
        max_gen = self.fetch_max_generation()
        gen_values = ["All Gens"] + [f"Gen {i}" for i in range(3, max_gen + 1)]

        self.gen_option = ctk.CTkOptionMenu(
            input_frame,
            values=gen_values,
            width=110,
        )
        self.gen_option.set("All Gens")
        self.gen_option.grid(row=1, column=1, padx=5, pady=8, sticky="w")

        self.update_cache_btn = ctk.CTkButton(
            input_frame,
            text="Update API Cache",
            width=120,
            fg_color="#2B5B84",
            hover_color="#1E3F5B",
            command=self.on_click_update_cache,
        )
        self.update_cache_btn.grid(row=1, column=2, padx=10, pady=8, sticky="e")

        # Row 2: Singles-Only Toggle Switch & Check Updates Button
        self.singles_switch = ctk.CTkSwitch(
            input_frame, text="Ignore Doubles-Only"
        )
        self.singles_switch.grid(
            row=2, column=0, columnspan=2, padx=10, pady=8, sticky="w"
        )

        self.update_btn = ctk.CTkButton(
            input_frame,
            text="Check Updates",
            width=120,
            fg_color="#4A5568",
            hover_color="#2D3748",
            command=self.run_update_check,
        )
        self.update_btn.grid(row=2, column=2, padx=10, pady=8, sticky="e")

        # Row 3: Status File Info Text
        self.file_info_label = ctk.CTkLabel(
            input_frame,
            text="Reads from blacklist.txt & wildcards.txt",
            font=("Arial", 11),
            text_color="gray",
        )
        self.file_info_label.grid(
            row=3, column=0, columnspan=3, padx=10, pady=(0, 8)
        )

        # Generate Button
        self.generate_btn = ctk.CTkButton(
            self,
            text="Generate Abilities",
            command=self.on_generate_click,
            state="disabled",
            font=("Arial", 14, "bold"),
        )
        self.generate_btn.pack(pady=10)

        # Scrollable Frame for Result Cards
        self.results_frame = ctk.CTkScrollableFrame(
            self, width=530, height=380
        )
        self.results_frame.pack(padx=20, pady=(5, 20), fill="both", expand=True)

    def load_ability_list(self, force_refresh: bool = False):
        if os.path.exists(CACHE_FILE) and not force_refresh:
            try:
                file_age_days = (time.time() - os.path.getmtime(CACHE_FILE)) / (
                    60 * 60 * 24
                )
                if file_age_days < CACHE_EXPIRY_DAYS:
                    with open(CACHE_FILE, "r", encoding="utf-8") as f:
                        self.all_abilities = json.load(f)
                    self.after(
                        0,
                        lambda: self.status_label.configure(
                            text=f"Loaded {len(self.all_abilities)} abilities (Cached {int(file_age_days)}d ago).",
                            text_color="green",
                        ),
                    )
                    self.after(
                        0, lambda: self.generate_btn.configure(state="normal")
                    )
                    return
            except Exception:
                pass

        status_msg = (
            "Force updating PokéAPI cache..."
            if force_refresh
            else "Cache expired/missing. Fetching fresh API data..."
        )
        self.after(
            0,
            lambda: self.status_label.configure(
                text=status_msg, text_color="yellow"
            ),
        )

        try:
            results = []
            max_gen = self.fetch_max_generation()
            for gen_num in range(3, max_gen + 1):
                url = f"https://pokeapi.co/api/v2/generation/{gen_num}/"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    gen_data = response.json()
                    for ab in gen_data.get("abilities", []):
                        results.append(
                            {
                                "name": ab["name"].replace("-", " ").title(),
                                "url": ab["url"],
                                "gen": gen_num,
                            }
                        )

            if results:
                self.all_abilities = results
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.all_abilities, f, indent=4)

                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text=f"Updated! Loaded {len(self.all_abilities)} total abilities.",
                        text_color="green",
                    ),
                )
            self.after(0, lambda: self.generate_btn.configure(state="normal"))

        except Exception:
            self.after(
                0,
                lambda: self.status_label.configure(
                    text="Error connecting to PokéAPI.", text_color="red"
                ),
            )

    def check_for_updates(self, manual=True):
        try:
            url = "https://api.github.com/repos/Zenshu/PokeAbilityRando/releases/latest"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_tag = data.get("tag_name")
                
                if latest_tag and latest_tag != CURRENT_VERSION:
                    asset_url = None
                    for asset in data.get("assets", []):
                        name = asset["name"].lower()
                        if sys.platform == "win32" and name.endswith(".exe"):
                            asset_url = asset["browser_download_url"]
                            break
                        elif sys.platform == "darwin" and ("mac" in name or "darwin" in name or name.endswith(".zip")):
                            asset_url = asset["browser_download_url"]
                            break
                        elif sys.platform == "linux" and ("linux" in name or "appimage" in name or not "." in name):
                            asset_url = asset["browser_download_url"]
                            break

                    if not asset_url and data.get("assets"):
                        asset_url = data["assets"][0]["browser_download_url"]

                    self.latest_asset_url = asset_url

                    self.after(0, lambda: self.status_label.configure(text=f"New version {latest_tag} available!", text_color="green"))
                    self.after(0, lambda: self.update_btn.configure(
                        text=f"Download {latest_tag}",
                        fg_color="#2B5B84",
                        hover_color="#1E3F5B",
                        command=self.trigger_download
                    ))
                elif manual:
                    self.after(0, lambda: self.status_label.configure(text="You are running the latest version.", text_color="gray"))
            elif manual:
                self.after(0, lambda: self.status_label.configure(text="No releases found on GitHub.", text_color="red"))
        except Exception:
            if manual:
                self.after(0, lambda: self.status_label.configure(text="Could not reach GitHub for updates.", text_color="red"))

    def trigger_download(self):
        """Called when the user explicitly clicks the dynamic download button."""
        if self.latest_asset_url:
            self.update_btn.configure(state="disabled", text="Downloading...")
            self.status_label.configure(text="Downloading update package...", text_color="blue")
            
            # Reveal progress bar right above the generate button only when downloading
            self.progress_bar.pack(pady=(0, 10), before=self.generate_btn)
            
            threading.Thread(target=self.download_and_apply_update, args=(self.latest_asset_url,), daemon=True).start()
        else:
            webbrowser.open("https://github.com/Zenshu/PokeAbilityRando/releases/latest")

    def download_and_apply_update(self, asset_url):
        temp_file = None
        try:
            if getattr(sys, "frozen", False):
                current_executable = sys.executable
            else:
                ext = ".exe" if sys.platform == "win32" else ""
                current_executable = os.path.join(get_app_install_dir(), f"PokéAbilityRando{ext}")

            temp_file = current_executable + ".tmp"

            response = requests.get(asset_url, stream=True, timeout=30)
            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0

                with open(temp_file, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            if total_size > 0:
                                progress = downloaded_size / total_size
                                percent = int(progress * 100)
                                self.after(0, lambda p=progress, pct=percent: [
                                    self.progress_bar.set(p),
                                    self.status_label.configure(text=f"Downloading update... {pct}%")
                                ])
                            else:
                                kb_downloaded = downloaded_size // 1024
                                self.after(0, lambda kb=kb_downloaded: self.status_label.configure(text=f"Downloading... {kb} KB"))

                # Validate downloaded file (must be at least 100KB and not an HTML response)
                if os.path.exists(temp_file) and os.path.getsize(temp_file) > 100 * 1024:
                    with open(temp_file, "rb") as check_f:
                        header = check_f.read(10)
                        if b"<!DOCTYPE" in header or b"<html" in header:
                            raise Exception("Downloaded file is an HTML page instead of an executable.")
                else:
                    raise Exception("Downloaded file is too small or invalid.")

                install_dir = get_app_install_dir()

                if sys.platform == "win32":
                    bat_path = os.path.join(install_dir, "update.bat")
                    with open(bat_path, "w", encoding="utf-8") as bat:
                        bat.write("@echo off\n")
                        bat.write("chcp 65001 > nul\n")
                        # Force-kill any lingering instances to clear file locks (Error 32 fix)
                        bat.write("taskkill /f /im PokéAbilityRando.exe > nul 2>&1\n")
                        bat.write("timeout /t 3 /nobreak > nul\n")
                        
                        # Directly move the verified temp file over the current executable
                        bat.write(f'move /y "{temp_file}" "{current_executable}"\n')
                        bat.write(f'start "" "{current_executable}"\n')
                        bat.write('del "%~f0"\n')
                    subprocess.Popen([bat_path], shell=True)
                else:
                    sh_path = os.path.join(install_dir, "update.sh")
                    with open(sh_path, "w", encoding="utf-8") as sh:
                        sh.write("#!/bin/bash\n")
                        sh.write("sleep 2\n")
                        sh.write(f'mv "{temp_file}" "{current_executable}"\n')
                        sh.write(f'chmod +x "{current_executable}"\n')
                        sh.write(f'xattr -d com.apple.quarantine "{current_executable}" 2>/dev/null\n')
                        sh.write(f'"{current_executable}" &\n')
                        sh.write(f'rm -- "$0"\n')
                    os.chmod(sh_path, 0o755)
                    subprocess.Popen(["sh", sh_path])

                self.after(0, sys.exit, 0)
            else:
                self.after(0, lambda: self.status_label.configure(text="Failed to download update file.", text_color="red"))
                self.after(0, lambda: self.update_btn.configure(state="normal", text="Retry Download"))
                self.after(0, self.progress_bar.pack_forget)
        except Exception as e:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            self.after(0, lambda err=str(e): self.status_label.configure(text=f"Update error: {err}", text_color="red"))
            self.after(0, lambda: self.update_btn.configure(state="normal", text="Retry Download"))
            self.after(0, self.progress_bar.pack_forget)

    def run_update_check(self):
        self.status_label.configure(text="Checking for updates...", text_color="blue")
        threading.Thread(target=self.check_for_updates, args=(True,), daemon=True).start()

    def on_click_update_cache(self):
        self.generate_btn.configure(state="disabled")
        threading.Thread(
            target=self.load_ability_list,
            kwargs={"force_refresh": True},
            daemon=True,
        ).start()

    def fetch_description(self, url: str) -> str:
        if url in self.ability_cache:
            return self.ability_cache[url]

        try:
            response = requests.get(url, timeout=5)
            data = response.json()

            effect = "No modern description available."
            flavor_entries = data.get("flavor_text_entries", [])

            english_entries = [
                entry for entry in flavor_entries if entry["language"]["name"] == "en"
            ]

            if english_entries:
                latest_entry = english_entries[-1]
                effect = latest_entry["flavor_text"]
                effect = effect.replace("\n", " ").replace("\f", " ")
                effect = " ".join(effect.split())

            self.ability_cache[url] = effect
            return effect
        except Exception:
            return "Failed to fetch description."

    def show_config_status(self):
        blacklist = load_list_from_file(BLACKLIST_FILE)
        wildcards = load_list_from_file(WILDCARD_FILE)
        msg = f"Loaded {len(blacklist)} blacklisted items & {len(wildcards)} wildcards."
        self.file_info_label.configure(text=msg, text_color="cyan")

    def clear_results(self):
        for widget in self.results_frame.winfo_children():
            widget.destroy()

    def on_generate_click(self):
        self.generate_btn.configure(state="disabled")
        self.clear_results()

        loading_label = ctk.CTkLabel(
            self.results_frame, text="Rolling abilities..."
        )
        loading_label.pack(pady=20)

        threading.Thread(
            target=self.generate_abilities_thread, daemon=True
        ).start()

    def generate_abilities_thread(self):
        try:
            count = int(self.count_entry.get())
            blacklist = load_list_from_file(BLACKLIST_FILE)
            wildcards = load_list_from_file(WILDCARD_FILE)

            selected_gen_str = self.gen_option.get()
            target_gen = None
            if selected_gen_str != "All Gens":
                target_gen = int(selected_gen_str.split(" ")[1])

            ignore_doubles = self.singles_switch.get() == 1

            pool = []
            for ab in self.all_abilities:
                name_lower = ab["name"].lower()

                if name_lower in blacklist:
                    continue

                if target_gen is not None and ab["gen"] != target_gen:
                    continue

                if ignore_doubles and name_lower in DOUBLES_ONLY_ABILITIES:
                    continue

                pool.append(ab)

            if count > len(pool):
                self.after(
                    0,
                    lambda: self.display_error(
                        f"Requested {count} abilities, but only {len(pool)} available under selected filters."
                    ),
                )
                return

            selected = random.sample(pool, count)
            results_data = []

            for ab in selected:
                is_wildcard = ab["name"].lower() in wildcards
                desc = (
                    "Wildcard replacement triggered."
                    if is_wildcard
                    else self.fetch_description(ab["url"])
                )
                results_data.append(
                    {
                        "name": ab["name"],
                        "description": desc,
                        "is_wildcard": is_wildcard,
                    }
                )

            self.after(0, lambda: self.render_results(results_data))

        except ValueError:
            self.after(
                0,
                lambda: self.display_error(
                    "Please enter a valid count number."
                ),
            )

    def display_error(self, message: str):
        self.clear_results()
        ctk.CTkLabel(
            self.results_frame, text=message, text_color="red"
        ).pack(pady=20)
        self.generate_btn.configure(state="normal")

    def render_results(self, results: list):
        self.clear_results()

        for idx, item in enumerate(results, 1):
            card = ctk.CTkFrame(self.results_frame)
            card.pack(padx=5, pady=5, fill="x")

            title_text = (
                f"{idx}. Any Ability Token"
                if item["is_wildcard"]
                else f"{idx}. {item['name']}"
            )
            title_color = "yellow" if item["is_wildcard"] else "white"

            title_label = ctk.CTkLabel(
                card,
                text=title_text,
                font=("Arial", 14, "bold"),
                text_color=title_color,
                anchor="w",
            )
            title_label.pack(padx=10, pady=(8, 2), fill="x")

            desc_text = (
                f"[Rolled: {item['name']}]"
                if item["is_wildcard"]
                else item["description"]
            )
            desc_label = ctk.CTkLabel(
                card,
                text=desc_text,
                wraplength=480,
                justify="left",
                anchor="w",
                text_color="gray80",
            )
            desc_label.pack(padx=10, pady=(0, 8), fill="x")

            btn_frame = ctk.CTkFrame(card, fg_color="transparent")
            btn_frame.pack(padx=10, pady=(0, 8), fill="x")

            add_bl_btn = ctk.CTkButton(
                btn_frame,
                text="+ Blacklist",
                width=90,
                height=24,
                fg_color="#8B0000",
                hover_color="#550000",
                command=lambda name=item["name"], c=card: self.add_to_file_action(
                    BLACKLIST_FILE, name, c
                ),
            )
            add_bl_btn.pack(side="left", padx=(0, 5))

            add_wc_btn = ctk.CTkButton(
                btn_frame,
                text="+ Wildcard",
                width=90,
                height=24,
                fg_color="#D2691E",
                hover_color="#8B4513",
                command=lambda name=item["name"], c=card: self.add_to_file_action(
                    WILDCARD_FILE, name, c
                ),
            )
            add_wc_btn.pack(side="left")

        self.generate_btn.configure(state="normal")

    def add_to_file_action(
        self, filepath: str, ability_name: str, card_widget: ctk.CTkFrame
    ):
        try:
            append_to_file(filepath, ability_name)
            self.show_config_status()

            for w in card_widget.winfo_children():
                if isinstance(w, ctk.CTkFrame):
                    w.destroy()

            list_type = "Blacklist" if filepath == BLACKLIST_FILE else "Wildcard"
            status_lbl = ctk.CTkLabel(
                card_widget,
                text=f"✓ Added '{ability_name}' to {list_type}",
                text_color="#00FF00",
                font=("Arial", 11, "italic"),
            )
            status_lbl.pack(padx=10, pady=(0, 8), anchor="w")
        except PermissionError:
            self.display_error("Permission denied. Run application as administrator.")


if __name__ == "__main__":
    app = PokemonAbilityApp()
    app.mainloop()