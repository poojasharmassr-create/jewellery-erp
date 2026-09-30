from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.graphics import Color, Rectangle
from kivy.utils import platform
import sqlite3, os
from datetime import datetime

DB = "jewellery.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS bills (id INTEGER PRIMARY KEY AUTOINCREMENT, bill_no INTEGER, date TEXT, party TEXT, mobile TEXT, bhaw REAL, old_balance REAL, item_weight REAL, item_fine REAL, jama_weight REAL, jama_fine REAL, cash_amount REAL, cash_fine REAL, net_total REAL, uptodate REAL, bhawkata_amount REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, bill_id INTEGER, section TEXT, name TEXT, weight REAL, touch REAL, fine REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS parties (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, mobile TEXT, last_balance REAL DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()

def gs(k, d=""):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (k,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else d

def ss(k, v):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (k, v))
    conn.commit()
    conn.close()

def next_bn():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT MAX(bill_no) FROM bills")
    r = c.fetchone()
    conn.close()
    return (r[0] or 0) + 1

def old_bal(party):
    if not party: return 0.0
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT uptodate FROM bills WHERE party=? ORDER BY id DESC LIMIT 1", (party,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else 0.0

def get_mob(party):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT mobile FROM parties WHERE name=?", (party,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else ""

def pdf_path():
    p = gs("pdf_path", "").strip()
    if p:
        try:
            if not os.path.exists(p): os.makedirs(p)
        except: pass
        return p
    if platform == "android":
        try:
            from android.storage import primary_external_storage_path
            return primary_external_storage_path() + "/Download"
        except: return "/sdcard/Download"
    return os.path.expanduser("~/Desktop")

def make_pdf(bn, dt, party, mob, bh, ob, items, jama, cash, cf, nt, up, am):
    try:
        from fpdf import FPDF
    except: return None
    try:
        iw = sum(i[1] for i in items)
        iff = sum(i[3] for i in items)
        jw = sum(j[1] for j in jama)
        jf = sum(j[3] for j in jama)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Courier", size=10)
        def L(t=""):
            pdf.cell(0, 5, t); pdf.ln(5)
        L("=" * 76)
        L("PYARE LAL KEEL MAKERS".center(76))
        L("Sadat, Ghazipur".center(76))
        L("=" * 76)
        L("Bill No: " + str(bn) + "     Date: " + str(dt))
        L("Party  : " + str(party))
        L("Mobile : " + str(mob or ""))
        L("-" * 76)
        L("ITEM SECTION")
        L(f"{'Item':<28}{'Weight':>12}{'Touch':>12}{'Fine':>12}")
        L("-" * 76)
        for it in items:
            L(f"{str(it[0]):<28}{it[1]:>12.3f}{it[2]:>12.2f}{it[3]:>12.3f}")
        L("-" * 76)
        L(f"{'ITEM TOTAL':<28}{iw:>12.3f}{'':>12}{iff:>12.3f}")
        L("")
        L("JAMA SECTION")
        L(f"{'Item':<28}{'Weight':>12}{'Touch':>12}{'Fine':>12}")
        L("-" * 76)
        for it in jama:
            L(f"{str(it[0]):<28}{it[1]:>12.3f}{it[2]:>12.2f}{it[3]:>12.3f}")
        L("-" * 76)
        L(f"{'JAMA TOTAL':<28}{jw:>12.3f}{'':>12}{jf:>12.3f}")
        L("=" * 76)
        L(f"Old Balance       : {ob:.3f}")
        L(f"Net Total         : {nt:.3f}")
        L(f"Metal Jama Fine   : {jf:.3f}")
        if cash > 0:
            L(f"Cash Jama         : Rs {cash:,.2f}")
            L(f"Cash Jama Fine    : {cf:.3f}")
        L(f"Total Jama Fine   : {jf + cf:.3f}")
        L(f"Bill Uptodate     : {up:.3f}")
        L(f"Bhawkata          : {bh:.0f} / 10 gm")
        L(f"Bhawkata Amount   : Rs. {am:,.2f}")
        L(f"Final Balance     : {up:.3f}")
        L("=" * 76)
        L("DHANYAVAAD!".center(76))
        L("=" * 76)
        dl = pdf_path()
        if not os.path.exists(dl):
            try: os.makedirs(dl)
            except: pass
        fn = dl + "/Bill_" + str(bn) + "_" + str(party).replace(" ", "_") + ".pdf"
        pdf.output(fn)
        return fn
    except: return None

class BillScreen(BoxLayout):
    def __init__(self, app_ref, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.app_ref = app_ref
        self.items = []
        self.jama = []
        self.cash_amount = 0.0
        sv = ScrollView(size_hint=(1, 1))
        main = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=dp(8))
        main.bind(minimum_height=main.setter("height"))
        sv.add_widget(main)
        h = BoxLayout(size_hint_y=None, height=dp(50), padding=[dp(10), dp(8)])
        with h.canvas.before:
            Color(0.17, 0.24, 0.31, 1)
            self.rect = Rectangle(pos=h.pos, size=h.size)
        h.bind(pos=lambda o, v: setattr(self.rect, 'pos', v), size=lambda o, v: setattr(self.rect, 'size', v))
        h.add_widget(Label(text="[b]PYARE LAL KEEL MAKERS[/b]", markup=True, font_size=sp(18), color=(1,1,1,1)))
        main.add_widget(h)
        main.add_widget(Label(text="Bill No:", size_hint_y=None, height=dp(25), font_size=sp(15), halign="left", valign="middle", text_size=(Window.width-dp(20), None)))
        self.bno = TextInput(text=str(next_bn()), multiline=False, size_hint_y=None, height=dp(45), font_size=sp(16), padding=[dp(10), dp(10)])
        main.add_widget(self.bno)
        main.add_widget(Label(text="Party Name:", size_hint_y=None, height=dp(25), font_size=sp(15), halign="left", valign="middle", text_size=(Window.width-dp(20), None)))
        self.party = TextInput(multiline=False, size_hint_y=None, height=dp(45), font_size=sp(16), padding=[dp(10), dp(10)], hint_text="Customer ka naam")
        self.party.bind(text=self.on_party)
        main.add_widget(self.party)
        main.add_widget(Label(text="Mobile:", size_hint_y=None, height=dp(25), font_size=sp(15), halign="left", valign="middle", text_size=(Window.width-dp(20), None)))
        self.mobile = TextInput(multiline=False, size_hint_y=None, height=dp(45), font_size=sp(16), padding=[dp(10), dp(10)], input_filter="int", hint_text="Auto aayega")
        main.add_widget(self.mobile)
        main.add_widget(Label(text="Bhaw (Rs/10gm):", size_hint_y=None, height=dp(25), font_size=sp(15), halign="left", valign="middle", text_size=(Window.width-dp(20), None)))
        self.bhaw = TextInput(multiline=False, size_hint_y=None, height=dp(45), font_size=sp(16), padding=[dp(10), dp(10)], input_filter="float", hint_text="80600")
        main.add_widget(self.bhaw)
        row = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(6))
        row.add_widget(Button(text="+ ITEM", on_press=lambda x: self.add_d("ITEM"), background_color=(0.2,0.7,0.4,1), font_size=sp(16), bold=True))
        row.add_widget(Button(text="+ JAMA", on_press=lambda x: self.add_d("JAMA"), background_color=(0.6,0.3,0.7,1), font_size=sp(16), bold=True))
        row.add_widget(Button(text="CASH", on_press=self.cash_d, background_color=(0.1,0.6,0.5,1), font_size=sp(16), bold=True))
        main.add_widget(row)
        self.item_lbl = Label(text="ITEM: 0", size_hint_y=None, height=dp(30), font_size=sp(15), color=(0.2,0.7,0.4,1), bold=True)
        main.add_widget(self.item_lbl)
        self.ibox = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(3))
        self.ibox.bind(minimum_height=self.ibox.setter("height"))
        main.add_widget(self.ibox)
        self.jama_lbl = Label(text="JAMA: 0", size_hint_y=None, height=dp(30), font_size=sp(15), color=(0.6,0.3,0.7,1), bold=True)
        main.add_widget(self.jama_lbl)
        self.jbox = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(3))
        self.jbox.bind(minimum_height=self.jbox.setter("height"))
        main.add_widget(self.jbox)
        self.calc_lbl = Label(text="", size_hint_y=None, height=dp(200), font_size=sp(14), halign="left", valign="top", markup=True, text_size=(Window.width-dp(30), None))
        main.add_widget(self.calc_lbl)
        row2 = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(6))
        row2.add_widget(Button(text="SAVE", on_press=self.save, background_color=(0.2,0.5,0.7,1), font_size=sp(15), bold=True))
        row2.add_widget(Button(text="PDF", on_press=self.print_pdf, background_color=(0.1,0.6,0.5,1), font_size=sp(15), bold=True))
        row2.add_widget(Button(text="NEW", on_press=self.newb, background_color=(0.9,0.6,0.1,1), font_size=sp(15), bold=True))
        main.add_widget(row2)
        self.add_widget(sv)
        self.recalc()
        self.rvi()

    def on_party(self, i, v):
        if v and len(v) > 1:
            m = get_mob(v.strip())
            if m and not self.mobile.text: self.mobile.text = m
        self.recalc()

    def add_d(self, sec):
        c = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(15))
        c.add_widget(Label(text="Item Name", size_hint_y=None, height=dp(25)))
        n = TextInput(multiline=False, size_hint_y=None, height=dp(45), font_size=sp(16), padding=[dp(10), dp(10)])
        c.add_widget(n)
        c.add_widget(Label(text="Weight (gram)", size_hint_y=None, height=dp(25)))
        w = TextInput(multiline=False, size_hint_y=None, height=dp(45), font_size=sp(16), padding=[dp(10), dp(10)], input_filter="float")
        c.add_widget(w)
        c.add_widget(Label(text="Touch", size_hint_y=None, height=dp(25)))
        t = TextInput(multiline=False, size_hint_y=None, height=dp(45), font_size=sp(16), padding=[dp(10), dp(10)], input_filter="float")
        c.add_widget(t)
        p = Popup(title=sec, content=c, size_hint=(0.95,0.75))
        def ok(x):
            try:
                nm = n.text.strip()
                ww = float(w.text) if w.text.strip() else 0.0
                tt = float(t.text) if t.text.strip() else 0.0
                if not nm: return
                fi = ww * tt / 100
                if sec == "ITEM": self.items.append([nm, ww, tt, fi])
                else: self.jama.append([nm, ww, tt, fi])
                p.dismiss(); self.rvi(); self.recalc()
            except: pass
        r = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(8))
        r.add_widget(Button(text="ADD", on_press=ok, background_color=(0.2,0.7,0.4,1), font_size=sp(16), bold=True))
        r.add_widget(Button(text="CANCEL", on_press=lambda x: p.dismiss(), background_color=(0.9,0.3,0.3,1), font_size=sp(16), bold=True))
        c.add_widget(r); p.open()

    def cash_d(self, *a):
        c = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(15))
        c.add_widget(Label(text="Cash Amount (Rs)", size_hint_y=None, height=dp(30), font_size=sp(16), bold=True))
        amt = TextInput(multiline=False, size_hint_y=None, height=dp(50), font_size=sp(18), padding=[dp(10), dp(10)], input_filter="float", text=str(int(self.cash_amount)) if self.cash_amount > 0 else "")
        c.add_widget(amt)
        p = Popup(title="Cash", content=c, size_hint=(0.95,0.5))
        def ok(x):
            try: self.cash_amount = float(amt.text) if amt.text.strip() else 0.0
            except: self.cash_amount = 0.0
            p.dismiss(); self.recalc()
        r = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(8))
        r.add_widget(Button(text="OK", on_press=ok, background_color=(0.2,0.7,0.4,1), font_size=sp(16), bold=True))
        r.add_widget(Button(text="CANCEL", on_press=lambda x: p.dismiss(), background_color=(0.9,0.3,0.3,1), font_size=sp(16), bold=True))
        c.add_widget(r); p.open()

    def rvi(self):
        self.ibox.clear_widgets()
        for idx, it in enumerate(self.items):
            r = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4))
            r.add_widget(Label(text="%d. %s %.3fg %.2f%% =%.3fg" % (idx+1, it[0], it[1], it[2], it[3]), font_size=sp(12), halign="left", valign="middle", text_size=(Window.width-dp(140), None)))
            eb = Button(text="EDIT", size_hint=(None,1), width=dp(55), background_color=(0.2,0.5,0.8,1), font_size=sp(11), bold=True)
            eb.bind(on_press=lambda x, i=idx: self.edit_i("ITEM", i)); r.add_widget(eb)
            db = Button(text="X", size_hint=(None,1), width=dp(40), background_color=(0.9,0.3,0.3,1), font_size=sp(14), bold=True)
            db.bind(on_press=lambda x, i=idx: self.del_i("ITEM", i)); r.add_widget(db)
            self.ibox.add_widget(r)
        self.item_lbl.text = "ITEM: " + str(len(self.items))
        self.jbox.clear_widgets()
        for idx, it in enumerate(self.jama):
            r = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4))
            r.add_widget(Label(text="%d. %s %.3fg %.2f%% =%.3fg" % (idx+1, it[0], it[1], it[2], it[3]), font_size=sp(12), halign="left", valign="middle", text_size=(Window.width-dp(140), None)))
            eb = Button(text="EDIT", size_hint=(None,1), width=dp(55), background_color=(0.2,0.5,0.8,1), font_size=sp(11), bold=True)
            eb.bind(on_press=lambda x, i=idx: self.edit_i("JAMA", i)); r.add_widget(eb)
            db = Button(text="X", size_hint=(None,1), width=dp(40), background_color=(0.9,0.3,0.3,1), font_size=sp(14), bold=True)
            db.bind(on_press=lambda x, i=idx: self.del_i("JAMA", i)); r.add_widget(db)
            self.jbox.add_widget(r)
        self.jama_lbl.text = "JAMA: " + str(len(self.jama))

    def edit_i(self, sec, idx):
        lst = self.items if sec == "ITEM" else self.jama
        if idx < 0 or idx >= len(lst): return
        it = lst[idx]
        c = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(15))
        c.add_widget(Label(text="Item Name", size_hint_y=None, height=dp(25)))
        n = TextInput(text=str(it[0]), multiline=False, size_hint_y=None, height=dp(45), font_size=sp(16), padding=[dp(10), dp(10)])
        c.add_widget(n)
        c.add_widget(Label(text="Weight", size_hint_y=None, height=dp(25)))
        w = TextInput(text=str(it[1]), multiline=False, size_hint_y=None, height=dp(45), font_size=sp(16), padding=[dp(10), dp(10)], input_filter="float")
        c.add_widget(w)
        c.add_widget(Label(text="Touch", size_hint_y=None, height=dp(25)))
        t = TextInput(text=str(it[2]), multiline=False, size_hint_y=None, height=dp(45), font_size=sp(16), padding=[dp(10), dp(10)], input_filter="float")
        c.add_widget(t)
        p = Popup(title="Edit " + sec, content=c, size_hint=(0.95,0.75))
        def ok(x):
            try:
                nm = n.text.strip()
                ww = float(w.text) if w.text.strip() else 0.0
                tt = float(t.text) if t.text.strip() else 0.0
                if not nm: return
                fi = ww * tt / 100
                lst[idx] = [nm, ww, tt, fi]
                p.dismiss(); self.rvi(); self.recalc()
            except: pass
        r = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(8))
        r.add_widget(Button(text="SAVE", on_press=ok, background_color=(0.2,0.7,0.4,1), font_size=sp(16), bold=True))
        r.add_widget(Button(text="CANCEL", on_press=lambda x: p.dismiss(), background_color=(0.9,0.3,0.3,1), font_size=sp(16), bold=True))
        c.add_widget(r); p.open()

    def del_i(self, sec, idx):
        if sec == "ITEM" and 0 <= idx < len(self.items): self.items.pop(idx)
        elif sec == "JAMA" and 0 <= idx < len(self.jama): self.jama.pop(idx)
        self.rvi(); self.recalc()

    def recalc(self):
        iw = sum(i[1] for i in self.items); iff = sum(i[3] for i in self.items)
        jw = sum(j[1] for j in self.jama); jf = sum(j[3] for j in self.jama)
        try: bh = float(self.bhaw.text) if self.bhaw.text.strip() else 0.0
        except: bh = 0.0
        cf = (self.cash_amount / (bh/10.0)) if bh > 0 else 0.0
        ob = old_bal(self.party.text.strip())
        nt = iff + ob; tj = jf + cf; up = nt - tj; am = up * bh / 10.0
        t = "[b]ITEM[/b] Wt: %.3f Fine: %.3f\n" % (iw, iff)
        t += "[b]JAMA[/b] Wt: %.3f Fine: %.3f\n" % (jw, jf)
        t += "[b]Cash:[/b] Rs %.0f (Fine: %.3f)\n" % (self.cash_amount, cf)
        t += "-----------------\n"
        t += "Old Bal: %.3f\n" % ob
        t += "Net Total: %.3f\n" % nt
        t += "Total Jama: %.3f\n" % tj
        t += "[b][color=8e44ad]Uptodate: %.3f[/color][/b]\n" % up
        t += "[b][color=e67e22]Bhawkata: Rs %.2f[/color][/b]" % am
        self.calc_lbl.text = t

    def save(self, *a):
        p = self.party.text.strip()
        if not p: self.msg("Error", "Party naam likho!"); return
        try: bn = int(self.bno.text)
        except: self.msg("Error", "Bill No galat!"); return
        iw = sum(i[1] for i in self.items); iff = sum(i[3] for i in self.items)
        jw = sum(j[1] for j in self.jama); jf = sum(j[3] for j in self.jama)
        try: bh = float(self.bhaw.text) if self.bhaw.text.strip() else 0.0
        except: bh = 0.0
        cf = (self.cash_amount / (bh/10.0)) if bh > 0 else 0.0
        ob = old_bal(p); nt = iff + ob; tj = jf + cf; up = nt - tj; am = up * bh / 10.0
        conn = sqlite3.connect(DB); c = conn.cursor()
        c.execute("INSERT INTO bills (bill_no, date, party, mobile, bhaw, old_balance, item_weight, item_fine, jama_weight, jama_fine, cash_amount, cash_fine, net_total, uptodate, bhawkata_amount) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (bn, datetime.now().strftime("%d-%m-%Y"), p, self.mobile.text, bh, ob, iw, iff, jw, jf, self.cash_amount, cf, nt, up, am))
        bid = c.lastrowid
        for it in self.items:
            c.execute("INSERT INTO items (bill_id, section, name, weight, touch, fine) VALUES (?,?,?,?,?,?)", (bid, "ITEM", it[0], it[1], it[2], it[3]))
        for it in self.jama:
            c.execute("INSERT INTO items (bill_id, section, name, weight, touch, fine) VALUES (?,?,?,?,?,?)", (bid, "JAMA", it[0], it[1], it[2], it[3]))
        c.execute("INSERT INTO parties (name, mobile, last_balance) VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET mobile=excluded.mobile, last_balance=excluded.last_balance", (p, self.mobile.text, up))
        conn.commit(); conn.close()
        self.msg("Saved!", "Bill " + str(bn) + " save!\nUptodate: %.3f" % up)
        if self.app_ref and hasattr(self.app_ref, 'cust_screen'):
            self.app_ref.cust_screen.refresh()

    def print_pdf(self, *a):
        p = self.party.text.strip()
        if not p: self.msg("Error", "Party naam likho!"); return
        try: bn = int(self.bno.text)
        except: self.msg("Error", "Bill No galat!"); return
        iw = sum(i[1] for i in self.items); iff = sum(i[3] for i in self.items)
        jw = sum(j[1] for j in self.jama); jf = sum(j[3] for j in self.jama)
        try: bh = float(self.bhaw.text) if self.bhaw.text.strip() else 0.0
        except: bh = 0.0
        cf = (self.cash_amount / (bh/10.0)) if bh > 0 else 0.0
        ob = old_bal(p); nt = iff + ob; tj = jf + cf; up = nt - tj; am = up * bh / 10.0
        fn = make_pdf(bn, datetime.now().strftime("%d-%m-%Y"), p, self.mobile.text, bh, ob, self.items, self.jama, self.cash_amount, cf, nt, up, am)
        if fn: self.msg("PDF Saved!", "Invoice:\n" + fn)
        else: self.msg("Error", "PDF nahi bani")

    def newb(self, *a):
        self.bno.text = str(next_bn())
        self.party
