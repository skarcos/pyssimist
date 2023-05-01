"""\
Purpose: Visualize test scenarios
Initial Version: Costas Skarakis 12/20/2021
"""

import tkinter.tix as tix
import tkinter
import threading
import traceback
from time import ctime
from sip.SipEndpoint import SipEndpoint

MAXROWS = 40
MESSAGEENTRYWIDTH = 30


class LoadWindow:
    def __init__(self):
        self.root = tix.Tk()
        scroll_window = tix.ScrolledWindow(self.root, width=300, height=800, scrollbar=tix.AUTO)
        scroll_window.pack(expand=1, fill=tix.BOTH)
        self.window = scroll_window.window
        self.debug = tkinter.IntVar()
        self.debug_check = tkinter.Checkbutton(self.window, variable=self.debug, text="Enable Click error to debug")
        self.debug_check.grid(row=0, column=0, sticky="w")
        self.pack_legend()
        self.frames = {}
        self.subs = {}

    def pack_legend(self):
        legend = tix.Frame(self.window)
        legend.grid(row=1, column=0, stick="we")
        tix.Label(legend, text="Endpoint", width=12).pack(side=tix.LEFT)
        tix.Label(legend, text="State", width=5).pack(side=tix.LEFT)
        tix.Label(legend, text="SIP Message History", width=MESSAGEENTRYWIDTH - 1).pack(side=tix.LEFT)
        tix.Label(legend, text="Result", width=8).pack(side=tix.LEFT)

    def debug_window(self, number):
        if self.debug.get():
            frame = tkinter.Toplevel()
            frame.title(number)
            sub = self.subs[number]
            sub_frame = self.frames[number]
            message = ""
            if sub_frame.error_message.get():
                message += "========== EXCEPTION TEXT  ==========\n"
                message += sub_frame.error_message.get()
            message += "\n========== INCOMING SIP MESSAGE BUFFER  ==========\n"
            message += str(sub.message_buffer)
            message += "\n========== LAST_MESSAGES_PER_DIALOG ==========\n%s\n" % str(sub.last_messages_per_dialog)
            message += "\n========== DIALOGS ==========\n%s\n" % str(sub.dialogs)
            message += "\n========== REQUESTS ==========\n%s\n" % str(sub.requests)
            message += "\n========== ADDRESS: %s:%s==========\n" % (str(sub.ip), str(sub.port))
            text = tkinter.Text(frame)
            text.insert("end", message)
            text.pack(side="left", expand=1, fill="both")

    def paint(self, number):
        if number not in self.frames:
            count = len(self.frames) + 2
            sub_row = count % MAXROWS
            sub_col = count // MAXROWS
            frame = tix.Frame(self.window)
            frame.grid(row=sub_row, column=sub_col)
            frame.label = tix.Label(frame, text=number, width=13)
            frame.arrow = tix.Label(frame, width=3, bg="yellow")
            frame.messagevar = tkinter.StringVar()
            frame.message = tkinter.Entry(frame, width=MESSAGEENTRYWIDTH, fg="black", exportselection=True,
                                          selectforeground='blue', state="readonly",
                                          textvariable=frame.messagevar)
            frame.error = tix.Label(frame, width=8)
            frame.error_message = tkinter.StringVar()
            frame.label.pack(side=tix.LEFT)
            frame.arrow.pack(side=tix.LEFT)
            frame.message.pack(side=tix.LEFT)
            frame.error.pack(side=tix.LEFT)
            frame.error.bind('<Button-1>', lambda event, n=number: self.debug_window(n))
            self.frames[number] = frame

    def arrow(self, number, text):
        self.frames[number].arrow["text"] = text

    def message(self, number, text):
        entry_text = self.frames[number].messagevar.get()
        entry_text += text
        self.frames[number].messagevar.set(entry_text)
        self.frames[number].message.xview_moveto(1)

    def error(self, number, text, exception_text):
        self.frames[number].error["text"] = text
        self.frames[number].error_message.set("%s:\n%s\n" % (ctime(),exception_text))
        self.frames[number].error["bg"] = "tomato"

    def no_error(self, number):
        self.frames[number].error["text"] = chr(10004)
        self.frames[number].error["bg"] = "green3"

    def start(self, func_on_thread, *args, **kwargs):
        func_thread = threading.Thread(target=func_on_thread, args=args, kwargs=kwargs).start()
        self.root.mainloop()
        print("Exit main loop")
        func_thread.join()


class SipEndpointView(SipEndpoint):
    def __init__(self, view, number):
        self.view = view
        self.view.subs[number] = self
        super().__init__(number)

    def connect(self, *args, **kwargs):
        self.view.paint(self.number)
        super().connect(*args, **kwargs)

    def use_link(self, *args, **kwargs):
        self.view.paint(self.number)
        super().use_link(*args, **kwargs)

    def send(self, *args, **kwargs):
        self.view.arrow(self.number, "Sndg")
        message = super().send(*args, **kwargs)
        self.view.arrow(self.number, "Sent")
        # if "expected_response" in kwargs and kwargs["expected_response"]:
        #     label = "<-" + kwargs["expected_response"][:3]
        #     self.view.message(self.number, label)
        return message

    def reply(self, *args, **kwargs):
        self.view.arrow(self.number, "Sndg")
        message = super().reply(*args, **kwargs)
        self.view.arrow(self.number, "Sent")
        label = "->" + message.get_status_or_method()[:3]
        self.view.message(self.number, label)
        return message

    def send_new(self, *args, **kwargs):
        self.view.arrow(self.number, "Sndg")
        message = super().send_new(*args, **kwargs)
        self.view.arrow(self.number, "Sent")
        label = "+->%s(%s)" % (message.get_status_or_method()[:3], message["Call-ID"])
        self.view.message(self.number, label)
        # if "expected_response" in kwargs and kwargs["expected_response"]:
        #     label = "<-" + kwargs["expected_response"][:3]
        #     self.view.message(self.number, label)
        return message

    def wait_for_message(self, message_type, **kwargs):
        self.view.arrow(self.number, "Wng")
        self.view.message(self.number, "<-")
        error = True
        try:
            message = super().wait_for_message(message_type, **kwargs)
            error = False
            self.view.arrow(self.number, "Rcvd")
            label = message.get_status_or_method()[:3]
            self.view.message(self.number, label)
            return message
        finally:
            if error:
                self.view.error(self.number, "No %s" % message_type[:3], traceback.format_exc())
            else:
                self.view.no_error(self.number)

    def colour(self, colour):
        self.view.frames[self.number].arrow["bg"] = colour

    def update_text(self, text=""):
        self.view.message(self.number, text)

    def update_arrow(self, arrow=""):
        self.view.arrow(self.number, arrow)

    def make_busy(self, busy=True):
        super().make_busy(busy)
        self.colour(["yellow", "cyan"][busy])
        self.view.arrow(self.number, ["Idle", "Busy"][busy])
