import os
import sys
from os import path

sys.path.append("..")
sys.path.append(path.join("..", ".."))
from tshark_tools.diff import analyze
from tshark_tools.lib import check_in_trace
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog, messagebox
from pprint import pformat
import threading


class Application:
    """Silly GUI"""

    def __init__(self):
        root = tk.Tk()
        root.title("Trace analyzer")
        self.master = root
        self.tests = {}
        self.tests_count = 0
        self.RunThread = None

        style = ttk.Style()
        style.configure("help_style.Label", font=("Consolas", 9))

        help_frame = ttk.Frame(self.master)
        help_frame.pack(side=tk.TOP)
        help_text = ttk.Label(help_frame, style="help_style.Label", text=check_in_trace.__doc__)
        help_text.pack()

        other_frames = ttk.Frame(self.master)
        other_frames.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        self.current_filter_frame = ttk.LabelFrame(other_frames, text="Current filter")
        self.current_filter_frame.pack(side=tk.LEFT, fill=tk.X)
        filter_preview = tk.StringVar()
        ttk.Label(self.current_filter_frame, textvariable=filter_preview, style="help_style.Label").pack()
        ttk.Button(self.current_filter_frame, text="Preview", command=lambda: filter_preview.set(pformat(self.tests))).pack()
        self.progress_bar = ttk.Progressbar(self.current_filter_frame, mode="indeterminate")

        self.command_frame = ttk.Frame(other_frames)
        self.command_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.wireshark = tk.StringVar(value="")
        ttk.Label(self.command_frame, text="Trace file selected:").pack()
        self.file_selected = ttk.Label(self.command_frame, text="No file selected")
        self.file_selected.pack()
        ttk.Button(self.command_frame, text="Select File", command=self.file_dialog).pack()
        ttk.Label(self.command_frame, text="Wireshark filter").pack()
        ttk.Entry(self.command_frame, textvariable=self.wireshark).pack()
        self.run_button = ttk.Button(self.command_frame, text="Run", command=self.analyze_in_thread)
        self.run_button.pack(side=tk.BOTTOM)

        filter_buttons_frame = ttk.Frame(self.command_frame)
        filter_buttons_frame.pack()
        ttk.Button(filter_buttons_frame, text="Add Header Filter", command=self.add_header_filter).pack(side=tk.LEFT)
        ttk.Button(filter_buttons_frame, text="Add SDP Filter", command=self.add_sdp_filter).pack(side=tk.LEFT)
        ttk.Button(filter_buttons_frame, text="Add XML Filter", command=self.add_xml_filter).pack(side=tk.LEFT)

        self.filters_frame = ttk.Frame(other_frames)
        self.filters_frame.pack(side=tk.LEFT)

    def file_dialog(self):
        self.tests["Filename"] = filedialog.askopenfilename(initialdir=os.getcwd(),
                                                            title="Select A File",
                                                            filetype=(("wireshark files", "*.cap *.pcap *.pcapng"),
                                                                      ("json files", "*.json"),
                                                                      ("all files", "*.*")))
        self.file_selected.configure(text=self.tests["Filename"])

    def add_header_filter(self):
        filter_frame = ttk.LabelFrame(self.filters_frame, text="Header criteria")
        filter_frame.pack()
        self.tests_count += 1
        self.tests["Test%d" % self.tests_count] = {}
        self.add_headers(filter_frame)
        return filter_frame

    def add_sdp_filter(self):
        filter_frame = ttk.LabelFrame(self.filters_frame, text="SDP criteria")
        filter_frame.pack()
        self.tests_count += 1
        self.tests["Test%d" % self.tests_count] = {}
        self.add_sdp(filter_frame)
        return filter_frame

    def add_xml_filter(self):
        filter_frame = ttk.LabelFrame(self.filters_frame, text="XML criteria")
        filter_frame.pack()
        self.tests_count += 1
        self.tests["Test%d" % self.tests_count] = {}
        self.add_xml(filter_frame)
        return filter_frame

    def add_headers(self, frame):
        def add_header():
            def set_header_values(a, b, c):
                if header.get():
                    self.tests["Test%d" % self.tests_count]["Headers"][header.get()] = header_text.get()

            header = tk.StringVar()
            header_text = tk.StringVar()
            header_text.trace("w", set_header_values)
            ttk.Label(frame, text="Header:").pack()
            ttk.Entry(frame, textvariable=header).pack()
            ttk.Label(frame, text="Contains:").pack()
            ttk.Entry(frame, textvariable=header_text).pack()

        def set_request_value(a, b, c):
            self.tests["Test%d" % self.tests_count]["Message"] = request.get()

        request = tk.StringVar()
        request.trace("w", set_request_value)
        self.tests["Test%d" % self.tests_count]["Headers"] = {}
        ttk.Label(frame, text="Message of type:").pack()
        ttk.Entry(frame, textvariable=request).pack()
        ttk.Button(frame, text="Add header filter", command=add_header).pack()

    def add_sdp(self, frame):
        sdp_includes = tk.StringVar()

    def add_xml(self, frame):
        xml_includes = tk.StringVar()

    def start(self):
        self.master.mainloop()

    def analyze_in_thread(self):
        self.run_button["state"] = tk.DISABLED
        self.RunThread = threading.Thread(target=self.analyze)
        self.RunThread.start()
        self.progress_bar.pack(fill=tk.X, expand=True)
        self.progress_bar.start(interval=10)
        self.master.after(1000, self.check_done)

    def check_done(self):
        if self.RunThread.is_alive():
            self.master.after(1000, self.check_done)
        else:
            self.RunThread.join()
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.run_button["state"] = tk.NORMAL
            self.master.update()

    def analyze(self):
        filters = [self.tests[test] for test in self.tests if test.startswith("Test")]
        file_generated = analyze(self.tests["Filename"], *filters, wireshark_filter=self.wireshark.get())
        messagebox.showinfo(title="Trace analyzed", message="Output filename: %s" % file_generated)


if __name__ == "__main__":
    Application().start()
