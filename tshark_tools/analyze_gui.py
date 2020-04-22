import os
import sys
import webbrowser
import ast
from os import path

sys.path.append("..")
sys.path.append(path.join("..", ".."))
from tshark_tools.diff import analyze
from tshark_tools.lib import check_in_trace, group_continuous_network_traces
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog, messagebox
from pprint import pformat
import threading


WIDTH = 1060
HEIGHT = 700


class Application:
    """Silly GUI"""

    def __init__(self):
        root = tk.Tk()
        root.title("Trace analyzer")
        self.master = root
        self.tests = {}
        self.tests_count = 0
        self.RunThread = None
        self.height = HEIGHT
        self.width = WIDTH

        style = ttk.Style()
        style.configure("help_style.Label", font=("Consolas", 9))
        style.configure("hyperlink.Label", foreground="blue", font=("Time", 9, "underline"))

        help_frame = ttk.Frame(self.master)
        help_frame.pack(side=tk.TOP)
        help_text = ttk.Label(help_frame, style="help_style.Label", text=check_in_trace.__doc__)
        help_text.pack()

        other_frames = ttk.Frame(self.master)
        other_frames.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        self.current_filter_frame = ttk.LabelFrame(other_frames, text="Import filter", width=self.width/3.0)
        self.current_filter_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        filter_preview = tk.StringVar()
        #ttk.Label(self.current_filter_frame, textvariable=filter_preview, style="help_style.Label").pack()
        self.import_filters = tk.Text(self.current_filter_frame, width=50, height=10, font=("Consolas", 9))
        self.import_filters.pack()
        #ttk.Button(self.current_filter_frame, text="Load Current", command=lambda: filter_preview.set(pformat(self.tests))).pack()
        ttk.Button(self.current_filter_frame, text="Load Current", command=self.load_current).pack()
        self.progress_bar = ttk.Progressbar(self.current_filter_frame, mode="indeterminate")

        self.command_frame = ttk.Frame(other_frames, width=self.width/3.0)
        self.command_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.wireshark = tk.StringVar(value="sip||mgcp")
        ttk.Label(self.command_frame, text="Trace file selected:").pack()
        self.file_selected = ttk.Label(self.command_frame, text="No file selected")
        self.file_selected.pack()
        ttk.Button(self.command_frame, text="Select File", command=self.file_dialog).pack()
        doc_link = ttk.Label(self.command_frame, style="hyperlink.Label", text="Wireshark Display filter:")
        doc_link.bind("<Button-1>", lambda e: webbrowser.open_new("https://wiki.wireshark.org/DisplayFilters"))
        doc_link.pack()
        ttk.Entry(self.command_frame, textvariable=self.wireshark).pack()

        self.hide_unmatched = tk.BooleanVar(value=False)
        ttk.Radiobutton(self.command_frame, text="Hide unmatched", value=True, variable=self.hide_unmatched).pack()
        ttk.Radiobutton(self.command_frame, text="Collapse unmatched", value=False, variable=self.hide_unmatched).pack()
        self.run_button = ttk.Button(self.command_frame, text="Run", command=self.analyze_in_thread)
        self.run_button.pack(side=tk.BOTTOM)
        self.clear_button = ttk.Button(self.command_frame, text="Clear", command=self.clear_filters)
        self.clear_button.pack(side=tk.BOTTOM)

        filter_buttons_frame = ttk.Frame(self.command_frame)
        filter_buttons_frame.pack()
        ttk.Button(filter_buttons_frame, text="Add Header Filter (OR)", command=self.add_header_filter).pack(side=tk.LEFT)
        ttk.Button(filter_buttons_frame, text="Add SDP Filter (OR)", command=self.add_sdp_filter).pack(side=tk.LEFT)
        ttk.Button(filter_buttons_frame, text="Add XML Filter (OR)", command=self.add_xml_filter).pack(side=tk.LEFT)

        self.filters_frame = ttk.Frame(other_frames, width=self.width/3.0)
        self.filters_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def load_current(self):
        self.import_filters.delete(1.0, tk.END)
        self.import_filters.insert(1.0, pformat(self.tests))

    def file_dialog(self):
        self.tests["Filename"] = filedialog.askopenfilename(initialdir=os.getcwd(),
                                                            title="Select A File",
                                                            filetypes=(("wireshark files", "*.cap *.pcap *.pcapng"),
                                                                       ("json files", "*.json"),
                                                                       ("all files", "*.*")),
                                                            multiple=True)
        if isinstance(self.tests["Filename"], str) or len(self.tests["Filename"]) == 1:
            self.file_selected.configure(text=self.tests["Filename"])
        else:
            self.file_selected.configure(text="Mulitple Selection")

    def clear_filters(self):
        self.tests_count = 0
        if "Filename" in self.tests:
            self.tests = {"Filename": self.tests["Filename"]}
        else:
            self.tests = {}
        filters = self.filters_frame.children
        for child_frame in filters:
            filters[child_frame].pack_forget()

    def add_header_filter(self):
        filter_frame = ttk.LabelFrame(self.filters_frame, text="Header criteria")
        filter_frame.pack(side=tk.LEFT)
        self.tests_count += 1
        self.tests["Test_header_%d" % self.tests_count] = {}
        self.add_headers(filter_frame, self.tests_count)
        return filter_frame

    def add_sdp_filter(self):
        filter_frame = ttk.LabelFrame(self.filters_frame, text="SDP criteria")
        filter_frame.pack(side=tk.LEFT)
        self.tests_count += 1
        self.tests["Test_sdp_%d" % self.tests_count] = {}
        self.add_sdp(filter_frame, self.tests_count)
        return filter_frame

    def add_xml_filter(self):
        filter_frame = ttk.LabelFrame(self.filters_frame, text="XML criteria")
        filter_frame.pack(side=tk.LEFT)
        self.tests_count += 1
        self.tests["Test_xml_%d" % self.tests_count] = {}
        self.add_xml(filter_frame, self.tests_count)
        return filter_frame

    def add_headers(self, frame, test_id):
        entries = []

        def set_header_values(a, b, c):
            self.import_filters.delete(1.0, tk.END)
            self.tests["Test_header_%d" % test_id]["Headers"] = {}
            for header, header_text in entries:
                if header.get():
                    self.tests["Test_header_%d" % test_id]["Headers"][header.get()] = header_text.get()

        def add_header():
            header = tk.StringVar()
            header_text = tk.StringVar()
            header.trace("w", set_header_values)
            header_text.trace("w", set_header_values)
            entries.append((header, header_text))
            ttk.Label(frame, text="Header:").pack()
            ttk.Entry(frame, textvariable=header).pack()
            ttk.Label(frame, text="Contains:").pack()
            ttk.Entry(frame, textvariable=header_text).pack()

        def set_request_value(a, b, c):
            self.import_filters.delete(1.0, tk.END)
            self.tests["Test_header_%d" % test_id]["Message"] = request.get()

        request = tk.StringVar()
        request.trace("w", set_request_value)
        self.tests["Test_header_%d" % test_id]["Headers"] = {}
        ttk.Label(frame, text="Msg type(empty=any):").pack()
        ttk.Entry(frame, textvariable=request).pack()
        ttk.Button(frame, text="Add header filter (AND)", command=add_header).pack()
        add_header()

    def add_sdp(self, frame, test_id):
        entries = []

        def set_sdp_values(a, b, c):
            self.import_filters.delete(1.0, tk.END)
            self.tests["Test_sdp_%d" % test_id]["sdp"] = {}
            for header, header_text in entries:
                sdp_line = header.get()
                if sdp_line:
                    if len(sdp_line) == 1:
                        sdp_line = sdp_line + "_line"
                    self.tests["Test_sdp_%d" % test_id]["sdp"][sdp_line] = header_text.get()

        def add_sdp_():
            header = tk.StringVar()
            header_text = tk.StringVar()
            header.trace("w", set_sdp_values)
            header_text.trace("w", set_sdp_values)
            entries.append((header, header_text))
            ttk.Label(frame, text="Line(o,a,v...):").pack()
            ttk.Entry(frame, textvariable=header).pack()
            ttk.Label(frame, text="Contains:").pack()
            ttk.Entry(frame, textvariable=header_text).pack()

        def set_sdp_includes_value(a, b, c):
            self.import_filters.delete(1.0, tk.END)
            self.tests["Test_sdp_%d" % test_id]["Message"] = sdp_includes.get()

        sdp_includes = tk.StringVar()
        sdp_includes.trace("w", set_sdp_includes_value)
        self.tests["Test_sdp_%d" % test_id]["sdp"] = {}
        ttk.Label(frame, text="Msg type(empty=any):").pack()
        ttk.Entry(frame, textvariable=sdp_includes).pack()
        ttk.Button(frame, text="Add sdp filter (AND)", command=add_sdp_).pack()
        add_sdp_()

    def add_xml(self, frame, test_id):
        entries = []

        def set_xml_values(a, b, c):
            self.import_filters.delete(1.0, tk.END)
            self.tests["Test_xml_%d" % test_id]["xml"] = {}
            for tag, tag_text, attr, attr_text in entries:
                xml_tag = tag.get()
                xml_attr = attr.get()
                xml_value = ""
                if xml_tag:
                    xml_value = xml_tag + " tag"
                self.tests["Test_xml_%d" % test_id]["xml"][xml_value] = tag_text.get()
                if xml_attr:
                    attr_value = "{} {} attr".format(xml_tag, xml_attr)
                    self.tests["Test_xml_%d" % test_id]["xml"][attr_value] = attr_text.get()

        def add_xml_():
            tag = tk.StringVar()
            attr = tk.StringVar()
            tag_text = tk.StringVar()
            attr_text = tk.StringVar()
            tag.trace("w", set_xml_values)
            tag_text.trace("w", set_xml_values)
            attr.trace("w", set_xml_values)
            attr_text.trace("w", set_xml_values)
            entries.append((tag, tag_text, attr, attr_text))
            ttk.Label(frame, text="XML label").pack()
            ttk.Entry(frame, textvariable=tag).pack()
            ttk.Label(frame, text="Contains in text:").pack()
            ttk.Entry(frame, textvariable=tag_text).pack()
            ttk.Label(frame, text="Or its attribute:").pack()
            ttk.Entry(frame, textvariable=attr).pack()
            ttk.Label(frame, text="Contains in value:").pack()
            ttk.Entry(frame, textvariable=attr_text).pack()

        def set_xml_includes_value(a, b, c):
            self.import_filters.delete(1.0, tk.END)
            self.tests["Test_xml_%d" % test_id]["Message"] = xml_includes.get()

        xml_includes = tk.StringVar()
        xml_includes.trace("w", set_xml_includes_value)
        self.tests["Test_xml_%d" % test_id]["xml"] = {}
        ttk.Label(frame, text="Msg type(empty=any):").pack()
        ttk.Entry(frame, textvariable=xml_includes).pack()
        ttk.Button(frame, text="Add xml filter (AND)", command=add_xml_).pack()
        add_xml_()

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
        tests = self.tests
        imported_tests = self.import_filters.get(1.0, tk.END).strip()
        if imported_tests:
            tests = ast.literal_eval(imported_tests)
        filters = [tests[test] for test in tests if test.startswith("Test")]
        if isinstance(self.tests["Filename"], str):
            file_generated = analyze(self.tests["Filename"], *filters, hide_unmatched=self.hide_unmatched.get(),
                                     wireshark_filter=self.wireshark.get())
            messagebox.showinfo(title="Trace analyzed", message="Output filename: %s" % file_generated)
        else:
            file_groups = group_continuous_network_traces(self.tests["Filename"])
            files_generated = ""
            for group in file_groups:
                files_generated += analyze(file_groups[group], *filters, hide_unmatched=self.hide_unmatched.get(),
                                           wireshark_filter=self.wireshark.get()) + "\n"
            messagebox.showinfo(title="Trace analyzed", message="Output filenames: %s" % files_generated)


if __name__ == "__main__":
    Application().start()
