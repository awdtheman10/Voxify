# boring imports
# V1.1 Hotfix 2:
# added comments, this is to help new devs learn the code
# fixed pitch + volume lol
# V1.2 BETA:
# hotfix 2 wasn't released, and i dont feel like pressing ctrl z for four days so im js gonna upload 1.2 in beta
print("loading time could take a little, just beware of that. rly depends on your hard drive")
print("v1.2 should add hotkey saving too")
print("if you see this, you should show your friends voxify")
import os
import json
import sounddevice as sd
import soundfile as sf
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, BooleanVar, StringVar, ttk
import numpy as np
import threading
import time
import asyncio
import subprocess
import ffmpeg
import soundfile as sf
import io
import edge_tts
import keyboard
import resampy
import pyttsx3
import sys
import shutil
import socket
APP_VERSION = "V1.2" # version. this is modifiable, and is not linked to the app at all. any value works. even 123abc.
base_dir = os.path.dirname(os.path.abspath(__file__)) # base directory
sounds_dir = os.path.join(base_dir, "Sounds") # sounds directory
prefs_path = os.path.join(base_dir, "vox_prefs.json") # preferences. V1.1 hotfix 1 renamed it from "voicify_prefs.json" to "vox_prefs.json" due to copyright.
os.makedirs(sounds_dir, exist_ok=True) # makes the directorys.
hotkey_refs = []  
active_keybinds = {}  # the current keybinds that are active

if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
# if you dont understand, basically if it says "frozen" then its an exe, if not, the .py

FFMPEG_PATH = os.path.join(base_dir, 'dependancies', 'ffmpeg.exe')

def ask_ffmpeg_path():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Select your ffmpeg.exe",
        filetypes=[("ffmpeg executable", "ffmpeg.exe")],
    )
    return file_path

if not os.path.isfile(FFMPEG_PATH):
    print("[ERROR] ffmpeg.exe not found in 'dependancies' folder.")
    print("You can fix this by moving ffmpeg.exe there manually.")
    print("[NOTE] DO NOT JUST MAKE A FILE CALLED FFMPEG.EXE, DOING THIS FIXES THE ISSUE, BUT YOUR SOUNDBOARD WONT WORK, AND POTENTIALLY THE TTS WONT WORK EITHER.")
    print("Alternatively, type 'Yes' to choose the ffmpeg.exe file yourself.")

    user_input = input("Type 'Yes' to manually select ffmpeg.exe: ").strip().lower()

    if user_input == "yes":
        new_path = ask_ffmpeg_path()
        if new_path and os.path.isfile(new_path):
            os.makedirs(os.path.dirname(FFMPEG_PATH), exist_ok=True)
            try:
                shutil.copyfile(new_path, FFMPEG_PATH)
                print(f"ffmpeg.exe copied to {FFMPEG_PATH}, booting")
            except Exception as e:
                print(f"Failed to copy file: {e}")
                time.sleep(4)
                os.close()
        else:
            print("ok i go goodbye now in 4 second")
            time.sleep(4)
            os.close()
    else:
        print("ffmpeg still missing.")
        time.sleep(4)
        os.close()
        
EDGE_VOICES = [
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-US-AriaNeural",
    "en-GB-RyanNeural",
    "en-GB-SoniaNeural",
] # these are voices when you HAVE internet and edge tts works
def get_voice_list():
    online = False
    try:
        socket.create_connection(("www.bing.com", 80), timeout=2)
        online = True
    except OSError:
        online = False

    if online:
        return EDGE_VOICES
    else:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        return [v.name for v in voices]

voice_names = get_voice_list()

# checks if bing is online
def check_edge_tts():
    try:
        socket.create_connection(("www.bing.com", 80), timeout=2)
        return True
    except OSError:
        return False

if not check_edge_tts():
    print("[Info] No internet detected. Using pyttsx3 voices.")
    # THIS INITALIZES PYTTSX3 IN CASE YOU CANT USE EDGE-TTS. I DIDN'T REALIZE EDGE-TTS NEEDED WIFI, MY BAD
else:
    voice_names = EDGE_VOICES
pyttsx3_engine = pyttsx3.init() 
pyttsx3_voices = pyttsx3_engine.getProperty('voices')
pyttsx3_voice_names = [v.name for v in pyttsx3_voices]
voice_names = pyttsx3_voice_names

# keybind handlers
def on_key_event(e):
    key = e.name.lower()
    if key in active_keybinds:
        play_sound_by_name(active_keybinds[key])
# registers keybinds
def register_all_keybinds():
    global active_keybinds
    active_keybinds.clear()

    for sound in soundboard_sounds:
        key = sound.get('keybind')
        if key:
            active_keybinds[key] = sound['name']
# the actual handler
keyboard.on_press(on_key_event)


# default preferences
default_prefs = {
    "tts_output_device": None,
    "monitor_output_device": None,
    "last_voice": None
}
# preferences stuff
def save_preferences(prefs):
    with open(prefs_path, "w") as f:
        json.dump(prefs, f)

def load_preferences():
    if os.path.exists(prefs_path):
        with open(prefs_path, "r") as f:
            return json.load(f)
    return default_prefs.copy()

prefs = load_preferences()
# getting all the valid output devices (if my code was right)
def get_output_devices():
    devices = sd.query_devices()
    valid_devices = []
    for i, d in enumerate(devices):
        if d['max_output_channels'] > 0:
            try:
                sd.check_output_settings(device=i, samplerate=44100)
                valid_devices.append((i, d['name']))
            except Exception:
                pass
    return valid_devices
# initalize the engine
# FIXED: Two engines got loaded on accident in V1.1, but this was fixed in V1.1H1 (hotfix 1), drastically reducing load times
# note: v1.2 beta fixed long loading times, because pyttsx3 wasn't being used, my mistake for leaving it in.
# the new version label
def add_version_label(parent_frame):
    version_label = tk.Label(parent_frame, text=APP_VERSION, font=("Arial", 8), fg="gray")
    version_label.pack(side="bottom", anchor="e", padx=5, pady=2)
voice_names = EDGE_VOICES

# this is used to load sounds automatically
def autoload():
    valid_exts = (".wav", ".flac", ".mp3", ".ogg", ".m4a", ".aac", ".wma", ".aiff",
                  ".alac", ".ac3", ".amr", ".caf", ".mp2", ".opus", ".ra", ".mka")
    
    for filename in os.listdir(sounds_dir):
        if not filename.lower().endswith(valid_exts):
            continue

        full_path = os.path.join(sounds_dir, filename)
        try:
            data, samplerate = load_audio_file(full_path)
        except Exception as e:
            print(f"[Error] Failed to load '{filename}': {e}")
            continue

        keybind = prefs.get("keybinds", {}).get(filename)
        soundboard_sounds.append({
            'path': full_path,
            'data': None,
            'samplerate': None, 
            'name': filename,
            'keybind': keybind
        })
    
    register_all_keybinds()
    refresh_sound_list()

# you can rescale this in the app, these are just the defaults
root = tk.Tk()
root.title("Voxify")
root.geometry("550x700")
beta_keybinds_var = BooleanVar(value=False)

notebook = ttk.Notebook(root)
notebook.pack(fill='both', expand=True)
# main tab, or tts
tts_tab = tk.Frame(notebook)
notebook.add(tts_tab, text='TTS')
add_version_label(tts_tab)

entry = tk.Entry(tts_tab, width=60)
entry.pack(pady=15)
# monitor
monitor_var = BooleanVar()
monitor_check = tk.Checkbutton(tts_tab, text="Monitor", variable=monitor_var)
monitor_check.pack()
# volume
tk.Label(tts_tab, text="Volume Meter:").pack(pady=(10,0))
volume_meter = ttk.Progressbar(tts_tab, orient='horizontal', length=400, mode='determinate', maximum=100)
volume_meter.pack()
# voice
voice_var = StringVar()
voice_var.set(prefs.get("last_voice") or voice_names[0])
voice_dropdown = ttk.Combobox(tts_tab, textvariable=voice_var, values=voice_names, width=60)
tk.Label(tts_tab, text="Choose Voice:").pack(pady=(10, 0))
voice_dropdown.pack()


all_output_devices = get_output_devices()
tts_output_devices = all_output_devices
tts_output_devices_dict = {f"[{idx}] {name}": idx for idx, name in tts_output_devices}

tts_output_device_var = StringVar()
if prefs["tts_output_device"] in tts_output_devices_dict:
    tts_output_device_var.set(prefs["tts_output_device"])
else:
    if tts_output_devices_dict:
        tts_output_device_var.set(next(iter(tts_output_devices_dict)))
    else:
        tts_output_device_var.set('')
# use steamvr mic or vb audio cable, both work fine
tk.Label(tts_tab, text="TTS Output Device (Virtual Mic playback):").pack(pady=(10, 0))
tts_output_dropdown = ttk.Combobox(tts_tab, textvariable=tts_output_device_var, values=list(tts_output_devices_dict.keys()), width=60)
tts_output_dropdown.pack()

monitor_output_devices = all_output_devices
monitor_output_devices_dict = {f"[{idx}] {name}": idx for idx, name in monitor_output_devices}

monitor_output_device_var = StringVar()
if prefs["monitor_output_device"] in monitor_output_devices_dict:
    monitor_output_device_var.set(prefs["monitor_output_device"])
else:
    if monitor_output_devices_dict:
        monitor_output_device_var.set(next(iter(monitor_output_devices_dict)))
    else:
        monitor_output_device_var.set('')
# output device
tk.Label(tts_tab, text="Monitor Output Device (Speakers/Headphones):").pack(pady=(10, 0))
monitor_output_dropdown = ttk.Combobox(tts_tab, textvariable=monitor_output_device_var, values=list(monitor_output_devices_dict.keys()), width=60)
monitor_output_dropdown.pack()

def save_tts_device(e=None):
    save_preferences({**prefs, "tts_output_device": tts_output_device_var.get()})
def save_monitor_device(e=None):
    save_preferences({**prefs, "monitor_output_device": monitor_output_device_var.get()})
def save_voice(e=None):
    save_preferences({**prefs, "last_voice": voice_var.get()})

tts_output_dropdown.bind("<<ComboboxSelected>>", save_tts_device)
monitor_output_dropdown.bind("<<ComboboxSelected>>", save_monitor_device)
voice_dropdown.bind("<<ComboboxSelected>>", save_voice)

tk.Label(tts_tab, text="TTS Volume:").pack(pady=(10, 0))
tts_volume_var = tk.DoubleVar()
tts_volume_var.set(1.0)
tts_volume_slider = tk.Scale(tts_tab, variable=tts_volume_var, from_=0.1, to=15, resolution=0.1, orient='horizontal', length=400)
tts_volume_slider.pack()



tts_lock = threading.Lock()
# actually make the text into voice, or in other terms, synthesize it
# single synthesise coroutine for edge_tts
async def synthesize_edge(text, voice, filename, timeout=3):
    communicate = edge_tts.Communicate(text, voice)
    # run with timeout to fail fast
    await asyncio.wait_for(communicate.save(filename), timeout=timeout)

def synthesize_text(text, filename):
    online = False
    try:
        socket.create_connection(("www.bing.com", 80), timeout=1)
        online = True
    except OSError:
        online = False

    voice = voice_var.get() or "en-US-GuyNeural"

    if online:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(synthesize_edge(text, voice, filename, timeout=10))
            loop.close()
            return
        except Exception as e:
            print(f"[Warning] Edge TTS failed. Falling back to pyttsx3: {e}")

    # fallback pyttsx3 immediately
    engine = pyttsx3.init()
    for v in engine.getProperty('voices'):
        if v.name == voice:
            engine.setProperty('voice', v.id)
            break
    engine.save_to_file(text, filename)
    engine.runAndWait()
    engine.stop()




# thread for the text
def voicify_text_thread():
    if not tts_lock.acquire(blocking=False):
        return

    try:
        text = entry.get()
        if not text:
            return

        selected_device_name = tts_output_device_var.get()
        if selected_device_name not in tts_output_devices_dict or selected_device_name == '':
            root.after(0, lambda: messagebox.showError("Error", "Please select a valid TTS output device!"))
            return

        selected_monitor_name = monitor_output_device_var.get()
        if monitor_var.get():
            if selected_monitor_name not in monitor_output_devices_dict or selected_monitor_name == '':
                print("[Error] Invalid Monitor output device selected")
                root.after(0, lambda: messagebox.showError("Error", "Please select a valid Monitor output device!"))
                return


        

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            temp_path = f.name

        synthesize_text(text, temp_path)
        time.sleep(1.5)

        if not os.path.exists(temp_path):
            return

        size = os.path.getsize(temp_path)
        if size == 0:
            return

        data, samplerate = load_audio_file(temp_path)

        target_samplerate = 44100
        if samplerate != target_samplerate:
            data = resampy.resample(data.T, samplerate, target_samplerate).T
            samplerate = target_samplerate

        data = data.astype('float32')

        def to_mono(audio):
            if len(audio.shape) > 1 and audio.shape[1] > 1:
                return np.mean(audio, axis=1)
            return audio

        data_mono = to_mono(data)

        volume = tts_volume_var.get()
        data_mono = data_mono * volume

        tts_out_idx = int(tts_output_devices_dict[selected_device_name])
        monitor_out_idx = int(monitor_output_devices_dict[selected_monitor_name]) if monitor_var.get() else None

        tts_device_info = sd.query_devices(tts_out_idx)
        tts_channels = min(tts_device_info['max_output_channels'], 2)

        if monitor_var.get():
            monitor_device_info = sd.query_devices(monitor_out_idx)
            monitor_channels = min(monitor_device_info['max_output_channels'], 2)
        else:
            monitor_channels = None

        def prepare_audio(audio, channels):
            if channels == 1:
                return audio
            else:
                return np.column_stack([audio, audio])

        tts_audio = prepare_audio(data_mono, tts_channels)
        monitor_audio = prepare_audio(data_mono, monitor_channels) if monitor_var.get() else None

        blocksize = 1024
        total_frames = len(tts_audio)
        pos = 0

        tts_stream = sd.OutputStream(device=tts_out_idx, samplerate=samplerate, channels=tts_channels, blocksize=blocksize, latency='low')
        monitor_stream = None
        if monitor_var.get():
            monitor_stream = sd.OutputStream(device=monitor_out_idx, samplerate=samplerate, channels=monitor_channels, blocksize=blocksize, latency='low')

        print("[Log] Starting TTS stream...")
        tts_stream.start()
        print("[Log] TTS stream started")
        if monitor_stream:
            monitor_stream.start()

        while pos < total_frames:
            end_pos = min(pos + blocksize, total_frames)
            chunk_tts = tts_audio[pos:end_pos]

            try:
                tts_stream.write(chunk_tts)
            except Exception as e:
                print(f"[Error] Exception during TTS stream write: {e}")
                break

            if monitor_stream:
                chunk_monitor = monitor_audio[pos:end_pos]
                try:
                    monitor_stream.write(chunk_monitor)
                except Exception as e:
                    print(f"[Error] Exception during Monitor stream write: {e}")
                    break

            volume_level = np.sqrt(np.mean(chunk_tts**2))
            root.after(0, lambda val=min(volume_level * 1000, 100): volume_meter.config(value=val))
            pos += blocksize

        print("[Log] Finished audio playback loop")

        print("[Log] Stopping TTS stream...")
        tts_stream.stop()
        tts_stream.close()
        print("[Log] TTS stream stopped and closed")

        if monitor_stream:
            monitor_stream.stop()
            monitor_stream.close()

        print(f"[Log] Attempting to remove temp file: {temp_path}")
        os.remove(temp_path)
        print("[Log] Temp file removed successfully")
    except Exception as e:
        print(f"[Error in voicify_text_thread] Exception: {e}")
    finally:
        root.after(0, lambda: button.config(state="normal", text="Voxify It"))
        root.after(0, lambda: volume_meter.config(value=0))
        tts_lock.release()

# the handler for the button. actually makes the text into voice
def voicify_text():
    if button['state'] == 'disabled':
        print("[Log] Button disabled, ignoring call")
        return
    button.config(state="disabled", text="Playing...")
    volume_meter['value'] = 0
    threading.Thread(target=voicify_text_thread, daemon=True).start()

# renamed from "TTS it" to "Voxify it", this is due to an error on my end, I accidently left it in for development purposes, and easier time reading.
button = tk.Button(tts_tab, text="Voxify it", command=voicify_text)
button.pack(pady=20)

sb_tab = tk.Frame(notebook)
notebook.add(sb_tab, text='Soundboard')
add_version_label(sb_tab)

settings_tab = tk.Frame(notebook)
notebook.add(settings_tab, text='Settings')
add_version_label(settings_tab)

topmost_var = BooleanVar(value=False)

# simple, toggles topmost. topmost means it goes over everything, even if you click on a new window
def on_topmost_toggle():
    root.wm_attributes("-topmost", topmost_var.get())
# the setting for it
topmost_check = tk.Checkbutton(settings_tab, text="Always on Top (Topmost)", variable=topmost_var, command=on_topmost_toggle)
tk.Checkbutton(settings_tab, text="(BETA) New keybinds", variable=beta_keybinds_var).pack(pady=5)
topmost_check.pack(pady=20)
# sound table
soundboard_sounds = []
# keybind
sound_tree = ttk.Treeview(sb_tab, columns=("Name", "Keybind"), show="headings", height=10)
sound_tree.heading("Name", text="Sound Name")
sound_tree.heading("Keybind", text="Keybind")
sound_tree.column("Name", width=300, anchor="w")
sound_tree.column("Keybind", width=100, anchor="center")
sound_tree.pack(pady=10, fill="x")
# monitor (the sequel)
sb_monitor_var = BooleanVar()
tk.Checkbutton(sb_tab, text="Monitor (Hear It)", variable=sb_monitor_var).pack()
sb_loop_var = BooleanVar(value=False)
# makes it loop. added in v1.1 hotfix 1
tk.Checkbutton(sb_tab, text="Loop Selected Sound", variable=sb_loop_var).pack()

sb_volume_scale = tk.Scale(sb_tab, from_=0.1, to=10, resolution=0.05, orient="horizontal", label="Volume", length=200)

sb_volume_scale.set(1.5)
sb_volume_scale.pack()

sb_pitch_scale = tk.Scale(sb_tab, from_=0.5, to=3, resolution=0.02, orient="horizontal", label="Pitch", length=200)
sb_pitch_scale.set(1.0)
sb_pitch_scale.pack()

# this just refreshes the soundboard list
def refresh_sound_list():
    for item in sound_tree.get_children():
        sound_tree.delete(item)
    for sound in soundboard_sounds:
        name = sound['name']
        key = sound.get('keybind') or ""
        sound_tree.insert("", tk.END, values=(name, key))

# loads audio
def load_audio_to_np(path, target_sr=44100, channels=2):
    try:
        out, _ = (
            FFMPEG_PATH
            .input(path)
            .output('pipe:', format='f32le', acodec='pcm_f32le', ar=target_sr, ac=channels)
            .run(capture_stdout=True, capture_stderr=True)
        )
        audio = np.frombuffer(out, dtype=np.float32)
        audio = audio.reshape(-1, channels)
        return audio, target_sr
    except ffmpeg.Error as e:
        raise RuntimeError(f"[FFMPEG Error] {e.stderr.decode()}")
# helper, loads the audio file
# beta 1.2 makes this use ffmpeg
def load_audio_file(path):
    try:
        out, err = (
            ffmpeg
            .input(path)
            .output('pipe:', format='f32le', ac=2, ar='44100')
            .run(capture_stdout=True, capture_stderr=True, cmd=FFMPEG_PATH)
        )
        # convert
        audio = np.frombuffer(out, np.float32)
        # reshape
        audio = audio.reshape((-1, 2))
        samplerate = 44100
        return audio, samplerate
    except ffmpeg.Error as e:
        raise RuntimeError(f"[Error] Could not load audio '{path}': {e.stderr.decode()}")



# what adds the sound
def add_sound():
    valid_exts = (".wav", ".flac", ".mp3", ".ogg", ".m4a", ".aac", ".wma", ".aiff",".alac", ".ac3", ".amr", ".caf", ".mp2", ".opus", ".ra", ".mka")
    paths = filedialog.askopenfilenames(
        filetypes=[
            ("Audio files", "*.wav *.flac *.mp3 *.ogg *.m4a *.aac *.wma *.aiff *.alac *.ac3 *.amr *.caf *.mp2 *.opus *.ra *.mka"),
            ("All files", "*.*")  # not recommended; supports only known audio formats
        ]
    )
    if not paths:
        return
    for path in paths:
        if not path.lower().endswith(valid_exts):
            print(f"[Skip] Unsupported file type: {path}") # self explanatory
            continue

        filename = os.path.basename(path)
        dest = os.path.join(sounds_dir, filename)
        if not os.path.exists(dest):
            shutil.copy2(path, dest)

        try:
            data, samplerate = load_audio_file(dest)
            register_all_keybinds()
        except Exception as e:
            print(f"[Error] Failed to load '{filename}': {e}")
            continue

        keybind = prefs.get("keybinds", {}).get(filename)
        soundboard_sounds.append({
            'path': dest,
            'data': None,  
            'samplerate': None,
            'name': filename,
            'keybind': keybind
        })
    register_all_keybinds()
    refresh_sound_list()


# sets a keybind, to the audio
def set_keybind():
    sel = sound_tree.selection()
    if not sel:
        return
    item = sel[0]
    values = sound_tree.item(item, "values")
    name = values[0]
    idx = next((i for i, s in enumerate(soundboard_sounds) if s['name'] == name), None)
    if idx is None:
        return

    def on_key(e):
        for sound in soundboard_sounds:
            key = sound.get('keybind')
            if key and keyboard.is_pressed(key):
                play_sound_by_name(sound['name'])

        soundboard_sounds[idx]['keybind'] = e.name
        print(f"[Log] Keybind for '{soundboard_sounds[idx]['name']}' set to: {e.name}")
        keyboard.unhook(hook)
        register_all_keybinds()
        refresh_sound_list()

    messagebox.showinfo("Keybind", "Exit this window, and then press a key to set a keybind.") # CLICK OK, THEN PRESS YOUR KEY. note: changed the message to be clearer.
    hook = keyboard.on_press(on_key)

# remove the selected sound
def remove_sound():
    sel = sound_tree.selection()
    if not sel:
        messagebox.showinfo("Remove Sound", "No sound selected.")
        return

    item = sel[0]
    values = sound_tree.item(item, "values")
    name = values[0]

    confirm = messagebox.askyesno("Confirm Delete", f"Remove '{name}' from the soundboard?")
    if not confirm:
        return

    idx = next((i for i, s in enumerate(soundboard_sounds) if s['name'] == name), None)
    if idx is not None:
        # delete the file from the Sounds folder too
        try:
            os.remove(soundboard_sounds[idx]['path'])
        except OSError:
            print(f"[Warning] Failed to remove file: {soundboard_sounds[idx]['path']}")
        del soundboard_sounds[idx]

    refresh_sound_list()
    register_all_keybinds()

# clear keybind for the selected sound
def clear_keybind():
    sel = sound_tree.selection()
    if not sel:
        messagebox.showinfo("Clear Keybind", "No sound selected.")
        return

    item = sel[0]
    values = sound_tree.item(item, "values")
    name = values[0]

    idx = next((i for i, s in enumerate(soundboard_sounds) if s['name'] == name), None)
    if idx is not None:
        soundboard_sounds[idx]['keybind'] = None

    refresh_sound_list()
    register_all_keybinds()


# another helper with playing audio, but by name
def play_sound_by_name(name):
    for i, s in enumerate(soundboard_sounds):
        if s['name'] == name:
            sound_tree.selection_remove(sound_tree.selection())
            for item in sound_tree.get_children():
                if sound_tree.item(item, "values")[0] == name:
                    sound_tree.selection_set(item)
                    sound_tree.see(item)
                    break
            play_sound()
            break
# self explanatory.
def on_close():
    keybinds = {s['name']: s['keybind'] for s in soundboard_sounds if s.get('keybind')}
    prefs['keybinds'] = keybinds
    save_preferences(prefs)
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)
# trimmed area down of empty lines
active_streams = []


def pitch_shift(data: np.ndarray, samplerate: int, pitch_factor: float):
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    FFMPEG_PATH = os.path.join(SCRIPT_DIR, "dependancies", "ffmpeg.exe")

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as in_f:
        sf.write(in_f.name, data, samplerate)
        in_f_path = in_f.name

    out_f = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    out_f_path = out_f.name
    out_f.close()

    try:
        if pitch_factor < 0.5 or pitch_factor > 3.0:
            raise ValueError("Pitch factor must be between .5 and 3")

        # ⬇ only asetrate = pitch + speed change
        new_rate = int(samplerate * pitch_factor)
        filter_str = f"asetrate={new_rate}"

        command = [
            FFMPEG_PATH,
            "-y",
            "-i", in_f_path,
            "-filter:a", filter_str,
            "-vn",
            "-ar", str(new_rate),  # output file also has this new rate
            out_f_path
        ]

        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        shifted_data, shifted_sr = sf.read(out_f_path, dtype='float32')
    finally:
        if os.path.exists(in_f_path):
            os.remove(in_f_path)
        if os.path.exists(out_f_path):
            os.remove(out_f_path)

    return shifted_data, new_rate  # new sample rate matches increased pitch/speed


loop_thread = None
loop_stop_flag = threading.Event()

# plays the sound
def play_sound():
    global loop_thread, loop_stop_flag, new_sr

    volume = sb_volume_scale.get()
    sel = sound_tree.selection()
    if not sel:
        return
    item = sel[0]
    values = sound_tree.item(item, "values")
    name = values[0]
    idx = next((i for i, s in enumerate(soundboard_sounds) if s['name'] == name), None)
    if idx is None:
        return
    sound = soundboard_sounds[idx]

    if sound['data'] is None or sound['samplerate'] is None:
        data, samplerate = load_audio_file(sound['path'])
        sound['data'] = data
        sound['samplerate'] = samplerate

    original_data = sound['data']
    original_sr = sound['samplerate']
    pitch_factor = sb_pitch_scale.get()
    new_sr = original_sr
    data = original_data * volume

    try:
        if pitch_factor != 1.0:
            data, new_sr = pitch_shift(data, original_sr, pitch_factor)
    except Exception as e:
        print(f"[Error] Pitch shifting failed: {e}")
        return

    samplerate = new_sr
    if data.ndim == 1: # mono audio
        data = np.column_stack([data, data])
    elif data.shape[1] == 1: # mono audio
        data = np.column_stack([data[:, 0], data[:, 0]])
    out_idx = int(tts_output_devices_dict[tts_output_device_var.get()]) # the index of output devices. what you see in the table.
    mon_idx = int(monitor_output_devices_dict[monitor_output_device_var.get()]) # the index of monitor indexes. what you see for output devices.

    channels_out = min(sd.query_devices(out_idx)['max_output_channels'], 2)
    channels_mon = min(sd.query_devices(mon_idx)['max_output_channels'], 2)
    # this prepares audio.
    def prepare_audio(audio, channels):
        if channels == 1:
            return np.mean(audio, axis=1)
        elif channels == 2:
            if audio.shape[1] == 1:
                return np.column_stack([audio[:,0], audio[:,0]])
            return audio
        else:
            return audio

    out_audio = prepare_audio(data, channels_out)
    mon_audio = prepare_audio(data, channels_mon)
    out_audio = out_audio * volume
    mon_audio = mon_audio * volume

    # streams the output. aka what you hear
    def stream_func():
        blocksize = 256
        pos = 0
        total = len(out_audio)

        try:
            out_stream = sd.OutputStream(device=out_idx, samplerate=samplerate, channels=channels_out, blocksize=blocksize, latency='low')
            mon_stream = None

            if sb_monitor_var.get():
                mon_stream = sd.OutputStream(device=mon_idx, samplerate=samplerate, channels=channels_mon, blocksize=blocksize, latency='low')
            out_stream.start()
            if mon_stream:
                mon_stream.start()
            while pos < total and not loop_stop_flag.is_set():
                end = min(pos + blocksize, total)
                out_chunk = out_audio[pos:end]
                mon_chunk = mon_audio[pos:end] if mon_stream else None

                try:
                    out_stream.write(np.ascontiguousarray(out_chunk))
                except Exception as e:
                    print(f"[Error] Soundboard output stream error: {e}")
                    break

                if mon_stream:
                    try:
                        mon_stream.write(np.ascontiguousarray(mon_chunk))
                    except Exception as e:
                        print(f"[Error] Soundboard monitor stream error: {e}")
                        break



                pos = end
                if pos == total and sb_loop_var.get():
                    pos = 0

        except Exception as e:
            print(f"[Error] Exception during stream setup or playback: {e}")
        finally:
            try:
                out_stream.stop()
                out_stream.close()
            except:
                pass

            if mon_stream:
                try:
                    mon_stream.stop()
                    mon_stream.close()
                except:
                    pass

    if loop_thread and loop_thread.is_alive():
        loop_stop_flag.set()
        loop_thread.join()
    loop_stop_flag.clear()
    loop_thread = threading.Thread(target=stream_func, daemon=True)
    loop_thread.start()


tk.Button(sb_tab, text="Set Keybind", command=set_keybind).pack(pady=5)
tk.Button(sb_tab, text="Remove Sound", command=remove_sound).pack(pady=5)
tk.Button(sb_tab, text="Clear Keybind", command=clear_keybind).pack(pady=5)
# stops the sounds.
# V1.1 didn't work very great with this. This was fixed in Hotfix 1.
def stop_all():
    global loop_thread, loop_stop_flag
    sd.stop()

    if loop_thread and loop_thread.is_alive():
        loop_stop_flag.set()

    for stream in active_streams[:]:
        if not stream.is_alive():
            active_streams.remove(stream)

    sb_loop_var.set(False)
tk.Button(sb_tab, text="Stop All Sounds", command=stop_all).pack(pady=5) # button to stop them


add_button = tk.Button(sb_tab, text="Add Sound(s)", command=add_sound) # adds sounds. this is the button
add_button.pack(pady=5) # packing

def sound_thread(): # seperate thread to prevent it from freezing the ui
    threading.Thread(target=play_sound, daemon=True).start() # the thread

play_button = tk.Button(sb_tab, text="Play Selected Sound", command=sound_thread)# plays the sound. this is the button.

play_button.pack(pady=5) # packing
def warm_up_streams():
    try:
        tts_out_idx = int(tts_output_devices_dict[tts_output_device_var.get()])
        mon_out_idx = int(monitor_output_devices_dict[monitor_output_device_var.get()])
        dummy_audio = np.zeros((4410, 2), dtype=np.float32)
        with sd.OutputStream(device=tts_out_idx, samplerate=44100, channels=2, blocksize=256):
            sd.sleep(50)  
            pass 
        with sd.OutputStream(device=mon_out_idx, samplerate=44100, channels=2, blocksize=256):
            sd.sleep(50)
            pass
    except Exception as e:
        print(f"[Warning] Stream warm-up failed: {e}")
def warm_up_soundboard_streams():
    try:
        out_idx = int(tts_output_devices_dict[tts_output_device_var.get()])
        mon_idx = int(monitor_output_devices_dict[monitor_output_device_var.get()])
        dummy_audio = np.zeros((2205, 2), dtype=np.float32)  # ~0.05s of silence @ 44.1kHz
        with sd.OutputStream(device=out_idx, samplerate=44100, channels=2, blocksize=256) as stream:
            stream.write(dummy_audio)
        if sb_monitor_var.get():
            with sd.OutputStream(device=mon_idx, samplerate=44100, channels=2, blocksize=256) as stream:
                stream.write(dummy_audio)

    except Exception as e:
        print(f"[Warning] Soundboard warm-up failed: {e}")



root.after(100, warm_up_streams) # warms up the streams, reducing delay
root.after(100, warm_up_soundboard_streams) # warms up the soundboard streams, reducing delay
autoload()

# in total, this could take max 300ms to 3 seconds to load

def check_internet():
    try:
        socket.create_connection(("www.bing.com", 80), timeout=2)
        return True
    except OSError:
        return False

def update_status():
    if check_internet():
        status_label.config(text="Internet: Connected", fg="green")
    else:
        status_label.config(text="Internet: Disconnected", fg="red")
    root.after(5000, update_status)  # check every 5 seconds

status_label = tk.Label(root, text="Checking...", anchor="w")
status_label.pack(side="bottom", fill="x", padx=5, pady=5)

update_status()  # start the loop

# my code isnt too great but works

root.mainloop()