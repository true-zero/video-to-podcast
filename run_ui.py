import tkinter as tk
from tkinter.filedialog import askdirectory
from os.path import isdir, splitext, join
from vidtopod import convert
from sys import platform
from os import walk

class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.create_widgets()
        self._lang_widgets = []
        self._vcmd = self.register(lambda x: str.isdigit(x) or x == "")


    def create_widgets(self):
        storage_location = self.draw_path_pick('location of where to store', row=0)
        videos_location = self.draw_path_pick('location of videos to convert', row=1)

        var1 = tk.IntVar()
        lang_code = tk.StringVar(None)
        tk.Checkbutton(self.master, text='set specific audio track?', variable=var1,
                       command=lambda: self.draw_lang_code(lang_code, not var1.get() == 0)).grid(row=3, sticky=tk.W)

        var2 = tk.IntVar()
        subtitle_sync_ms = tk.IntVar(None)
        so_widgets = []
        tk.Checkbutton(self.master, text='set subtitle offset?', variable=var2,
                       command=lambda: self.draw_ms('subtitle offset', subtitle_sync_ms, so_widgets, 6, not var2.get() == 0)).grid(row=5, sticky=tk.W)

        var3 = tk.IntVar()
        padding_ms = tk.IntVar(None)
        pad_widgets = []

        tk.Checkbutton(self.master, text='pad subtitles?', variable=var3,
                       command=lambda: self.draw_ms('pad timing', padding_ms, pad_widgets, 8, not var3.get() == 0)).grid(row=7, sticky=tk.W)

        tk.Button(self.master, text='Run', command=lambda: self.generate_btn_clicked(
            storage_location.get(),
            videos_location.get(),
            None if var1.get() == 0 else lang_code.get(),
            None if var2.get() == 0 else subtitle_sync_ms.get(),
            None if var3.get() == 0 else padding_ms.get(),
        )).grid(row=9, column=2)

    def draw_path_pick(self, text, row):
        tk.Label(self.master, text=text, height=1).grid(row=row)
        v = tk.StringVar(None)
        tk.Entry(self.master, textvariable=v, width=50,
                 state='disabled').grid(row=row, column=1)
        tk.Button(self.master, text='Pick', command=lambda: v.set(askdirectory())).grid(row=row, column=2)
        return v

    def draw_lang_code(self, v, is_checked):
        if not is_checked:
            for w in self._lang_widgets:
                w.destroy()

            return

        lbl = tk.Label(self.master, text='lang code', height=1)
        lbl.grid(row=4, sticky=tk.W)
        entry = tk.Entry(self.master, textvariable=v, width=10)
        entry.grid(row=4, column=1, sticky=tk.W)

        self._lang_widgets.append(lbl)
        self._lang_widgets.append(entry)

    def draw_ms(self, txt, v, ms_widgets, row, is_checked):
        if not is_checked:
            for w in ms_widgets:
                w.destroy()

            return

        lbl = tk.Label(self.master, text=txt + ' (ms)', height=1)
        lbl.grid(row=row, sticky=tk.W)
        entry = tk.Entry(self.master, validate='all', validatecommand=(self._vcmd, '%P'),
                         textvariable=v, width=10)
        entry.grid(row=row, column=1, sticky=tk.W)

        ms_widgets.append(lbl)
        ms_widgets.append(entry)

    def generate_btn_clicked(self, storage_location, videos_location, lang_code, subtitle_sync_ms, padding_ms):
        if len(storage_location.strip()) == 0:
            print('[video-to-podcast] no storage location set')
            return

        if len(videos_location.strip()) == 0:
            print('[video-to-podcast] no video location set')
            return

        for root, _, file_names in walk(videos_location):
            file_names = list(filter(lambda p: splitext(p)[1] in ['.mp4', '.mkv'], file_names))

            if len(file_names) == 0:
                continue

            for file_name in file_names:
                exit_code = convert(storage_location, join(root, file_name), lang_code, subtitle_sync_ms, padding_ms)

                if exit_code is None:
                    continue

                if exit_code == 1:
                    print(f'[video-to-podcast] already has been converted {splitext(file_name)[0]}, skipping')
                elif exit_code == 2:
                    print(f'[video-to-podcast] no track found with the id "{lang_code}" {splitext(file_name)[0]}, skipping')
                elif exit_code == 3:
                    print(f'[video-to-podcast] no subtitles were found for {splitext(file_name)[0]}, skipping')


print('[video-to-podcast] developed by true-zero (discord: Kaguya#1337)')

if platform not in ['win32', 'darwin', 'linux']:
    print('[video-to-podcast]: unsupported platform')
    input('Press enter to exit.')
    exit(0)

root = tk.Tk()
root.title('video-to-podcast')
root.geometry('495x230')
app = Application(master=root)
app.mainloop()