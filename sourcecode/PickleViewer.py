print("Loading Modules...")
import pickle
import os.path
import pprint
import ast
import sys
import threading
import uuid
import urllib.request
import configparser
import hashlib
import subprocess
import ctypes
import json
import time
import tkinter as tk
from tkinter import *
from tkinter import messagebox, filedialog, font, ttk
from TkSStausBar import StatusBar
from pygments.lexers.python import PythonLexer
from pygments.styles import get_style_by_name

# Checking if wait mode
wait_mode = False
update_mode = False
if "--wait" in sys.argv:
    wait_mode = True
    print("Wait mode enabled")

if "--update" in sys.argv:
    update_mode = True
    print("Update mode enabled")

# Initial sys Frozen
frozen = 'not'
bol_frozen = False
if getattr(sys, 'frozen', False):
    # we are running in a bundle
    frozen = 'bundle'
    bol_frozen = True
    bundle_dir = None
    try:
        bundle_dir = sys._MEIPASS
        print('bundle dir is', bundle_dir)
    except BaseException as e:
        print("Error while getting bundle dir!", e)
        messagebox.showerror("Bundle Error", "Error while getting bundle dir! " + str(e))
    # print('sys.argv[0] is', sys.argv[0])
    # print('sys.argv[1] is', sys.argv[1])
    input("Press enter to continue...") if wait_mode else False
else:
    # we are running in a normal Python environment
    bundle_dir = os.path.dirname(os.path.abspath(__file__))
print('PickleViewer v0.7.6 is', frozen, 'frozen')

# Hide Console
kernel32 = ctypes.WinDLL('kernel32')
user32 = ctypes.WinDLL('user32')

SW_HIDE = 0
SW_SHOW = 0

hWnd = kernel32.GetConsoleWindow()
if hWnd:
    user32.ShowWindow(hWnd, SW_HIDE) if not wait_mode else False

# Loading settings
print("Loading settings")
conf_path = os.path.join(os.path.dirname(sys.argv[0]), "config.ini")
# Creating config file, if not exists
if not os.path.isfile(conf_path):
    print("Settings file does not exists. Creating...")
    tmp_conf_file = open(conf_path, "w")
    tmp_conf_file.write("[WINDOW]\ngeometry = 981x407+182+182\nstate = normal")
    tmp_conf_file.close()

# Generating fallback
local_config = configparser.ConfigParser()
local_config["WINDOW"] = {"geometry": "981x407+182+182", "state": "normal"}

# loading config file
try:
    local_config.read(conf_path)
except configparser.Error as ex:
    print("Error while reading config-file:", ex)

# TODO: Software Info's
software_name = "PickleViewer v0.7.7"
software_version = "0.77"
software_version_string = "0.7.7-beta.5"
software_title = software_name + " (" + software_version_string + ")"

# Global Variables
data = {}

pp = pprint.PrettyPrinter(indent=2)
editing = True
open_filename = ""
open_filetitle = "*untitled*"
file_loaded = False
file_changed = False

rf_running = False
rf_allDone = False
rf_threads = 0
tv_threads = 0

last_text = ""


# Functions
def getSHA(filename):
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


def checkForUpdates():
    print("Checking for updates...")
    req_data = urllib.request.urlopen(
        "https://raw.githubusercontent.com/Matix-Media/PickleViewer/master/versions/info.ini").read()
    body = req_data.decode("utf-8")
    config = configparser.ConfigParser()
    config.read_string(body)
    try:
        recent_version = config["RECENT"]["version"]
        recent_installer_path = config["RECENT"]["installer_path"]
        recent_version_info = urllib.request.urlopen(config["RECENT"]["version_info"]).read().decode("utf-8")
        recent_installer_sha = config["RECENT"]["sha256"]
        if float(recent_version) > float(software_version) or update_mode:
            print("Version outdated! Ask for download")
            question_result = messagebox.askquestion("Update",
                                                     "Your " + software_name + \
                                                     " version is outdated. Would you like to download version " + \
                                                     config["RECENT"]["version_string"] + " of " + \
                                                     software_name + "?\n\nFeatures:\n" + \
                                                     recent_version_info)
            print("Download installer?", question_result)
            if question_result == "yes":
                appdata = os.getenv("APPDATA")
                save_path = os.path.join(appdata, "PickleViewer v0.7.6", "installer",
                                         os.path.basename(recent_installer_path))
                print("Downloading setup to \"", save_path, "\"...", sep="")
                SB.set("Downloading \"" + os.path.basename(recent_installer_path) + "\"...")
                if not os.path.isdir(os.path.dirname(save_path)):
                    print("Path \"", os.path.dirname(save_path), "\" does not exists, creating...", sep="")
                    os.makedirs(os.path.dirname(save_path))
                urllib.request.urlretrieve(recent_installer_path, save_path)
                SB.set("Downloaded \"" + os.path.basename(recent_installer_path) + "\"")
                print("Download done. Checking SHA256...")
                if getSHA(save_path) == recent_installer_sha:
                    print("SHA256 successfully verified! Starting installer...")
                    subprocess.Popen(r'explorer /run,"' + save_path + '"')
                else:
                    print("! Warning: SHA256 of installer could not be verified!")
                    messagebox.showwarning("Update", "Warning: SHA256 of installer could not be verified!")
                    if messagebox.askokcancel("Update", "Run installer of own risk without SHA256 verification?"):
                        print("Starting installer...")
                        subprocess.Popen(r'explorer /run,"' + save_path + '"')

        elif float(recent_version) == float(software_version):
            print("You are using the latest version of", software_name)
        elif float(recent_version) < float(software_version):
            print("Wow, you are using a version, that can't be even downloaded right now!")
            messagebox.showinfo("Update", "Wow, you are using a version of " + software_name + \
                                ", that can't be even downloaded right now!")
    except configparser.Error as ex:
        print("Can not read Online Version info's:", ex)


def askForOverwrite():
    if messagebox.askokcancel("Open file - warning",
                              "The file current open was not saved! Do you want to overwrite it?", ):
        print("Overwriting!")
        return True
    else:
        return False


def load_file(filename):
    global open_filename
    global file_loaded
    global open_filetitle
    global editing
    global file_changed
    global rf_allDone
    global last_text

    print("Selected Path:", filename)
    if filename == "":
        print("Opening canceled!")
        SB.set("opening canceled!")
        return

    if file_changed:
        if not askForOverwrite():
            return

    if os.path.isfile(filename):
        print("Reading file \"", os.path.basename(filename), "\"...", sep="")
        try:
            data = pickle.load(open(filename, "rb"))
            print("Data:")
            format_data = pp.pformat(data)
            print(format_data)
            print("End.")
            T.config(state=NORMAL)
            T.delete("1.0", END)
            T.insert("1.0", format_data)
            last_text = format_data
            T.config(state=DISABLED)

            file_loaded = True
            open_filename = filename
            open_filetitle = os.path.basename(filename)
            editing = False
            root.title(software_title + " - " + open_filetitle)
            filemenu.entryconfig("Edit current Pickle file", state=NORMAL)
            print("re-colorizing...")
            rf_allDone = False
            refreshManager()
            SB.set("Loaded Pickle file \"" + open_filetitle + "\"")

        except BaseException as e:
            print("Error while reading Data:\n", e)
            error = "Error while reading Data:\n" + str(e)
            messagebox.showerror("Error", error)
            file_loaded = False

    else:
        print("Error: The Path \"", filename, "\" is not valid.", sep="")
        error = "Error: The Path \"" + filename + "\" is not valid."
        messagebox.showerror("Error", error)
        file_loaded = False


def save_to_file(event=None):
    global open_filename
    global file_loaded
    global open_filetitle
    global editing
    global file_changed
    print("Starting saving.")
    print("Checking if file is from filesystem.")
    data_to_write = None
    opened_file = None
    try:
        data_to_write = ast.literal_eval(T.get("1.0", END))
    except BaseException as e:
        error_msg = "Error while reading data: " + str(e)
        print(error_msg)
        messagebox.showerror("Error", error_msg)
        return

    try:
        if not file_loaded or not os.path.isfile(open_filename):
            tmp_file = filedialog.asksaveasfile(mode="wb", defaultextension=".pkl")
            if tmp_file is None:
                print("Saving canceled!")
                SB.set("Saving canceled!")
                return
            else:
                opened_file = tmp_file
        else:
            opened_file = open(open_filename, "wb")
        pickle.dump(data_to_write, opened_file)
        open_filename = opened_file.name
        file_loaded = True
        open_filetitle = os.path.basename(open_filename)
        if editing:
            root.title(software_title + " - " + open_filetitle + " [Edit]")
        else:
            root.title(software_title + " - " + open_filetitle)
        file_changed = False
        SB.set("Saved Pickle file \"" + open_filetitle + "\"")
        print("Saving Done.")
    except BaseException as e:
        error_msg = "Error while saving file: " + str(e)
        print(error_msg)
        messagebox.showerror("Error", error_msg)
        return


def SaveSettings():
    print("Saving settings.")
    if str(root.state()) == "normal":
        local_config["WINDOW"]["geometry"] = str(root.winfo_geometry())
    local_config["WINDOW"]["state"] = str(root.state())
    try:
        with open(conf_path, "w") as conf_file:
            local_config.write(conf_file)
    except BaseException as ex_save:
        print("Error while saving settings:", ex_save)
        messagebox.showerror("Error while saving settings", "Error while saving settings: " + str(ex_save))


def create_tags():
    bold_font = font.Font(T, T.cget("font"))
    bold_font.configure(weight=font.BOLD)

    italic_font = font.Font(T, T.cget("font"))
    italic_font.configure(slant=font.ITALIC)

    bold_italic_font = font.Font(T, T.cget("font"))
    bold_italic_font.configure(weight=font.BOLD, slant=font.ITALIC)

    style = get_style_by_name('default')
    for ttype, ndef in style:
        # print(ttype, ndef)
        tag_font = None
        if ndef['bold'] and ndef['italic']:
            tag_font = bold_italic_font
        elif ndef['bold']:
            tag_font = bold_font
        elif ndef['italic']:
            tag_font = italic_font

        if ndef['color']:
            foreground = "#%s" % ndef['color']
        else:
            foreground = None

        T.tag_configure(str(ttype), foreground=foreground, font=tag_font)


def removecolors():
    for tag in root.tagdefs:
        T.tag_remove(tag, "1.0", "end")


def recolorize():
    code = T.get("1.0", "end-1c")
    tokensource = PythonLexer().get_tokens(code)

    start_line = 1
    start_index = 0
    end_line = 1
    end_index = 0
    for ttype, value in tokensource:
        if "\n" in value:
            end_line += value.count("\n")
            end_index = len(value.rsplit("\n", 1)[1])
        else:
            end_index += len(value)

        if value not in (" ", "\n"):
            index1 = "%s.%s" % (start_line, start_index)
            index2 = "%s.%s" % (end_line, end_index)

            for tagname in T.tag_names(index1):
                T.tag_remove(tagname, index1, index2)

            # print(ttype, repr(value), index1, index2)
            T.tag_add(str(ttype), index1, index2)

        start_line = end_line
        start_index = end_index


def json_tree(tree, parent, dictionary):
    num = 0
    for key in dictionary:
        uid = uuid.uuid4()
        if isinstance(key, dict):
            uid2 = uuid.uuid4()
            tree.insert(parent, 'end', uid, text=num, value="[...]",
                        tag=(uid, True, str(key), uid2, False))

            tree.insert(uid, END, text="[...] Loading...", iid=uid2, tag=(uid2, False))

            # tree.insert(parent, 'end', uid, text=key)
            # json_tree(tree, uid, key)
        elif isinstance(dictionary[key], list):
            uid2 = uuid.uuid4()
            tree.insert(parent, 'end', uid, text=key + ' [...]', value="[...]",
                        tag=(uid, True, str(dictionary[key]), uid2, False))

            tree.insert(uid, END, text="[...] Loading...", iid=uid2, tag=(uid2, False))
            # try:
            #    time.sleep(0.5)
            #    json_tree(tree,
            #              uid,
            #              dict([(i, x) for i, x in enumerate(dictionary[key])]))
            # except TypeError as ex:
            #    print("TreeView loading: Error while reading info's:", ex)

        else:
            value = dictionary[key]
            if value is None:
                value = 'None'
            tree.insert(parent, 'end', uid, text=key, value=value, tag=(uid, False))
        num += 1


def loadTreeview():
    global tv_threads

    TR.delete(*TR.get_children())
    inner_data = {}
    try:
        inner_data = ast.literal_eval(T.get("1.0", END))
    except BaseException as e:
        error_msg = "TreeView loading: Error while reading data: " + str(e)
        print(error_msg)
        TR.insert('', 0, text="Can't load DataTree")
        tv_threads -= 1
        print("Treeview threads =", tv_threads)
        return

    def myprint(d, parent):
        for k, v in d.items():
            if isinstance(v, dict):
                myprint(v, parent)
            else:
                to_collapse = TR.insert(parent, 'end', text=v)
                TR.item(to_collapse, open=True)
                # print("{0} : {1}".format(k, v))

    # tr_parent = TR.insert('', 'end', text='PickleFile')
    # TR.item(tr_parent, open=True)
    # myprint(inner_data, tr_parent)
    # TR.insert("", END, inner_data)
    try:
        json_tree(TR, '', inner_data)

    except TypeError as ex:
        print("TreeView loading: Error while getting info's:", ex)
    tv_threads -= 1


def refreshManager():
    global rf_running
    global rf_allDone
    global rf_threads
    global tv_threads

    rf_threads += 1

    if not rf_running and not rf_allDone:
        # print("Running refresh")
        rf_running = True
        recolorize()
        if tv_threads < 1:
            tv_threads += 1
            # print("Starting Treeview thread")
            tree_thread = threading.Thread(target=loadTreeview)
            tree_thread.start()
        else:
            # print("Treeview thread already running")
            pass
        rf_running = False
        rf_allDone = True
    else:
        if rf_running:
            # print("Refresh already running!")
            pass
        elif rf_allDone:
            # print("All refreshes already done.")
            pass

    rf_threads -= 1


# Textbox events
def event_key(event):
    global rf_allDone
    global file_loaded
    global file_changed
    global editing
    global rf_running
    global rf_threads
    global last_text

    current_text = T.get("1.0", END)

    if file_loaded and editing and last_text != current_text:
        file_changed = True
        root.title(software_title + " - *" + open_filetitle + " [Edit]")
    rf_allDone = False
    if editing and not rf_running and rf_threads < 2 and last_text != current_text:
        last_text = current_text
        th = threading.Thread(target=refreshManager)
        th.start()
    else:
        # print("RefreshManager Thread stack full.")
        pass


def event_tab(event=None):
    T.insert(tk.INSERT, " " * 2)
    return 'break'


# TreeView Events
def selectItem(event=None):
    if not TR.focus():
        print("No item selected!")
        return
    curItem = TR.focus()
    # print(TR.item(curItem))
    itemInfo = TR.item(curItem)
    if itemInfo["tags"][1] == "True":
        print("Selected TreeView item:", itemInfo["tags"][0], ", Item has subItems:", True, ", Placeholder-Child-IID:",
              itemInfo["tags"][3])
        if TR.exists(itemInfo["tags"][3]):
            TR.delete(itemInfo["tags"][3])
        if itemInfo["tags"][4] == "True":
            print("Dict already generated.")
            return
        print("Getting item dict...")
        item_dict = ["Error while generating Dict"]
        try:
            item_dict = ast.literal_eval(itemInfo["tags"][2])
        except BaseException as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print("Error while generating subItems:", ex, ", Line", exc_tb.tb_lineno)
            messagebox.showerror("Error while generating subItems", "Error while generating subItems: " + str(ex) + \
                                 ", Line " + str(exc_tb.tb_lineno))
            return

        json_tree(TR, curItem, item_dict)
        itemInfo["tags"][4] = "True"
        t1 = itemInfo["tags"][0]
        TR.item(curItem,
                tag=(itemInfo["tags"][0], itemInfo["tags"][1], itemInfo["tags"][2], itemInfo["tags"][3], "True"))
    else:
        print("Selected TreeView item:", itemInfo["tags"][0], ", Item has subItems:", False)


# Window events
def menQuit(event=None):
    print("Inventing quitting...")
    if file_changed:
        if messagebox.askokcancel("Quit",
                                  "The current file was not saved! If you quit, the changes will be lost! Do you really want to quit?"):
            print("Lost changes")
            print("Quitting!")
            root.quit()
        else:
            print("Quitting canceled!")
    else:
        SaveSettings()
        print("Quitting!")
        root.quit()


# Defining main window
root = tk.Tk()
root.title(software_title + " - " + open_filetitle + " [Edit]")
try:
    root.iconbitmap(os.path.join(os.path.dirname(sys.argv[0]), "icon.ico"))
except BaseException as e:
    print("Can not load PicklePreview Icon! " + str(e))
    messagebox.showwarning("Load Error", "Can not load PicklePreview Icon! " + str(e))
    input("Press enter to continue...") if wait_mode else False
root.protocol("WM_DELETE_WINDOW", menQuit)
print("Set window geometry to:", local_config["WINDOW"]["geometry"])
root.geometry(local_config["WINDOW"]["geometry"])
print("Set window state:", local_config["WINDOW"]["state"])
root.state(local_config["WINDOW"]["state"])
SB = StatusBar(root)
SB.set("no recent Actions")
SB.pack(side=BOTTOM, fill=X)
# PW = PanedWindow(orient=HORIZONTAL)
# PW.pack(fill=BOTH, expand=1)

S = tk.Scrollbar(root)
T = tk.Text(root)
# PW.add(T)
T.pack(side=tk.LEFT, fill=tk.BOTH, anchor=tk.N, expand=True)
# PW.add(S)
S.pack(side=tk.LEFT, fill=tk.Y)
S.config(command=T.yview)
T.config(yscrollcommand=S.set)
T.bind("<Key>", event_key)
T.bind("<Tab>", event_tab)

TR = ttk.Treeview(root, columns="Value")
TR.column("Value", width=100, anchor="center")
TR.heading("Value", text="Value")
TR_S = ttk.Scrollbar(root, orient="vertical", command=TR.yview)
TR_S.pack(side=RIGHT, fill=Y)
# PW.add(TR)
# PW.add(TR_S)
TR.pack(side=RIGHT, fill=Y)
TR.config(yscrollcommand=TR_S.set, selectmode=BROWSE)
TR.bind('<ButtonRelease-1>', selectItem)


# Menubar Actions
def menAbout(event=None):
    messagebox.showinfo("About", software_name + """\n\nVersion: """ + software_version_string + """\nCreator: Max Heilmann\nCompany: Matix Media, Inc.
    \nCopyright: [c] 2019\n\nThis is a open source Project under the Public MIT (X11-License) license.
    \n\nFor more info's, visit \nhttps://www.matix-media.de""")


def menEdit(event=None):
    global editing
    global last_text

    if not editing:
        last_text = T.get("1.0", END)
        root.title(software_title + " - " + open_filetitle + " [Edit]")
        T.config(state=tk.NORMAL)
        editing = True
        filemenu.entryconfig("Edit current Pickle file", state=tk.DISABLED)
        SB.set("Enabled editing for current Pickle file")


def menOpen(event=None):
    filename = filedialog.askopenfilename(title="Select Pickle file", filetypes=(("all files", "*.*"),))
    load_file(filename)


def menHelp(event=None):
    messagebox.showinfo("Help", """HELP
    \n\nSave current Pickle file...: With the save function you can save your opened Pickle file
    \nOpen Pickle file...: With the open function you can open Pickle files
    \nEdit current Pickle file: With the edit function you can edit the open Pickle file
    \nNew Pickle file: With the new file function you create a new Pickle file. When creating, the previous file is overwritten
    \nExit: With the exit button you can end the program
    \n\nI hope I could help!""")


def menNew(event=None):
    global editing
    global open_filetitle
    global open_filename
    global file_loaded
    global rf_allDone
    print("Entering new file Creation.")
    if messagebox.askyesno("New Pickle file",
                           "Do you want to create a new file? It will overwrite the current open file."):
        print("Creating new file.")
        editing = True
        open_filetitle = "*untitled*"
        open_filename = ""
        file_loaded = False
        T.config(state=NORMAL)
        T.delete("1.0", END)
        filemenu.entryconfig("Edit current Pickle file", state=tk.DISABLED)
        root.title(software_title + " - " + open_filetitle + " [Edit]")
        SB.set("Created new Pickle file")
        rf_allDone = False
        refreshManager()


def donothing():
    print("No define action.")


# Menubar generating
menubar = tk.Menu(root)
filemenu = tk.Menu(menubar, tearoff=0)
filemenu.add_command(label="New Pickle file", command=menNew, accelerator="Ctrl+N")
filemenu.add_command(label="Open Pickle file...", command=menOpen, accelerator="Ctrl+O")
filemenu.add_command(label="Save current Pickle file...", command=save_to_file, accelerator="Ctrl+S")
filemenu.add_command(label="Edit current Pickle file", command=menEdit, state=DISABLED, accelerator="Ctrl+E")
filemenu.add_separator()
filemenu.add_command(label="Exit", command=menQuit, accelerator="Ctrl+Q")
menubar.add_cascade(label="File", menu=filemenu)

helpmenu = Menu(menubar, tearoff=0)
helpmenu.add_command(label="Help", command=menHelp)
helpmenu.add_command(label="About...", command=menAbout, accelerator="F1")
menubar.add_cascade(label="Help", menu=helpmenu)

root.config(menu=menubar)

# Adding Shortcuts
root.bind("<Control-KeyPress-s>", save_to_file)
root.bind("<Control-KeyPress-Insert>", menNew)
root.bind("<Control-KeyPress-o>", menOpen)
root.bind("<Control-KeyPress-e>", menEdit)
root.bind("<Control-KeyPress-n>", menNew)
root.bind("<F1>", menHelp)

root.bind("<Control-KeyPress-q>", menQuit)
print("Creating color-tags...")
create_tags()
print("Testing coloring...")
recolorize()

# Main Checking process
file_to_open_start = ""
try:
    print("Path to icon file:", os.path.join(os.path.dirname(os.path.realpath(__file__)), "icon.ico"))
    print("Script Path:", os.path.realpath(__file__))
    print("Startup Arguments:", sys.argv)
    if len(sys.argv) > 1:  #
        if not sys.argv[1][:2] == "--":
            file_to_open_start = sys.argv[1]
        else:
            print("Parameter was special:", sys.argv[1][:2])
    else:
        print("No opened file by startup")
except BaseException as e:
    print("Error while starting! Check startup parameters. " + str(e))
    messagebox.showerror("Startup Error", "Error while starting! Check startup parameters. " + str(e))
    input("Press enter to continue...") if wait_mode else False

if not file_to_open_start == "":
    load_file(file_to_open_start)

# print("Window geometry:", root.geometry())

# Check for Updates
update_thread = threading.Thread(target=checkForUpdates)
update_thread.start()

# Main Loop
tk.mainloop()

if hWnd:
    user32.ShowWindow(hWnd, SW_SHOW) if not wait_mode else False
