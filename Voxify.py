import os
import resampy
import json
import shutil
import pyttsx3
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
import tempfile
import numpy as np
import soundfile as sf
import io
import edge_tts
import keyboard
base_dir = os.path.dirname(os.path.abspath(__file__))
sounds_dir = os.path.join(base_dir, "Sounds")
prefs_path = os.path.join(base_dir, "voicify_prefs.json")
os.makedirs(sounds_dir, exist_ok=True)
beta_keybinds_var = BooleanVar(value=False)

hotkey_refs = []  

def register_all_keybinds():
    global hotkey_refs

    for ref in hotkey_refs:
        try:
            keyboard.unhook(ref)
        except Exception as e:
            print(f"[Warning] Failed to unhook: {e}")
    hotkey_refs.clear()

    def on_key(e):
        for sound in soundboard_sounds:
            key = sound.get('keybind')
            if key and e.name == key:
                play_sound_by_name(sound['name'])

    hook = keyboard.on_press(on_key)
    hotkey_refs.append(hook)


    for sound in soundboard_sounds:
        key = sound.get('keybind')
        if key:
            try:
                ref = keyboard.add_hotkey(key, lambda s=sound['name']: play_sound_by_name(s))
                hotkey_refs.append(ref)
            except Exception as e:
                print(f"[Error] Failed to register hotkey '{key}' for '{sound['name']}': {e}")



def load_audio_any_format(path, target_sr=44100):
    command = [
        'ffmpeg', '-i', path,
        '-f', 'f32le',              
        '-acodec', 'pcm_f32le',
        '-ar', str(target_sr),      
        '-ac', '2',                 
        '-loglevel', 'error',
        '-hide_banner', '-'
    ]

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg error:\n{process.stderr.decode()}")

    raw_audio = np.frombuffer(process.stdout, dtype=np.float32)
    audio = raw_audio.reshape(-1, 2)  
    return audio, target_sr

default_prefs = {
    "tts_output_device": None,
    "monitor_output_device": None,
    "last_voice": None
}

def save_preferences(prefs):
    with open(prefs_path, "w") as f:
        json.dump(prefs, f)

def load_preferences():
    if os.path.exists(prefs_path):
        with open(prefs_path, "r") as f:
            return json.load(f)
    return default_prefs.copy()

prefs = load_preferences()

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

engine = pyttsx3.init()
voices = engine.getProperty('voices')
EDGE_VOICES = [
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-US-AriaNeural",
    "en-GB-RyanNeural",
    "en-GB-SoniaNeural",
]

voice_names = EDGE_VOICES

root = tk.Tk()
root.title("Voicify TTS")
root.geometry("550x700")

notebook = ttk.Notebook(root)
notebook.pack(fill='both', expand=True)

tts_tab = tk.Frame(notebook)
notebook.add(tts_tab, text='TTS')

entry = tk.Entry(tts_tab, width=60)
entry.pack(pady=15)

monitor_var = BooleanVar()
monitor_check = tk.Checkbutton(tts_tab, text="Monitor (Hear It Yourself)", variable=monitor_var)
monitor_check.pack()

tk.Label(tts_tab, text="Volume Meter:").pack(pady=(10,0))
volume_meter = ttk.Progressbar(tts_tab, orient='horizontal', length=400, mode='determinate', maximum=100)
volume_meter.pack()

voice_var = StringVar()
voice_var.set(prefs["last_voice"] or voice_names[0])
tk.Label(tts_tab, text="Choose Voice:").pack(pady=(10, 0))
voice_dropdown = ttk.Combobox(tts_tab, textvariable=voice_var, values=voice_names, width=60)
voice_dropdown.pack()

tts_output_devices = get_output_devices()
tts_output_devices_dict = {f"[{idx}] {name}": idx for idx, name in tts_output_devices}

tts_output_device_var = StringVar()
if prefs["tts_output_device"] in tts_output_devices_dict:
    tts_output_device_var.set(prefs["tts_output_device"])
else:
    if tts_output_devices_dict:
        tts_output_device_var.set(next(iter(tts_output_devices_dict)))
    else:
        tts_output_device_var.set('')

tk.Label(tts_tab, text="TTS Output Device (Virtual Mic playback):").pack(pady=(10, 0))
tts_output_dropdown = ttk.Combobox(tts_tab, textvariable=tts_output_device_var, values=list(tts_output_devices_dict.keys()), width=60)
tts_output_dropdown.pack()

monitor_output_devices = get_output_devices()
monitor_output_devices_dict = {f"[{idx}] {name}": idx for idx, name in monitor_output_devices}

monitor_output_device_var = StringVar()
if prefs["monitor_output_device"] in monitor_output_devices_dict:
    monitor_output_device_var.set(prefs["monitor_output_device"])
else:
    if monitor_output_devices_dict:
        monitor_output_device_var.set(next(iter(monitor_output_devices_dict)))
    else:
        monitor_output_device_var.set('')

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
tts_volume_slider = tk.Scale(tts_tab, variable=tts_volume_var, from_=0.8, to=6.5, resolution=0.1, orient='horizontal', length=400)
tts_volume_slider.pack()

engine = pyttsx3.init()
voices = engine.getProperty('voices')
voice_names = [v.name for v in voices]

tts_lock = threading.Lock()

def synthesize_text(text, filename):
    voice = voice_var.get()
    if not voice:
        voice = "en-US-GuyNeural"

    async def _speak():
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(filename)
        except Exception as e:
            print(f"[Error] edge-tts synthesis failed: {e}")

    try:
        asyncio.run(_speak())
        time.sleep(0.2)
    except Exception as e:
        print(f"[Error] asyncio run failed: {e}")

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

        voice_id = None
        for v in voices:
            if v.name == voice_var.get():
                voice_id = v.id
                break
        if voice_id is not None:
            engine.setProperty('voice', voice_id)
        else:
            print("[Warning] Selected voice not found, using default voice")

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

        tts_stream = sd.OutputStream(device=tts_out_idx, samplerate=samplerate, channels=tts_channels, blocksize=blocksize)
        monitor_stream = None
        if monitor_var.get():
            monitor_stream = sd.OutputStream(device=monitor_out_idx, samplerate=samplerate, channels=monitor_channels, blocksize=blocksize)

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
        root.after(0, lambda: button.config(state="normal", text="Voicify It"))
        root.after(0, lambda: volume_meter.config(value=0))
        tts_lock.release()

def voicify_text():
    if button['state'] == 'disabled':
        print("[Log] Button disabled, ignoring call")
        return
    button.config(state="disabled", text="Playing...")
    volume_meter['value'] = 0
    threading.Thread(target=voicify_text_thread, daemon=True).start()

button = tk.Button(tts_tab, text="Voicify It", command=voicify_text)
button.pack(pady=20)

sb_tab = tk.Frame(notebook)
notebook.add(sb_tab, text='Soundboard')

settings_tab = tk.Frame(notebook)
notebook.add(settings_tab, text='Settings')

topmost_var = BooleanVar(value=False)

def on_topmost_toggle():
    root.wm_attributes("-topmost", topmost_var.get())

topmost_check = tk.Checkbutton(settings_tab, text="Always on Top (Topmost)", variable=topmost_var, command=on_topmost_toggle)
topmost_check.pack(pady=20)

soundboard_sounds = []

sound_tree = ttk.Treeview(sb_tab, columns=("Name", "Keybind"), show="headings", height=10)
sound_tree.heading("Name", text="Sound Name")
sound_tree.heading("Keybind", text="Keybind")
sound_tree.column("Name", width=300, anchor="w")
sound_tree.column("Keybind", width=100, anchor="center")
sound_tree.pack(pady=10, fill="x")

sb_monitor_var = BooleanVar()
tk.Checkbutton(sb_tab, text="Monitor (Hear It)", variable=sb_monitor_var).pack()
sb_loop_var = BooleanVar(value=False)
tk.Checkbutton(sb_tab, text="Loop Selected Sound", variable=sb_loop_var).pack()

sb_volume_scale = tk.Scale(sb_tab, from_=0.1, to=3.0, resolution=0.1, orient="horizontal", label="Volume")
sb_volume_scale.set(1.0)
sb_volume_scale.pack()

sb_pitch_scale = tk.Scale(sb_tab, from_=0.4, to=3.0, resolution=0.1, orient="horizontal", label="Pitch")
sb_pitch_scale.set(1.0)
sb_pitch_scale.pack()

def refresh_sound_list():
    for item in sound_tree.get_children():
        sound_tree.delete(item)
    for sound in soundboard_sounds:
        name = sound['name']
        key = sound.get('keybind') or ""
        sound_tree.insert("", tk.END, values=(name, key))

def load_audio_to_np(path, target_sr=44100, channels=2):
    command = [
        'ffmpeg', '-i', path,
        '-f', 'f32le',
        '-acodec', 'pcm_f32le',
        '-ar', str(target_sr),
        '-ac', str(channels),
        '-loglevel', 'error',
        '-hide_banner', '-'
    ]

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        raise RuntimeError(f"[FFMPEG] Error loading audio: {process.stderr.decode()}")

    audio = np.frombuffer(process.stdout, dtype=np.float32)
    audio = audio.reshape(-1, channels)
    return audio, target_sr

def load_audio_file(path):
    try:
        data, samplerate = sf.read(path, dtype='float32')
        
        if len(data.shape) == 1:
            data = np.column_stack((data, data))
        return data, samplerate
    except Exception as e:
        raise RuntimeError(f"[Error] Could not load audio '{path}': {e}")

def add_sound():
    valid_exts = (".wav", ".flac", ".mp3", ".ogg")
    paths = filedialog.askopenfilenames(
        filetypes=[
            ("Audio files", "*.wav *.flac *.mp3 *.ogg"),
            ("All files", "*.*")
        ]
    )
    if not paths:
        return
    for path in paths:
        if not path.lower().endswith(valid_exts):
            print(f"[Skip] Unsupported file type: {path}")
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
            'data': data,
            'samplerate': samplerate,
            'name': filename,
            'keybind': keybind
        })
    register_all_keybinds()
    refresh_sound_list()



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
    sound = soundboard_sounds[idx]

    def on_key(e):
        soundboard_sounds[idx]['keybind'] = e.name
        print(f"[Log] Keybind for '{soundboard_sounds[idx]['name']}' set to: {e.name}")
        keyboard.unhook(hook)  
        register_all_keybinds()
    messagebox.showinfo("Keybind", "Press any key to assign to the selected sound.")
    hook = keyboard.on_press(on_key)

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

def on_close():
    keybinds = {s['name']: s['keybind'] for s in soundboard_sounds if s.get('keybind')}
    prefs['keybinds'] = keybinds
    save_preferences(prefs)
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)




active_streams = []

loop_thread = None
loop_stop_flag = threading.Event()

def play_sound():
    global loop_thread, loop_stop_flag
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
    
    data = sound['data'] * sb_volume_scale.get()
    samplerate = int(sound['samplerate'] * sb_pitch_scale.get())

    out_idx = int(tts_output_devices_dict[tts_output_device_var.get()])
    mon_idx = int(monitor_output_devices_dict[monitor_output_device_var.get()])

    channels_out = min(sd.query_devices(out_idx)['max_output_channels'], 2)
    channels_mon = min(sd.query_devices(mon_idx)['max_output_channels'], 2)

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

    def stream_func():
        blocksize = 1024
        pos = 0
        total = len(out_audio)
        out_stream = sd.OutputStream(device=out_idx, samplerate=samplerate, channels=channels_out, blocksize=blocksize)
        mon_stream = sd.OutputStream(device=mon_idx, samplerate=samplerate, channels=channels_mon, blocksize=blocksize) if sb_monitor_var.get() else None
        out_stream.start()
        if mon_stream:
            mon_stream.start()
        while pos < total and not loop_stop_flag.is_set():
            end = min(pos+blocksize, total)
            out_chunk = out_audio[pos:end]
            try:
                out_stream.write(out_chunk)
            except Exception as e:
                print(f"[Error] Soundboard output stream error: {e}")
                break
            if mon_stream:
                mon_chunk = mon_audio[pos:end]
                try:
                    mon_stream.write(mon_chunk)
                except Exception as e:
                    print(f"[Error] Soundboard monitor stream error: {e}")
                    break
            pos = end
            if pos == total and sb_loop_var.get():
                pos = 0
        out_stream.stop()
        out_stream.close()
        if mon_stream:
            mon_stream.stop()
            mon_stream.close()

    if loop_thread and loop_thread.is_alive():
        loop_stop_flag.set()
        loop_thread.join()
    loop_stop_flag.clear()
    loop_thread = threading.Thread(target=stream_func, daemon=True)
    loop_thread.start()


tk.Button(sb_tab, text="Set Keybind", command=set_keybind).pack(pady=5)


def stop_all():
    global loop_thread, loop_stop_flag
    sd.stop()

    if loop_thread and loop_thread.is_alive():
        loop_stop_flag.set()

    for stream in active_streams[:]:
        if not stream.is_alive():
            active_streams.remove(stream)

    sb_loop_var.set(False)
tk.Button(sb_tab, text="Stop All Sounds", command=stop_all).pack(pady=5)


add_button = tk.Button(sb_tab, text="Add Sound(s)", command=add_sound)
add_button.pack(pady=5)

play_button = tk.Button(sb_tab, text="Play Selected Sound", command=play_sound)
play_button.pack(pady=5)

root.mainloop()
